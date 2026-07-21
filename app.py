from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from cosmed_utils import (
    calculate_enhanced_epoch_summary,
    calculate_enhanced_summary,
    convert_time_to_seconds,
    create_epochs_from_markers,
    dataframe_to_excel_bytes,
    detect_available_variables,
    load_biopac_txt,
    load_cosmed_file,
    missingness_by_variable,
    parse_manual_markers,
    qc_overview,
    resample_data_with_method,
    run_qc_checks,
    smooth_data_advanced,
)


PROJECT_ROOT = Path(__file__).resolve().parent
EXAMPLE_FILE = PROJECT_ROOT / "examples" / "synthetic_cosmed_export.xlsx"
PLOT_COLORS = px.colors.qualitative.Safe

VARIABLE_GROUPS = {
    "Ventilation": ["VE", "Rf", "VT", "IV", "Ti", "Te", "Ttot", "Ti/Ttot", "BR"],
    "Gas exchange": ["VO2", "VCO2", "RQ", "VO2/kg", "METS", "VE/VO2", "VE/VCO2"],
    "Expired gases": ["FeO2", "FeCO2", "FetO2", "FetCO2", "PetO2", "PetCO2"],
    "Environmental": ["Amb. Temp.", "RH Amb", "Device Temp.", "PB", "RH Sample"],
    "GPS and movement": ["GPS Speed", "GPS Dist.", "GPS Altitude", "Cadence", "Long", "Lat"],
    "Timing and markers": ["t", "t_seconds", "Phase", "Marker", "Phase time"],
}


st.set_page_config(
    page_title="COLD-CUTS COSMED Viewer v1.0",
    page_icon="CC",
    layout="wide",
)

st.markdown(
    """
    <style>
    :root {
        --primary-dark: #16324F;
        --secondary-teal: #1F6F78;
        --accent-blue: #3B82F6;
        --background: #F4F7FA;
        --card: #FFFFFF;
        --text: #17212B;
        --muted: #52606D;
        --warning: #ED9B40;
        --error: #C62828;
        --border: #D7DEE7;
    }
    .stApp {
        background: var(--background);
        color: var(--text);
    }
    section[data-testid="stSidebar"] {
        background: var(--primary-dark);
    }
    section[data-testid="stSidebar"] * {
        color: #FFFFFF;
    }
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] textarea,
    section[data-testid="stSidebar"] select,
    section[data-testid="stSidebar"] [data-baseweb="select"] * {
        color: var(--text) !important;
    }
    .hero {
        background: var(--card);
        border: 1px solid var(--border);
        border-left: 6px solid var(--secondary-teal);
        border-radius: 8px;
        padding: 1.15rem 1.35rem;
        margin-bottom: 1rem;
    }
    .hero h1 {
        color: var(--text);
        font-size: 1.9rem;
        margin: 0;
        letter-spacing: 0;
    }
    .hero p, .muted {
        color: var(--muted);
        margin: 0.35rem 0 0 0;
    }
    .info-card {
        background: #FFF9EC;
        border: 1px solid var(--warning);
        border-radius: 8px;
        padding: 0.9rem 1rem;
        color: var(--text);
    }
    .status-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 0.75rem 0.85rem;
        min-height: 82px;
    }
    .status-label {
        color: var(--muted);
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
    }
    .status-value {
        color: var(--text);
        font-size: 1.05rem;
        font-weight: 750;
        margin-top: 0.2rem;
        word-break: break-word;
    }
    div.stButton > button, div.stDownloadButton > button {
        border-radius: 8px;
        border: 1px solid var(--secondary-teal);
        background: var(--secondary-teal);
        color: #FFFFFF;
        font-weight: 700;
    }
    div.stButton > button:hover, div.stDownloadButton > button:hover {
        border: 1px solid var(--primary-dark);
        background: var(--primary-dark);
        color: #FFFFFF;
    }
    label, .stMarkdown, .stDataFrame {
        color: var(--text);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def write_uploaded_file(uploaded_file: Any) -> Path:
    """Save a Streamlit upload to a temporary file and return its path."""
    suffix = Path(uploaded_file.name).suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(uploaded_file.getbuffer())
        return Path(temp_file.name)


@st.cache_data(show_spinner=False)
def list_excel_sheets(file_bytes: bytes) -> list[str]:
    """Return worksheet names for an uploaded Excel file."""
    with NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
        temp_file.write(file_bytes)
        temp_path = Path(temp_file.name)
    return pd.ExcelFile(temp_path, engine="openpyxl").sheet_names


def parse_time_input(value: str) -> float | None:
    """Parse empty, seconds, mm:ss, or hh:mm:ss time text."""
    if not str(value).strip():
        return None
    parsed = convert_time_to_seconds(pd.Series([value])).iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def seconds_to_label(value: float | int | None) -> str:
    """Format seconds as HH:MM:SS for display."""
    if value is None or pd.isna(value):
        return "N/A"
    value = int(float(value))
    hours = value // 3600
    minutes = (value % 3600) // 60
    seconds = value % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def numeric_columns(df: pd.DataFrame) -> list[str]:
    """Return columns with at least one valid numeric value."""
    return [col for col in df.columns if pd.to_numeric(df[col], errors="coerce").notna().any()]


def variable_group(column: str) -> str:
    """Assign a friendly group name to a variable."""
    for group, names in VARIABLE_GROUPS.items():
        if column in names:
            return group
    if column == "t_seconds":
        return "Timing and markers"
    return "Other"


def filter_variables(
    candidates: list[str],
    search: str,
    group: str,
    df: pd.DataFrame,
    max_missing_pct: float,
) -> list[str]:
    """Filter available variable names by search, group, and missingness."""
    filtered = []
    for col in candidates:
        if search and search.lower() not in col.lower():
            continue
        if group != "All" and variable_group(col) != group:
            continue
        missing_pct = df[col].isna().mean() * 100 if col in df.columns and len(df) else 0
        if missing_pct > max_missing_pct:
            continue
        filtered.append(col)
    return filtered


def make_manual_epoch_table(text: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Parse markers and derive epochs."""
    markers = parse_manual_markers(text)
    epochs = create_epochs_from_markers(markers)
    return markers, epochs


def make_event_epochs(event_text: str) -> list[dict[str, Any]]:
    """Create epochs from lines such as '05:00 Hand In'."""
    rows = []
    for line in event_text.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) != 2:
            continue
        seconds = parse_time_input(parts[0])
        if seconds is not None:
            rows.append({"label": parts[1], "seconds": seconds})
    rows = sorted(rows, key=lambda row: row["seconds"])
    epochs = []
    for index, row in enumerate(rows):
        end = rows[index + 1]["seconds"] if index + 1 < len(rows) else np.nan
        epochs.append({"epoch": row["label"], "start": row["seconds"], "end": end})
    return epochs


def load_epoch_file(uploaded_epoch_file: Any) -> list[dict[str, Any]]:
    """Load epochs from CSV, TXT, TSV, or Excel with name/start/end columns."""
    if uploaded_epoch_file is None:
        return []
    suffix = Path(uploaded_epoch_file.name).suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        epoch_df = pd.read_excel(uploaded_epoch_file)
    elif suffix == ".tsv":
        epoch_df = pd.read_csv(uploaded_epoch_file, sep="\t")
    else:
        epoch_df = pd.read_csv(uploaded_epoch_file)

    lower_map = {str(col).strip().lower(): col for col in epoch_df.columns}
    name_col = lower_map.get("epoch name") or lower_map.get("phase") or lower_map.get("name") or epoch_df.columns[0]
    start_col = lower_map.get("start time") or lower_map.get("start") or epoch_df.columns[1]
    end_col = lower_map.get("end time") or lower_map.get("end") or epoch_df.columns[2]

    epochs = []
    for _, row in epoch_df.iterrows():
        start = parse_time_input(str(row[start_col]))
        end = parse_time_input(str(row[end_col]))
        if start is not None:
            epochs.append({"epoch": str(row[name_col]), "start": start, "end": end if end is not None else np.nan})
    return epochs


def epochs_to_dataframe(epochs: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert epoch dictionaries into a display table."""
    if not epochs:
        return pd.DataFrame(columns=["Phase", "Start", "End"])
    return pd.DataFrame([
        {
            "Phase": epoch["epoch"],
            "Start": seconds_to_label(epoch["start"]),
            "End": seconds_to_label(epoch["end"]),
            "start_seconds": epoch["start"],
            "end_seconds": epoch["end"],
        }
        for epoch in epochs
    ])


def add_epoch_shapes(fig: go.Figure, epochs: list[dict[str, Any]]) -> go.Figure:
    """Add vertical epoch boundary lines and shaded regions to a Plotly figure."""
    for epoch in epochs:
        start = epoch["start"]
        end = epoch["end"]
        fig.add_vline(x=start, line_dash="dash", line_color="#52606D", opacity=0.65)
        fig.add_annotation(x=start, y=1.02, yref="paper", text=str(epoch["epoch"]), showarrow=False, font_size=11)
        if pd.notna(end):
            fig.add_vrect(x0=start, x1=end, fillcolor="#3B82F6", opacity=0.06, line_width=0)
    return fig


def time_series_plot(
    df: pd.DataFrame,
    selected: list[str],
    epochs: list[dict[str, Any]],
    qc_report: pd.DataFrame,
    separate_charts: bool,
    time_col: str,
) -> go.Figure:
    """Build an interactive time-series plot with QC markers."""
    x = df[time_col] if time_col in df.columns else pd.Series(df.index, index=df.index)
    fig = go.Figure()
    numeric_selected = [col for col in selected if col in df.columns and pd.to_numeric(df[col], errors="coerce").notna().any()]
    for idx, col in enumerate(numeric_selected):
        y = pd.to_numeric(df[col], errors="coerce")
        axis = "y" if not separate_charts or idx == 0 else f"y{idx + 1}"
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode="lines",
            name=col,
            line={"color": PLOT_COLORS[idx % len(PLOT_COLORS)], "width": 2},
            yaxis=axis,
            hovertemplate=f"Time=%{{x}}<br>{col}=%{{y}}<extra></extra>",
        ))

    if not qc_report.empty and "row" in qc_report.columns:
        flagged_rows = [row for row in qc_report.dropna(subset=["row"])["row"].astype(int).unique() if row in df.index]
        if flagged_rows:
            fig.add_trace(go.Scatter(
                x=x.loc[flagged_rows],
                y=[0] * len(flagged_rows),
                mode="markers",
                name="QC flagged row",
                marker={"color": "#C62828", "size": 8, "symbol": "x"},
                hovertemplate="QC flagged row<br>Time=%{x}<extra></extra>",
            ))

    if separate_charts and len(numeric_selected) > 1:
        for idx, col in enumerate(numeric_selected):
            key = "yaxis" if idx == 0 else f"yaxis{idx + 1}"
            fig.update_layout({
                key: {
                    "title": col,
                    "domain": [1 - (idx + 1) / len(numeric_selected), 1 - idx / len(numeric_selected) - 0.02],
                }
            })

    add_epoch_shapes(fig, epochs)
    fig.update_layout(
        height=max(420, 220 * max(1, len(numeric_selected))) if separate_charts else 520,
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        font={"color": "#17212B"},
        xaxis={"title": "Time (seconds)", "rangeslider": {"visible": True}},
        legend={"orientation": "h", "y": -0.25},
        margin={"l": 40, "r": 20, "t": 40, "b": 80},
    )
    return fig


def phase_comparison_plot(phase_summary: pd.DataFrame) -> go.Figure:
    """Create a phase mean comparison plot."""
    if phase_summary.empty:
        return go.Figure()
    fig = px.bar(
        phase_summary,
        x="Phase",
        y="Mean",
        color="Variable",
        error_y="SD" if "SD" in phase_summary.columns else None,
        barmode="group",
        color_discrete_sequence=PLOT_COLORS,
    )
    fig.update_layout(plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", font={"color": "#17212B"})
    return fig


def distribution_plot(df: pd.DataFrame, selected: list[str], plot_type: str) -> go.Figure:
    """Create a histogram or box plot for selected numeric variables."""
    long_df = df[selected].apply(pd.to_numeric, errors="coerce").melt(var_name="Variable", value_name="Value").dropna()
    if long_df.empty:
        return go.Figure()
    if plot_type == "Box plot":
        fig = px.box(long_df, x="Variable", y="Value", color="Variable", color_discrete_sequence=PLOT_COLORS)
    else:
        fig = px.histogram(long_df, x="Value", color="Variable", barmode="overlay", opacity=0.7, color_discrete_sequence=PLOT_COLORS)
    fig.update_layout(plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", font={"color": "#17212B"})
    return fig


def relationship_stats(df: pd.DataFrame, x_col: str, y_col: str) -> tuple[pd.DataFrame, go.Figure]:
    """Calculate Pearson/Spearman correlations and draw a scatterplot."""
    paired = pd.DataFrame({
        x_col: pd.to_numeric(df[x_col], errors="coerce"),
        y_col: pd.to_numeric(df[y_col], errors="coerce"),
    }).dropna()
    if len(paired) < 3:
        return pd.DataFrame({"Message": ["Need at least 3 paired values."]}), go.Figure()

    stats = pd.DataFrame([{
        "X": x_col,
        "Y": y_col,
        "N": len(paired),
        "Pearson r": paired[x_col].corr(paired[y_col], method="pearson"),
        "Spearman rho": paired[x_col].corr(paired[y_col], method="spearman"),
    }])
    fig = px.scatter(paired, x=x_col, y=y_col, trendline="ols", color_discrete_sequence=["#1F6F78"])
    fig.update_layout(plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF", font={"color": "#17212B"})
    return stats, fig


def download_csv(df: pd.DataFrame) -> bytes:
    """Encode a DataFrame as CSV bytes."""
    return df.to_csv(index=False).encode("utf-8")


def manifest_text(settings: dict[str, Any]) -> str:
    """Render a small analysis manifest as plain text."""
    lines = [f"{key}: {value}" for key, value in settings.items()]
    return "\n".join(lines).encode("utf-8").decode("utf-8")


st.markdown(
    """
    <div class="hero">
        <h1>COLD-CUTS COSMED Viewer v1.0</h1>
        <p>Scientific dashboard for COSMED K5 exports and basic BIOPAC/Laser Doppler text files.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.title("Controls")
    with st.expander("1. Data source", expanded=True):
        data_source = st.selectbox("Data Source", ["COSMED K5 (.xlsx/.csv/.txt/.tsv)", "BIOPAC / Laser Doppler (.txt)"])
        uploaded_file = st.file_uploader("Upload file", type=["xlsx", "csv", "txt", "tsv"])
        use_example = st.toggle("Use synthetic COSMED demo", value=uploaded_file is None)
        worksheet_name = 0
        if uploaded_file is not None and Path(uploaded_file.name).suffix.lower() in {".xlsx", ".xls"}:
            sheets = list_excel_sheets(uploaded_file.getvalue())
            worksheet_name = st.selectbox("Worksheet", sheets)
        header_override_text = st.text_input("Header row override", value="", help="Leave blank for automatic detection. Use 0 for the first row.")

    with st.expander("2. Time and processing", expanded=True):
        start_time_text = st.text_input("Manual start time", value="", placeholder="00:30")
        end_time_text = st.text_input("Manual end time", value="", placeholder="05:00")
        resampling_label = st.selectbox(
            "Resampling",
            ["Raw/original", "1-second", "5-second", "10-second", "15-second", "30-second", "1-minute", "Custom interval"],
        )
        custom_interval = st.number_input("Custom interval seconds", min_value=1, max_value=3600, value=20)
        aggregation_method = st.selectbox("Aggregation method", ["Mean", "Median", "Minimum", "Maximum", "First", "Last"])
        smoothing_method = st.selectbox("Smoothing", ["None", "Rolling mean", "Rolling median", "Exponential moving average", "Savitzky-Golay"])
        smoothing_window = st.slider("Smoothing window", min_value=3, max_value=61, value=5, step=2)

    with st.expander("3. QC settings", expanded=True):
        flag_speaking = st.checkbox("Flag possible speaking", value=True)
        flag_movement = st.checkbox("Flag possible movement", value=True)
        flag_missing = st.checkbox("Flag missing values", value=True)
        flag_jumps = st.checkbox("Flag sudden jumps", value=True)
        flag_impossible = st.checkbox("Flag impossible values", value=True)
        exclude_flagged_rows = st.checkbox("Exclude flagged rows from calculations", value=False)

    with st.expander("4. Variable filtering", expanded=False):
        variable_search = st.text_input("Search variables", value="")
        variable_group_choice = st.selectbox("Variable group", ["All"] + sorted(set(VARIABLE_GROUPS.keys()) | {"Other"}))
        max_missing_pct = st.slider("Exclude variables above missing %", 0, 100, 100)

st.markdown(
    """
    <div class="info-card">
    <strong>Important interpretation note:</strong> QC flags are review prompts only. They cannot prove speaking,
    movement, sensor failure, disease, or any specific event.
    </div>
    """,
    unsafe_allow_html=True,
)

header_override = int(header_override_text) if header_override_text.strip().isdigit() else None
run_analysis = st.button("Run Analysis", width="stretch")

if not run_analysis:
    st.info("Upload a file or use the synthetic demo, adjust the sidebar, then click Run Analysis.")
    st.stop()

try:
    if data_source.startswith("BIOPAC"):
        if uploaded_file is None:
            st.error("BIOPAC/Laser Doppler mode needs a .txt upload.")
            st.stop()
        file_path = write_uploaded_file(uploaded_file)
        raw_df, detection = load_biopac_txt(file_path)
        source_name = uploaded_file.name
        time_col = "t_seconds"
        header_confidence = "N/A"
    else:
        if uploaded_file is not None:
            file_path = write_uploaded_file(uploaded_file)
            source_name = uploaded_file.name
        elif use_example:
            file_path = EXAMPLE_FILE
            source_name = EXAMPLE_FILE.name
        else:
            st.error("Upload a COSMED file or turn on the synthetic demo.")
            st.stop()
        raw_df, detection = load_cosmed_file(file_path, sheet_name=worksheet_name, header_override=header_override)
        time_col = "t_seconds" if "t_seconds" in raw_df.columns else raw_df.columns[0]
        header_confidence = "N/A" if pd.isna(detection.get("confidence")) else f"{detection.get('confidence', 0):.2f}"
except Exception as error:
    st.error(f"Could not load the file. Details: {error}")
    st.stop()

if data_source.startswith("BIOPAC"):
    st.subheader("BIOPAC / Laser Doppler Import Preview")
    biopac_cols = st.columns(6)
    biopac_cols[0].metric("Duration", seconds_to_label(detection.get("duration_seconds")))
    biopac_cols[1].metric("Sample rate", "N/A" if pd.isna(detection.get("sample_rate")) else f"{detection.get('sample_rate')} Hz")
    biopac_cols[2].metric("Samples", f"{detection.get('total_samples', 0):,}")
    biopac_cols[3].metric("Channels", f"{len(detection.get('columns', [])) - 1:,}")
    biopac_cols[4].metric("Missing", f"{detection.get('missing_values', 0):,}")
    biopac_cols[5].metric("Memory", f"{detection.get('memory_usage_mb', 0):.2f} MB")
    st.dataframe(raw_df.head(20), width="stretch")

available_variables = [col for col in detect_available_variables(raw_df) if col != time_col]
if not available_variables:
    available_variables = [col for col in numeric_columns(raw_df) if col != time_col]
available_variables = filter_variables(available_variables, variable_search, variable_group_choice, raw_df, max_missing_pct)

if not available_variables:
    st.warning("No variables match the current filters.")
    st.stop()

default_variables = [col for col in ["VO2", "VCO2", "VE", "Rf"] if col in available_variables] or available_variables[: min(4, len(available_variables))]
selector_cols = st.columns([3, 1, 1])
selected_variables = selector_cols[0].multiselect("Variables", available_variables, default=default_variables)
if selector_cols[1].button("Select all"):
    selected_variables = available_variables
if selector_cols[2].button("Clear all"):
    selected_variables = []

if not selected_variables:
    st.warning("Choose at least one variable to analyze.")
    st.stop()

full_min = float(pd.to_numeric(raw_df[time_col], errors="coerce").min()) if time_col in raw_df.columns else 0.0
full_max = float(pd.to_numeric(raw_df[time_col], errors="coerce").max()) if time_col in raw_df.columns else float(len(raw_df))
range_start, range_end = st.slider(
    "Selected time range",
    min_value=full_min,
    max_value=full_max,
    value=(full_min, full_max),
    step=max((full_max - full_min) / 200, 1.0),
)
manual_start = parse_time_input(start_time_text)
manual_end = parse_time_input(end_time_text)
start_time = manual_start if manual_start is not None else range_start
end_time = manual_end if manual_end is not None else range_end
if end_time <= start_time:
    st.error("End time must be after start time.")
    st.stop()

resampling_seconds = {
    "Raw/original": None,
    "1-second": 1,
    "5-second": 5,
    "10-second": 10,
    "15-second": 15,
    "30-second": 30,
    "1-minute": 60,
    "Custom interval": int(custom_interval),
}[resampling_label]

filtered_df = raw_df.copy()
filtered_df = filtered_df[(pd.to_numeric(filtered_df[time_col], errors="coerce") >= start_time) & (pd.to_numeric(filtered_df[time_col], errors="coerce") <= end_time)]
processed_df = resample_data_with_method(filtered_df, time_col, resampling_seconds, aggregation_method)
processed_df = smooth_data_advanced(processed_df, selected_variables, smoothing_method, smoothing_window)

st.subheader("Epoch Builder")
epoch_method = st.radio("Choose epoch method", ["Manual start/end markers", "Event marker builder", "Import epoch file"], horizontal=True)
manual_marker_text = ""
event_marker_text = ""
uploaded_epoch_file = None
if epoch_method == "Manual start/end markers":
    manual_marker_text = st.text_area(
        "Manual markers",
        value="Baseline start, 00:30\nBaseline end, 02:30\nCold Water start, 03:00\nCold Water end, 04:00\nRecovery start, 04:30",
        height=135,
    )
    marker_table, epochs = make_manual_epoch_table(manual_marker_text)
elif epoch_method == "Event marker builder":
    event_marker_text = st.text_area(
        "Event markers",
        value="00:00 Baseline\n05:00 Hand In\n08:00 Peak Cold\n15:00 Recovery",
        height=135,
    )
    epochs = make_event_epochs(event_marker_text)
    marker_table = pd.DataFrame()
else:
    uploaded_epoch_file = st.file_uploader("Upload epoch file", type=["csv", "txt", "tsv", "xlsx"], key="epoch_file")
    epochs = load_epoch_file(uploaded_epoch_file)
    marker_table = pd.DataFrame()

qc_report = run_qc_checks(
    processed_df,
    selected_variables,
    flag_speaking=flag_speaking and data_source.startswith("COSMED"),
    flag_movement=flag_movement,
    flag_missing=flag_missing,
    flag_jumps=flag_jumps,
    flag_impossible=flag_impossible,
)

analysis_df = processed_df.copy()
excluded_rows = set()
if exclude_flagged_rows and not qc_report.empty:
    excluded_rows = set(qc_report.dropna(subset=["row"])["row"].astype(int).tolist())
    analysis_df = analysis_df.loc[[idx for idx in analysis_df.index if int(idx) not in excluded_rows]]

variable_summary = calculate_enhanced_summary(analysis_df, selected_variables, time_col=time_col)
phase_summary = calculate_enhanced_epoch_summary(analysis_df, selected_variables, epochs, qc_report, time_col=time_col)
qc_summary = qc_overview(qc_report, len(processed_df))
missing_summary = missingness_by_variable(processed_df, selected_variables)
usable_rows = len(processed_df) - len(excluded_rows)
usable_pct = (usable_rows / len(processed_df) * 100) if len(processed_df) else 0

status_values = [
    ("File", source_name),
    ("Rows analyzed", f"{len(analysis_df):,}"),
    ("Columns detected", f"{len(raw_df.columns):,}"),
    ("Time range", f"{seconds_to_label(start_time)} to {seconds_to_label(end_time)}"),
    ("Header confidence", header_confidence),
    ("QC flags", f"{len(qc_report):,}"),
    ("Usable rows", f"{usable_pct:.1f}%"),
]
status_cols = st.columns(len(status_values))
for col, (label, value) in zip(status_cols, status_values):
    col.markdown(
        f"<div class='status-card'><div class='status-label'>{label}</div><div class='status-value'>{value}</div></div>",
        unsafe_allow_html=True,
    )

tabs = st.tabs(["Data Overview", "Time Series", "Phase Analysis", "Relationships", "Quality Control", "Downloads"])

with tabs[0]:
    st.subheader("Detected Data")
    overview_cols = st.columns(2)
    with overview_cols[0]:
        st.write("Detected columns")
        st.dataframe(pd.DataFrame({"Column": list(raw_df.columns), "Group": [variable_group(col) for col in raw_df.columns]}), width="stretch")
    with overview_cols[1]:
        st.write("Cleaned preview")
        st.dataframe(processed_df.head(50), width="stretch")
    if data_source.startswith("COSMED"):
        with st.expander("COSMED header detection"):
            st.write(f"Detected header row: `{detection.get('header_row')}`")
            st.write(f"Matched headers: {', '.join(detection.get('matched_headers', []))}")

with tabs[1]:
    st.subheader("Interactive Time Series")
    separate_charts = st.toggle("Separate charts", value=True)
    fig = time_series_plot(processed_df, selected_variables, epochs, qc_report, separate_charts, time_col)
    st.plotly_chart(fig)
    plot_type = st.selectbox("Distribution view", ["Histogram", "Box plot"])
    st.plotly_chart(distribution_plot(analysis_df, selected_variables, plot_type))

with tabs[2]:
    st.subheader("Phase Analysis")
    st.dataframe(epochs_to_dataframe(epochs), width="stretch")
    if phase_summary.empty:
        st.info("No complete phase summaries yet. Define start/end epochs to populate this table.")
    else:
        st.dataframe(phase_summary, width="stretch")
        st.plotly_chart(phase_comparison_plot(phase_summary))

with tabs[3]:
    st.subheader("Relationships")
    relationship_vars = [col for col in selected_variables if pd.to_numeric(analysis_df[col], errors="coerce").notna().sum() >= 3]
    if len(relationship_vars) < 2:
        st.info("Choose at least two numeric variables with valid paired data.")
    else:
        rel_cols = st.columns(2)
        x_col = rel_cols[0].selectbox("X variable", relationship_vars, index=0)
        y_col = rel_cols[1].selectbox("Y variable", relationship_vars, index=min(1, len(relationship_vars) - 1))
        rel_stats, rel_fig = relationship_stats(analysis_df, x_col, y_col)
        st.dataframe(rel_stats, width="stretch")
        st.plotly_chart(rel_fig)

with tabs[4]:
    st.subheader("Quality Control")
    st.dataframe(qc_summary, width="stretch")
    st.write("Missingness by selected variable")
    st.dataframe(missing_summary, width="stretch")
    if qc_report.empty:
        st.success("No QC flags found with current settings.")
    else:
        issue_options = ["All"] + sorted(qc_report["issue"].dropna().unique().tolist())
        issue_filter = st.selectbox("QC category filter", issue_options)
        visible_qc = qc_report if issue_filter == "All" else qc_report[qc_report["issue"] == issue_filter]
        st.dataframe(visible_qc, width="stretch")

with tabs[5]:
    st.subheader("Downloads")
    settings = {
        "original_filename": source_name,
        "analysis_timestamp": datetime.now().isoformat(timespec="seconds"),
        "selected_variables": selected_variables,
        "time_range": f"{seconds_to_label(start_time)} to {seconds_to_label(end_time)}",
        "resampling": resampling_label,
        "aggregation": aggregation_method,
        "smoothing": f"{smoothing_method}, window {smoothing_window}",
        "qc_settings": {
            "speaking": flag_speaking,
            "movement": flag_movement,
            "missing": flag_missing,
            "jumps": flag_jumps,
            "impossible": flag_impossible,
            "exclude_flagged_rows": exclude_flagged_rows,
        },
        "defined_phases": epochs,
        "included_rows": len(analysis_df),
        "excluded_rows": len(excluded_rows),
    }
    st.download_button("Download filtered data CSV", download_csv(analysis_df), "filtered_data.csv", "text/csv")
    st.download_button(
        "Download filtered data Excel",
        dataframe_to_excel_bytes({"Filtered Data": analysis_df}),
        "filtered_data.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.download_button("Download variable summary CSV", download_csv(variable_summary), "variable_summary.csv", "text/csv")
    st.download_button("Download phase summary CSV", download_csv(phase_summary), "phase_summary.csv", "text/csv")
    st.download_button("Download QC report CSV", download_csv(qc_report), "qc_report.csv", "text/csv")
    st.download_button("Download event marker table CSV", download_csv(marker_table), "event_markers.csv", "text/csv")
    st.download_button("Download analysis manifest", manifest_text(settings), "analysis_manifest.txt", "text/plain")

st.caption("Raw uploaded data are preserved separately in memory. Processing is applied to copies for filtering, resampling, smoothing, and analytics.")

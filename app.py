from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import matplotlib
import pandas as pd
import streamlit as st

from cosmed_utils import (
    calculate_epoch_summary,
    calculate_summary_stats,
    convert_time_to_seconds,
    create_epochs_from_markers,
    detect_available_variables,
    load_cosmed_file,
    parse_manual_markers,
    plot_selected_variables,
    resample_data,
    run_qc_checks,
    smooth_data,
)


matplotlib.use("Agg")

PROJECT_ROOT = Path(__file__).resolve().parent
EXAMPLE_FILE = PROJECT_ROOT / "examples" / "synthetic_cosmed_export.xlsx"


st.set_page_config(
    page_title="COLD-CUTS COSMED Viewer v1.0",
    page_icon="CC",
    layout="wide",
)

st.markdown(
    """
    <style>
    .stApp {
        background:
            linear-gradient(135deg, rgba(245, 247, 251, 0.96), rgba(232, 241, 238, 0.96));
    }
    .hero {
        padding: 1.4rem 1.6rem;
        border: 1px solid #d8e2df;
        border-radius: 8px;
        background: #ffffff;
        margin-bottom: 1rem;
    }
    .hero h1 {
        margin: 0;
        color: #153c3b;
        font-size: 2rem;
        letter-spacing: 0;
    }
    .hero p {
        margin: 0.4rem 0 0 0;
        color: #405456;
        font-size: 1rem;
    }
    .metric-box {
        padding: 0.85rem 1rem;
        border-radius: 8px;
        border: 1px solid #d8e2df;
        background: #ffffff;
    }
    .small-note {
        color: #5a6668;
        font-size: 0.9rem;
    }
    div.stButton > button {
        border-radius: 8px;
        border: 1px solid #153c3b;
        background: #153c3b;
        color: white;
        font-weight: 650;
    }
    div.stButton > button:hover {
        border: 1px solid #1f6662;
        background: #1f6662;
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def parse_time_input(value: str) -> float | None:
    if not str(value).strip():
        return None
    parsed = convert_time_to_seconds(pd.Series([value])).iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def write_uploaded_file(uploaded_file) -> Path:
    suffix = Path(uploaded_file.name).suffix
    with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_file.write(uploaded_file.getbuffer())
        return Path(temp_file.name)


def load_source(uploaded_file, use_example: bool) -> tuple[pd.DataFrame, dict, str]:
    if uploaded_file is not None:
        file_path = write_uploaded_file(uploaded_file)
        source_name = uploaded_file.name
    elif use_example:
        file_path = EXAMPLE_FILE
        source_name = str(EXAMPLE_FILE)
    else:
        raise ValueError("Upload a COSMED file or turn on the example file option.")

    df, detection = load_cosmed_file(file_path)
    return df, detection, source_name


st.markdown(
    """
    <div class="hero">
        <h1>COLD-CUTS COSMED Viewer v1.0</h1>
        <p>Upload a COSMED K5 export, choose variables, filter time, flag possible artifacts, and view everything in one simple app.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Load Data")
    uploaded_file = st.file_uploader(
        "Upload COSMED file",
        type=["xlsx", "csv", "txt", "tsv"],
        help="COSMED exports can be messy. The app searches for the real table header.",
    )
    use_example = st.toggle("Use synthetic demo file", value=True)

    st.header("Time")
    start_time_text = st.text_input("Start time", value="", placeholder="Example: 00:30")
    end_time_text = st.text_input("End time", value="", placeholder="Example: 05:00")

    st.header("Averaging")
    resampling_choice = st.selectbox(
        "Refresh / resampling",
        ["raw/original", "1 second average", "5 second average", "10 second average", "30 second average", "60 second average"],
    )
    smoothing_choice = st.selectbox(
        "Smoothing",
        ["none", "rolling mean 5 samples", "rolling mean 10 samples", "rolling mean 30 samples"],
    )

    st.header("QC Flags")
    flag_speaking = st.checkbox("Possible speaking", value=True)
    flag_movement = st.checkbox("Possible movement", value=True)
    flag_missing = st.checkbox("Missing values", value=True)
    flag_jumps = st.checkbox("Sudden jumps", value=True)
    flag_impossible = st.checkbox("Impossible values", value=True)


left, right = st.columns([1.2, 1])

with left:
    st.subheader("Event Markers")
    marker_text = st.text_area(
        "Enter one marker per line",
        value="Baseline start, 00:30\nBaseline end, 02:30\nMovement start, 03:00\nMovement end, 04:00\nRecovery start, 04:30",
        height=150,
        help="Use labels like 'Baseline start, 00:30' and 'Baseline end, 02:30'.",
    )

with right:
    st.subheader("What this app can and cannot say")
    st.info(
        "Artifact flags are review prompts only. They can flag possible speaking or possible movement, "
        "but they cannot prove what happened."
    )

run_analysis = st.button("Run Analysis", width="stretch")

if not run_analysis:
    st.markdown(
        """
        <p class="small-note">
        Choose the demo file or upload your own COSMED export, adjust the sidebar settings, then click Run Analysis.
        </p>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

try:
    raw_df, detection, source_name = load_source(uploaded_file, use_example)
except Exception as error:
    st.error(f"Could not load the file: {error}")
    st.stop()

available_variables = detect_available_variables(raw_df)
if not available_variables:
    st.warning("No common COSMED variables were detected. Showing all columns so you can inspect the file.")
    available_variables = list(raw_df.columns)

default_variables = [col for col in ["VO2", "VCO2", "VE", "Rf"] if col in available_variables]
if not default_variables:
    default_variables = available_variables[:4]

selected_variables = st.multiselect(
    "Choose variables to analyze",
    options=available_variables,
    default=default_variables,
)

if not selected_variables:
    st.warning("Choose at least one variable.")
    st.stop()

df = raw_df.copy()
start_time = parse_time_input(start_time_text)
end_time = parse_time_input(end_time_text)

if "t_seconds" in df.columns:
    if start_time is not None:
        df = df[df["t_seconds"] >= start_time]
    if end_time is not None:
        df = df[df["t_seconds"] <= end_time]

df = resample_data(df, "t_seconds", resampling_choice)
df = smooth_data(df, selected_variables, smoothing_choice)

markers = parse_manual_markers(marker_text)
epochs = create_epochs_from_markers(markers)
summary = calculate_summary_stats(df, selected_variables)
epoch_summary = calculate_epoch_summary(df, selected_variables, epochs)
qc_report = run_qc_checks(
    df,
    selected_variables,
    flag_speaking=flag_speaking,
    flag_movement=flag_movement,
    flag_missing=flag_missing,
    flag_jumps=flag_jumps,
    flag_impossible=flag_impossible,
)

metric_cols = st.columns(4)
metric_cols[0].metric("Rows Analyzed", f"{len(df):,}")
metric_cols[1].metric("Columns Detected", f"{len(raw_df.columns):,}")
metric_cols[2].metric("Header Confidence", f"{detection['confidence']:.2f}")
metric_cols[3].metric("QC Flags", f"{len(qc_report):,}")

with st.expander("Detected File Details", expanded=True):
    st.write(f"File: `{source_name}`")
    st.write(f"Detected header row: `{detection['header_row']}`")
    st.write("Matched headers:")
    st.write(", ".join(detection["matched_headers"]) or "None")
    if detection["confidence"] < 0.5:
        st.warning("Low confidence header detection. Inspect the preview below.")
        st.dataframe(detection["preview"].head(20), width="stretch")

for column_name in ["Phase", "Marker"]:
    if column_name in raw_df.columns:
        unique_values = sorted(
            [str(value) for value in raw_df[column_name].dropna().unique() if str(value).strip()]
        )[:30]
        with st.expander(f"Unique {column_name} values"):
            st.write(unique_values)

tabs = st.tabs(["Plot", "Cleaned Preview", "Summary", "Epochs", "QC Report"])

with tabs[0]:
    fig = plot_selected_variables(df, selected_variables, epochs, qc_report)
    st.pyplot(fig, clear_figure=True)

with tabs[1]:
    st.dataframe(df.head(50), width="stretch")

with tabs[2]:
    st.dataframe(summary, width="stretch")

with tabs[3]:
    if epoch_summary.empty:
        st.info("No complete start/end epochs were entered.")
    else:
        st.dataframe(epoch_summary, width="stretch")

with tabs[4]:
    if qc_report.empty:
        st.success("No QC flags found with the current settings.")
    else:
        st.dataframe(qc_report, width="stretch")

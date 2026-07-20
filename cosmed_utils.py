"""Beginner-friendly helpers for COLD-CUTS COSMED Viewer v1.0."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


KNOWN_COSMED_HEADERS = {
    "t",
    "rf",
    "vt",
    "ve",
    "iv",
    "vo2",
    "vco2",
    "rq",
    "o2exp",
    "co2exp",
    "ve/vo2",
    "ve/vco2",
    "vo2/kg",
    "mets",
    "feo2",
    "feco2",
    "feto2",
    "fetco2",
    "fio2",
    "fico2",
    "peo2",
    "peco2",
    "peto2",
    "petco2",
    "phase",
    "marker",
    "amb. temp.",
    "rh amb",
    "device temp.",
    "analyz. press.",
    "pb",
    "eekc",
    "eeh",
    "eem",
    "eetot",
    "eekg",
    "pro",
    "fat",
    "cho",
    "pro%",
    "fat%",
    "cho%",
    "nprq",
    "long",
    "lat",
    "gps altitude",
    "barom_altitude",
    "gps speed",
    "gps dist.",
    "ti",
    "te",
    "ttot",
    "ti/ttot",
    "vd/vt e",
    "logve",
    "t rel",
    "mark speed",
    "mark distance",
    "battery",
    "phase time",
    "br",
    "o2 delay",
    "co2 delay",
    "gps heading",
    "rh sample",
    "cadence",
    "satellites",
    "fixing",
    "satellites snr",
    "vt/ti",
    "paco2_e",
    "hr",
}

PREFERRED_VARIABLES = [
    "VO2",
    "VCO2",
    "VE",
    "Rf",
    "VT",
    "RQ",
    "VO2/kg",
    "METS",
    "FeO2",
    "FeCO2",
    "PetO2",
    "PetCO2",
    "HR",
    "GPS Speed",
    "Phase",
    "Marker",
]

POSITIVE_PHYSIOLOGY_COLUMNS = ["VO2", "VCO2", "VE", "VT", "Rf"]


def _normalize_header(value: Any) -> str:
    return str(value).replace("\n", " ").replace("\r", " ").strip().lower()


def _read_raw_file(file_path: str | Path, nrows: int | None = None) -> pd.DataFrame:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, header=None, nrows=nrows, engine="openpyxl")
    if suffix == ".csv":
        return pd.read_csv(path, header=None, nrows=nrows)
    if suffix == ".tsv":
        return pd.read_csv(path, header=None, sep="\t", nrows=nrows)
    if suffix == ".txt":
        return pd.read_csv(path, header=None, sep=None, engine="python", nrows=nrows)
    raise ValueError(f"Unsupported file type: {suffix}. Use .xlsx, .csv, .txt, or .tsv.")


def _read_with_header(file_path: str | Path, header_row: int) -> pd.DataFrame:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, header=header_row, engine="openpyxl")
    if suffix == ".csv":
        return pd.read_csv(path, header=header_row)
    if suffix == ".tsv":
        return pd.read_csv(path, header=header_row, sep="\t")
    if suffix == ".txt":
        return pd.read_csv(path, header=header_row, sep=None, engine="python")
    raise ValueError(f"Unsupported file type: {suffix}. Use .xlsx, .csv, .txt, or .tsv.")


def detect_cosmed_header(file_path: str | Path) -> dict[str, Any]:
    """Find the row that looks most like the real COSMED data header."""
    preview = _read_raw_file(file_path, nrows=50)
    best_row = 0
    best_score = -1
    best_matches: list[str] = []

    for row_index, row in preview.iterrows():
        normalized = [_normalize_header(value) for value in row.dropna().tolist()]
        matches = [value for value in normalized if value in KNOWN_COSMED_HEADERS]
        if len(matches) > best_score:
            best_row = int(row_index)
            best_score = len(matches)
            best_matches = matches

    confidence = min(best_score / 8, 1.0) if best_score > 0 else 0.0
    return {
        "header_row": best_row,
        "score": best_score,
        "confidence": confidence,
        "matched_headers": best_matches,
        "preview": preview,
    }


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace and remove line breaks from column names."""
    cleaned = df.copy()
    cleaned.columns = [
        str(col).replace("\n", " ").replace("\r", " ").strip()
        for col in cleaned.columns
    ]
    cleaned = cleaned.loc[:, ~cleaned.columns.str.contains("^Unnamed")]
    return cleaned


def convert_time_to_seconds(series: pd.Series) -> pd.Series:
    """Convert seconds, mm:ss, or hh:mm:ss values into seconds."""
    def convert_one(value: Any) -> float:
        if pd.isna(value):
            return np.nan
        if isinstance(value, pd.Timedelta):
            return value.total_seconds()
        if isinstance(value, (int, float, np.integer, np.floating)):
            return float(value)

        text = str(value).strip()
        if not text:
            return np.nan
        if ":" not in text:
            try:
                return float(text)
            except ValueError:
                return np.nan

        parts = text.split(":")
        try:
            numbers = [float(part) for part in parts]
        except ValueError:
            return np.nan
        if len(numbers) == 2:
            minutes, seconds = numbers
            return minutes * 60 + seconds
        if len(numbers) == 3:
            hours, minutes, seconds = numbers
            return hours * 3600 + minutes * 60 + seconds
        return np.nan

    return series.apply(convert_one)


def load_cosmed_file(file_path: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load a messy COSMED file after automatically detecting the data table."""
    detection = detect_cosmed_header(file_path)
    df = _read_with_header(file_path, detection["header_row"])
    df = clean_column_names(df)
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all").reset_index(drop=True)

    for col in df.columns:
        if col != "t" and not col.lower().endswith("marker") and col not in {"Phase", "Marker"}:
            numeric = pd.to_numeric(df[col], errors="coerce")
            if numeric.notna().sum() >= max(1, int(df[col].notna().sum() * 0.5)):
                df[col] = numeric

    if "t" in df.columns:
        df["t_seconds"] = convert_time_to_seconds(df["t"])

    detection["columns"] = list(df.columns)
    return df, detection


def detect_available_variables(df: pd.DataFrame) -> list[str]:
    """Return the beginner-friendly list of variables present in the file."""
    lower_to_original = {col.lower(): col for col in df.columns}
    available = []
    for variable in PREFERRED_VARIABLES:
        if variable.lower() in lower_to_original:
            available.append(lower_to_original[variable.lower()])
    return available


def resample_data(df: pd.DataFrame, time_col: str, rate: str) -> pd.DataFrame:
    """Average numeric columns into selected time bins."""
    if rate == "raw/original" or time_col not in df.columns:
        return df.copy()
    seconds = int(rate.split()[0])
    working = df.copy()
    working["_time_bin"] = (working[time_col] // seconds) * seconds
    numeric_cols = working.select_dtypes(include="number").columns.tolist()
    text_cols = [col for col in working.columns if col not in numeric_cols and col != "_time_bin"]

    numeric = working.groupby("_time_bin", as_index=False)[numeric_cols].mean()
    if time_col in numeric.columns:
        numeric[time_col] = numeric["_time_bin"]
    else:
        numeric.insert(0, time_col, numeric["_time_bin"])

    for col in text_cols:
        first_values = working.groupby("_time_bin")[col].first().reset_index(drop=True)
        numeric[col] = first_values
    return numeric.drop(columns=["_time_bin"], errors="ignore")


def smooth_data(df: pd.DataFrame, columns: list[str], method: str) -> pd.DataFrame:
    """Apply a rolling mean to selected numeric columns."""
    smoothed = df.copy()
    if method == "none":
        return smoothed
    window = int(method.split()[-2])
    for col in columns:
        if col in smoothed.columns and pd.api.types.is_numeric_dtype(smoothed[col]):
            smoothed[col] = smoothed[col].rolling(window=window, min_periods=1, center=True).mean()
    return smoothed


def parse_manual_markers(text: str) -> pd.DataFrame:
    """Parse marker lines such as 'Baseline start, 00:30'."""
    rows = []
    for line in text.splitlines():
        if not line.strip() or "," not in line:
            continue
        label, time_value = line.split(",", 1)
        seconds = convert_time_to_seconds(pd.Series([time_value.strip()])).iloc[0]
        rows.append({"label": label.strip(), "time": time_value.strip(), "seconds": seconds})
    return pd.DataFrame(rows)


def create_epochs_from_markers(markers: pd.DataFrame) -> list[dict[str, Any]]:
    """Turn start/end marker pairs into analysis epochs."""
    if markers.empty:
        return []
    epochs = []
    starts: dict[str, float] = {}
    for _, row in markers.sort_values("seconds").iterrows():
        label = str(row["label"]).strip()
        lower = label.lower()
        seconds = float(row["seconds"])
        if lower.endswith(" start"):
            starts[label[:-6].strip()] = seconds
        elif lower.endswith(" end"):
            name = label[:-4].strip()
            if name in starts:
                epochs.append({"epoch": name, "start": starts[name], "end": seconds})
        else:
            epochs.append({"epoch": label, "start": seconds, "end": np.nan})
    return epochs


def calculate_summary_stats(df: pd.DataFrame, selected_columns: list[str]) -> pd.DataFrame:
    """Calculate simple descriptive statistics for selected variables."""
    rows = []
    for col in selected_columns:
        if col not in df.columns:
            rows.append({"variable": col, "issue": "missing selected variable"})
            continue
        numeric = pd.to_numeric(df[col], errors="coerce")
        rows.append({
            "variable": col,
            "mean": numeric.mean(),
            "median": numeric.median(),
            "min": numeric.min(),
            "max": numeric.max(),
            "standard deviation": numeric.std(),
            "number of valid points": int(numeric.notna().sum()),
            "number of missing points": int(numeric.isna().sum()),
        })
    return pd.DataFrame(rows)


def calculate_epoch_summary(
    df: pd.DataFrame,
    selected_columns: list[str],
    epochs: list[dict[str, Any]],
    time_col: str = "t_seconds",
) -> pd.DataFrame:
    """Calculate averages inside each manually defined epoch."""
    if not epochs or time_col not in df.columns:
        return pd.DataFrame()
    rows = []
    for epoch in epochs:
        start = epoch["start"]
        end = epoch["end"]
        if pd.isna(end):
            mask = df[time_col] >= start
        else:
            mask = (df[time_col] >= start) & (df[time_col] <= end)
        subset = df.loc[mask]
        row = {
            "epoch": epoch["epoch"],
            "start_seconds": start,
            "end_seconds": end,
            "rows": len(subset),
        }
        for col in selected_columns:
            if col in subset.columns:
                row[f"{col}_mean"] = pd.to_numeric(subset[col], errors="coerce").mean()
        rows.append(row)
    return pd.DataFrame(rows)


def _robust_spike_flags(series: pd.Series, threshold: float = 4.0) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    diff = numeric.diff().abs()
    median = diff.median()
    mad = (diff - median).abs().median()
    if pd.isna(mad) or mad == 0:
        z = (diff - diff.mean()) / diff.std(ddof=0)
        return z.abs().fillna(0) > threshold
    modified_z = 0.6745 * (diff - median) / mad
    return modified_z.abs().fillna(0) > threshold


def flag_possible_speaking(df: pd.DataFrame) -> pd.Series:
    """Flag patterns consistent with possible speaking, not definite speaking."""
    flags = pd.Series(False, index=df.index)
    if "Rf" in df.columns:
        rf = pd.to_numeric(df["Rf"], errors="coerce")
        flags |= (rf > 45) | _robust_spike_flags(rf)
    if "VE" in df.columns:
        ve = pd.to_numeric(df["VE"], errors="coerce")
        flags |= _robust_spike_flags(ve)
    if "VT" in df.columns:
        vt = pd.to_numeric(df["VT"], errors="coerce")
        flags |= _robust_spike_flags(vt)
    if "VO2" in df.columns and "VCO2" in df.columns:
        flags |= _robust_spike_flags(df["VO2"]) & _robust_spike_flags(df["VCO2"])
    return flags.fillna(False)


def flag_possible_movement(df: pd.DataFrame) -> pd.Series:
    """Flag patterns consistent with possible movement, not definite movement."""
    flags = pd.Series(False, index=df.index)
    jump_count = pd.Series(0, index=df.index, dtype=int)
    for col in ["GPS Speed", "VE", "Rf", "VT"]:
        if col in df.columns:
            col_flags = _robust_spike_flags(df[col])
            flags |= col_flags
            jump_count += col_flags.astype(int)
    flags |= jump_count >= 2
    for col in ["Marker", "Phase"]:
        if col in df.columns:
            text = df[col].astype(str).str.lower()
            flags |= text.str.contains("movement|move|walk|run|motion", regex=True, na=False)
    return flags.fillna(False)


def run_qc_checks(
    df: pd.DataFrame,
    selected_columns: list[str],
    flag_speaking: bool = True,
    flag_movement: bool = True,
    flag_missing: bool = True,
    flag_jumps: bool = True,
    flag_impossible: bool = True,
) -> pd.DataFrame:
    """Create a row-level QC report for selected variables."""
    rows = []
    if "t_seconds" not in df.columns and "t" not in df.columns:
        rows.append({"row": None, "variable": "t", "issue": "missing time column", "severity": "warning"})

    for col in selected_columns:
        if col not in df.columns:
            rows.append({"row": None, "variable": col, "issue": "missing selected variable", "severity": "warning"})
            continue

        numeric = pd.to_numeric(df[col], errors="coerce")
        nonnumeric = df[col].notna() & numeric.isna()
        for row_index in df.index[nonnumeric]:
            rows.append({"row": int(row_index), "variable": col, "issue": "nonnumeric value", "severity": "warning"})

        if flag_missing:
            for row_index in df.index[df[col].isna()]:
                rows.append({"row": int(row_index), "variable": col, "issue": "missing value", "severity": "warning"})

        if flag_impossible and col in POSITIVE_PHYSIOLOGY_COLUMNS:
            for row_index in df.index[numeric < 0]:
                rows.append({"row": int(row_index), "variable": col, "issue": "impossible negative value", "severity": "warning"})

        if flag_impossible and col == "RQ":
            for row_index in df.index[(numeric < 0.5) | (numeric > 1.5)]:
                rows.append({"row": int(row_index), "variable": col, "issue": "RQ outside broad possible range", "severity": "warning"})

        if flag_jumps and pd.api.types.is_numeric_dtype(numeric):
            for row_index in df.index[_robust_spike_flags(numeric)]:
                rows.append({"row": int(row_index), "variable": col, "issue": "sudden jump", "severity": "review"})

    if flag_speaking:
        for row_index in df.index[flag_possible_speaking(df)]:
            rows.append({"row": int(row_index), "variable": "multiple", "issue": "possible speaking artifact", "severity": "review"})

    if flag_movement:
        for row_index in df.index[flag_possible_movement(df)]:
            rows.append({"row": int(row_index), "variable": "multiple", "issue": "possible movement artifact", "severity": "review"})

    return pd.DataFrame(rows, columns=["row", "variable", "issue", "severity"])


def plot_selected_variables(
    df: pd.DataFrame,
    selected_columns: list[str],
    epochs: list[dict[str, Any]] | None,
    qc_flags: pd.DataFrame | None,
    time_col: str = "t_seconds",
    output_path: str | Path | None = None,
) -> plt.Figure:
    """Plot selected variables over time with optional epoch shading and QC markers."""
    numeric_columns = [
        col for col in selected_columns
        if col in df.columns and pd.api.types.is_numeric_dtype(pd.to_numeric(df[col], errors="coerce"))
    ]
    if not numeric_columns:
        numeric_columns = [col for col in df.select_dtypes(include="number").columns if col != time_col][:1]

    fig, axes = plt.subplots(len(numeric_columns), 1, figsize=(10, max(3, 2.6 * len(numeric_columns))), sharex=True)
    if len(numeric_columns) == 1:
        axes = [axes]

    x = df[time_col] if time_col in df.columns else pd.Series(df.index, index=df.index)
    for ax, col in zip(axes, numeric_columns):
        y = pd.to_numeric(df[col], errors="coerce")
        ax.plot(x, y, linewidth=1.6, label=col)
        ax.set_ylabel(col)
        ax.grid(True, alpha=0.25)

        if epochs:
            for epoch in epochs:
                start = epoch["start"]
                end = epoch["end"] if not pd.isna(epoch["end"]) else x.max()
                ax.axvspan(start, end, alpha=0.12)
                ax.text(start, ax.get_ylim()[1], epoch["epoch"], fontsize=8, va="top")

        if qc_flags is not None and not qc_flags.empty:
            rows = qc_flags.dropna(subset=["row"])["row"].astype(int).unique()
            rows = [row for row in rows if row in df.index]
            if rows:
                ax.scatter(x.loc[rows], y.loc[rows], color="red", s=20, zorder=5, label="QC flag")
        ax.legend(loc="best")

    axes[-1].set_xlabel("Time (seconds)" if time_col in df.columns else "Row")
    fig.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=160, bbox_inches="tight")
    return fig


def export_outputs(
    df: pd.DataFrame,
    summary: pd.DataFrame,
    epoch_summary: pd.DataFrame,
    qc_report: pd.DataFrame,
    manifest: dict[str, Any],
    output_dir: str | Path = "outputs",
) -> list[str]:
    """Export the cleaned data, summaries, QC report, plot manifest, and manifest."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    files = {
        "cleaned_data": output_path / "cleaned_cosmed_data.csv",
        "summary_statistics": output_path / "summary_statistics.xlsx",
        "epoch_summary": output_path / "epoch_summary.xlsx",
        "qc_report": output_path / "qc_report.csv",
        "manifest": output_path / "manifest.yaml",
    }
    df.to_csv(files["cleaned_data"], index=False)
    summary.to_excel(files["summary_statistics"], index=False)
    epoch_summary.to_excel(files["epoch_summary"], index=False)
    qc_report.to_csv(files["qc_report"], index=False)

    manifest = dict(manifest)
    manifest["analysis date/time"] = manifest.get("analysis date/time", datetime.now().isoformat(timespec="seconds"))
    manifest["outputs created"] = [str(path) for path in files.values()] + [str(output_path / "cosmed_plot.png")]
    with open(files["manifest"], "w", encoding="utf-8") as handle:
        for key, value in manifest.items():
            handle.write(f"{key}: {repr(value)}\n")

    return manifest["outputs created"]

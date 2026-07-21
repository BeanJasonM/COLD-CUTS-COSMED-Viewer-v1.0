"""Beginner-friendly helpers for COLD-CUTS COSMED Viewer v1.0."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
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


def _read_raw_file(file_path: str | Path, nrows: int | None = None, sheet_name: str | int = 0) -> pd.DataFrame:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, header=None, nrows=nrows, engine="openpyxl", sheet_name=sheet_name)
    if suffix == ".csv":
        return pd.read_csv(path, header=None, nrows=nrows)
    if suffix == ".tsv":
        return pd.read_csv(path, header=None, sep="\t", nrows=nrows)
    if suffix == ".txt":
        return pd.read_csv(path, header=None, sep=None, engine="python", nrows=nrows)
    raise ValueError(f"Unsupported file type: {suffix}. Use .xlsx, .csv, .txt, or .tsv.")


def _read_with_header(file_path: str | Path, header_row: int, sheet_name: str | int = 0) -> pd.DataFrame:
    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, header=header_row, engine="openpyxl", sheet_name=sheet_name)
    if suffix == ".csv":
        return pd.read_csv(path, header=header_row)
    if suffix == ".tsv":
        return pd.read_csv(path, header=header_row, sep="\t")
    if suffix == ".txt":
        return pd.read_csv(path, header=header_row, sep=None, engine="python")
    raise ValueError(f"Unsupported file type: {suffix}. Use .xlsx, .csv, .txt, or .tsv.")


def detect_cosmed_header(file_path: str | Path, sheet_name: str | int = 0) -> dict[str, Any]:
    """Find the row that looks most like the real COSMED data header."""
    preview = _read_raw_file(file_path, nrows=50, sheet_name=sheet_name)
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


def load_cosmed_file(
    file_path: str | Path,
    sheet_name: str | int = 0,
    header_override: int | None = None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load a messy COSMED file after automatically detecting the data table."""
    detection = detect_cosmed_header(file_path, sheet_name=sheet_name)
    if header_override is not None:
        detection["header_row"] = int(header_override)
        detection["confidence"] = np.nan
        detection["matched_headers"] = ["manual override"]
    df = _read_with_header(file_path, detection["header_row"], sheet_name=sheet_name)
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


def resample_data_with_method(
    df: pd.DataFrame,
    time_col: str,
    interval_seconds: int | None,
    method: str = "Mean",
) -> pd.DataFrame:
    """Resample numeric data into time bins with a chosen aggregation method."""
    if not interval_seconds or interval_seconds <= 0 or time_col not in df.columns:
        return df.copy()

    working = df.copy()
    working["_time_bin"] = (working[time_col] // interval_seconds) * interval_seconds
    numeric_cols = [col for col in working.select_dtypes(include="number").columns if col != "_time_bin"]
    text_cols = [col for col in working.columns if col not in numeric_cols and col != "_time_bin"]
    grouped = working.groupby("_time_bin", as_index=False)
    method_map = {
        "Mean": "mean",
        "Median": "median",
        "Minimum": "min",
        "Maximum": "max",
        "First": "first",
        "Last": "last",
    }
    aggregation = method_map.get(method, "mean")
    numeric = getattr(grouped[numeric_cols], aggregation)()

    if time_col in numeric.columns:
        numeric[time_col] = numeric["_time_bin"]
    else:
        numeric.insert(0, time_col, numeric["_time_bin"])

    for col in text_cols:
        text_values = working.groupby("_time_bin")[col].first().reset_index(drop=True)
        numeric[col] = text_values

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


def smooth_data_advanced(
    df: pd.DataFrame,
    columns: list[str],
    method: str,
    window: int,
) -> pd.DataFrame:
    """Smooth selected columns without changing the original input DataFrame."""
    smoothed = df.copy()
    if method == "None" or window <= 1:
        return smoothed
    window = max(2, int(window))

    for col in columns:
        if col not in smoothed.columns:
            continue
        numeric = pd.to_numeric(smoothed[col], errors="coerce")
        if numeric.notna().sum() == 0:
            continue
        if method == "Rolling mean":
            smoothed[col] = numeric.rolling(window=window, min_periods=1, center=True).mean()
        elif method == "Rolling median":
            smoothed[col] = numeric.rolling(window=window, min_periods=1, center=True).median()
        elif method == "Exponential moving average":
            smoothed[col] = numeric.ewm(span=window, adjust=False, min_periods=1).mean()
        elif method == "Savitzky-Golay":
            try:
                from scipy.signal import savgol_filter
            except ImportError:
                continue
            valid = numeric.interpolate(limit_direction="both")
            savgol_window = window if window % 2 == 1 else window + 1
            if len(valid) >= savgol_window and savgol_window >= 5:
                smoothed[col] = savgol_filter(valid, window_length=savgol_window, polyorder=2)
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


def _safe_slope(x: pd.Series, y: pd.Series) -> float:
    valid = x.notna() & y.notna()
    if valid.sum() < 2 or x.loc[valid].nunique() < 2:
        return np.nan
    return float(np.polyfit(x.loc[valid], y.loc[valid], 1)[0])


def _safe_auc(x: pd.Series, y: pd.Series) -> float:
    valid = x.notna() & y.notna()
    if valid.sum() < 2:
        return np.nan
    return float(np.trapz(y.loc[valid], x.loc[valid]))


def calculate_enhanced_summary(
    df: pd.DataFrame,
    selected_columns: list[str],
    time_col: str = "t_seconds",
) -> pd.DataFrame:
    """Calculate a richer variable-level analytics table."""
    x = pd.to_numeric(df[time_col], errors="coerce") if time_col in df.columns else pd.Series(df.index, index=df.index)
    rows = []
    for col in selected_columns:
        if col not in df.columns:
            rows.append({"Variable": col, "Issue": "Missing selected variable"})
            continue
        y = pd.to_numeric(df[col], errors="coerce")
        valid = y.dropna()
        missing_count = int(y.isna().sum())
        valid_count = int(valid.shape[0])
        if valid_count == 0:
            rows.append({
                "Variable": col,
                "Valid": 0,
                "Missing": missing_count,
                "Missing %": round((missing_count / len(y) * 100), 2) if len(y) else np.nan,
                "Issue": "No valid numeric data",
            })
            continue

        first_index = valid.index[0]
        last_index = valid.index[-1]
        first_value = float(valid.iloc[0])
        last_value = float(valid.iloc[-1])
        absolute_change = last_value - first_value
        percent_change = np.nan if first_value == 0 or pd.isna(first_value) else (absolute_change / first_value) * 100
        peak_index = y.idxmax()
        min_index = y.idxmin()

        rows.append({
            "Variable": col,
            "Valid": valid_count,
            "Missing": missing_count,
            "Missing %": round((missing_count / len(y) * 100), 2) if len(y) else np.nan,
            "Mean": valid.mean(),
            "Median": valid.median(),
            "SD": valid.std(),
            "Minimum": valid.min(),
            "Maximum": valid.max(),
            "IQR": valid.quantile(0.75) - valid.quantile(0.25),
            "First valid": first_value,
            "Last valid": last_value,
            "Absolute change": absolute_change,
            "Percent change": percent_change,
            "Linear slope": _safe_slope(x, y),
            "Area under curve": _safe_auc(x, y),
            "Peak value": y.loc[peak_index],
            "Time of peak": x.loc[peak_index] if peak_index in x.index else np.nan,
            "Minimum value": y.loc[min_index],
            "Time of minimum": x.loc[min_index] if min_index in x.index else np.nan,
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


def calculate_enhanced_epoch_summary(
    df: pd.DataFrame,
    selected_columns: list[str],
    epochs: list[dict[str, Any]],
    qc_report: pd.DataFrame | None = None,
    time_col: str = "t_seconds",
    baseline_name: str = "Baseline",
) -> pd.DataFrame:
    """Calculate phase/epoch summaries with changes, QC counts, and usable percentages."""
    if not epochs or time_col not in df.columns:
        return pd.DataFrame()

    x_all = pd.to_numeric(df[time_col], errors="coerce")
    qc_rows = set()
    if qc_report is not None and not qc_report.empty and "row" in qc_report.columns:
        qc_rows = set(qc_report.dropna(subset=["row"])["row"].astype(int).tolist())

    baseline_means: dict[str, float] = {}
    rows = []
    for epoch in epochs:
        start = epoch["start"]
        end = epoch["end"]
        mask = x_all >= start if pd.isna(end) else (x_all >= start) & (x_all <= end)
        subset = df.loc[mask]
        x = x_all.loc[subset.index]
        flagged_count = sum(1 for idx in subset.index if int(idx) in qc_rows)
        usable_percentage = 100.0 if len(subset) == 0 else ((len(subset) - flagged_count) / len(subset)) * 100

        for col in selected_columns:
            if col not in subset.columns:
                continue
            y = pd.to_numeric(subset[col], errors="coerce")
            valid = y.dropna()
            if valid.empty:
                continue
            epoch_name = str(epoch["epoch"])
            mean_value = valid.mean()
            if epoch_name.lower() == baseline_name.lower():
                baseline_means[col] = mean_value
            baseline = baseline_means.get(col, np.nan)
            absolute_from_baseline = mean_value - baseline if pd.notna(baseline) else np.nan
            percent_from_baseline = (
                np.nan
                if pd.isna(baseline) or baseline == 0
                else absolute_from_baseline / baseline * 100
            )
            rows.append({
                "Phase": epoch_name,
                "Variable": col,
                "Start": start,
                "End": end,
                "Rows": len(subset),
                "Mean": mean_value,
                "Median": valid.median(),
                "SD": valid.std(),
                "Minimum": valid.min(),
                "Maximum": valid.max(),
                "Absolute change from baseline": absolute_from_baseline,
                "Percent change from baseline": percent_from_baseline,
                "Slope": _safe_slope(x, y),
                "Area under curve": _safe_auc(x, y),
                "QC flagged observations": flagged_count,
                "Usable %": usable_percentage,
            })
    return pd.DataFrame(rows)


def qc_overview(qc_report: pd.DataFrame, total_rows: int) -> pd.DataFrame:
    """Summarize QC flags by issue category."""
    if qc_report.empty:
        return pd.DataFrame(columns=["Issue", "Flags", "Rows affected %"])
    grouped = qc_report.groupby("issue", dropna=False).size().reset_index(name="Flags")
    grouped = grouped.rename(columns={"issue": "Issue"})
    grouped["Rows affected %"] = grouped["Flags"].apply(
        lambda value: round((value / total_rows * 100), 2) if total_rows else 0
    )
    return grouped.sort_values("Flags", ascending=False)


def missingness_by_variable(df: pd.DataFrame, selected_columns: list[str]) -> pd.DataFrame:
    """Calculate missingness percentage for selected variables."""
    rows = []
    for col in selected_columns:
        if col in df.columns:
            rows.append({
                "Variable": col,
                "Missing": int(df[col].isna().sum()),
                "Missing %": round((df[col].isna().mean() * 100), 2) if len(df) else 0,
            })
    return pd.DataFrame(rows)


def dataframe_to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Create an in-memory Excel workbook from one or more DataFrames."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df in sheets.items():
            safe_name = sheet_name[:31] or "Sheet1"
            df.to_excel(writer, index=False, sheet_name=safe_name)
    return buffer.getvalue()


def detect_biopac_txt(file_path: str | Path) -> dict[str, Any]:
    """Detect basic BIOPAC/Laser Doppler text-export structure."""
    path = Path(file_path)
    lines = path.read_text(errors="ignore").splitlines()
    numeric_start = 0
    delimiter = "\t"
    found_numeric = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        for candidate in ["\t", ",", ";", " "]:
            parts = [part for part in stripped.split(candidate) if part != ""]
            numeric_count = sum(pd.to_numeric(pd.Series(parts), errors="coerce").notna())
            if len(parts) >= 2 and numeric_count >= 2:
                numeric_start = index
                delimiter = candidate
                found_numeric = True
                break
        if found_numeric:
            break

    metadata_lines = lines[:numeric_start]
    header_candidates = [line for line in metadata_lines[-5:] if line.strip()]
    channel_names: list[str] = []
    if header_candidates:
        possible_header = header_candidates[-1]
        parts = [part.strip() for part in possible_header.replace(",", "\t").split("\t") if part.strip()]
        if len(parts) >= 2 and not all(pd.to_numeric(pd.Series(parts), errors="coerce").notna()):
            channel_names = parts

    sample_rate = np.nan
    for line in metadata_lines:
        lower = line.lower()
        if "sample" in lower and ("rate" in lower or "freq" in lower):
            numbers = pd.Series(line.replace("=", " ").replace(":", " ").split()).str.extract(r"(\d+\.?\d*)")[0].dropna()
            if not numbers.empty:
                sample_rate = float(numbers.iloc[0])
                break

    return {
        "numeric_start": numeric_start,
        "delimiter": delimiter,
        "metadata_lines": metadata_lines,
        "sample_rate": sample_rate,
        "channel_names": channel_names,
    }


def load_biopac_txt(file_path: str | Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Load a BIOPAC/Laser Doppler text export by locating the first numeric row."""
    detection = detect_biopac_txt(file_path)
    delimiter = detection["delimiter"]
    sep = r"\s+" if delimiter == " " else delimiter
    df = pd.read_csv(file_path, sep=sep, header=None, skiprows=detection["numeric_start"], engine="python")
    df = df.dropna(axis=1, how="all").dropna(axis=0, how="all").reset_index(drop=True)

    channel_names = detection["channel_names"]
    if len(channel_names) == len(df.columns):
        df.columns = channel_names
    else:
        df.columns = [f"Channel {index + 1}" for index in range(len(df.columns))]

    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    sample_rate = detection["sample_rate"]
    if pd.notna(sample_rate) and sample_rate > 0:
        df.insert(0, "t_seconds", np.arange(len(df)) / sample_rate)
    else:
        df.insert(0, "t_seconds", np.arange(len(df)))

    detection["columns"] = list(df.columns)
    detection["total_samples"] = len(df)
    detection["duration_seconds"] = float(df["t_seconds"].max()) if len(df) else 0.0
    detection["missing_values"] = int(df.isna().sum().sum())
    detection["duplicate_timestamps"] = int(df["t_seconds"].duplicated().sum())
    detection["memory_usage_mb"] = float(df.memory_usage(deep=True).sum() / 1_000_000)
    return df, detection


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

# COLD-CUTS Viewer v1.0

A beginner-friendly Python app for exploring COSMED K5 Excel/CSV exports.

The easiest version is the Streamlit app in `app.py`. It gives you simple buttons, upload controls, sidebar settings, tabs, tables, interactive plots, and downloads. The Jupyter notebook is still included as an optional learning version.

## Start fresh in a brand-new GitHub repo

1. Go to [github.com](https://github.com) and sign in.
2. Click **New repository**.
3. Name it something like `cold-cuts-cosmed-viewer`.
4. Choose **Public** or **Private**.
5. Check **Add a README file** if GitHub asks.
6. Click **Create repository**.
7. Click the green **Code** button.
8. Open the **Codespaces** tab.
9. Click **Create codespace on main**.

After Codespaces opens, upload or add these project files and folders:

- `README.md`
- `requirements.txt`
- `cosmed_utils.py`
- `app.py`
- `notebooks/COSMED_Viewer_v1.ipynb`
- `examples/synthetic_cosmed_export.xlsx`
- `outputs/`

If you are starting from this folder on your computer, you can also upload the files through the GitHub web page by clicking **Add file** and then **Upload files**.

## Quick start: Streamlit button app

1. Open this folder in GitHub Codespaces.
2. Install the requirements:

   ```bash
   pip install -r requirements.txt
   ```

3. Start the app:

   ```bash
   python -m streamlit run app.py
   ```

4. Codespaces will show a popup about port `8501`. Click **Open in Browser**.
5. In the app, keep **Use synthetic demo file** on for the first test.
6. Click **Run Analysis**.

The results show inside the app tabs. You do not need to open CSV or Excel output files.

## Updating an existing Streamlit Cloud app

If your app is already deployed, upload or replace these files in GitHub:

- `app.py`
- `cosmed_utils.py`
- `requirements.txt`
- `README.md`
- `examples/synthetic_cosmed_export.xlsx`

Then commit the changes to the `main` branch. Streamlit Cloud usually redeploys automatically after GitHub updates.

If Streamlit asks for the main file path, use:

```text
app.py
```

## Optional: Jupyter notebook version

If you want to see the notebook version:

```bash
jupyter lab
```

Then open:

`notebooks/COSMED_Viewer_v1.ipynb`

In Codespaces, Jupyter may open inside VS Code. If it asks for a kernel, choose the Python environment where you installed `requirements.txt`.

## Loading a COSMED file

The app gives you two beginner-friendly options:

- Use the included synthetic demo file.
- Upload a real COSMED file.

Supported file types:

- `.xlsx`
- `.csv`
- `.txt`
- `.tsv`

The app also has a second data source mode for basic BIOPAC / Laser Doppler `.txt` exports. Choose **BIOPAC / Laser Doppler (.txt)** from the **Data Source** dropdown, upload a `.txt` file, and the app will try to detect the first numeric data row, sample rate, channels, duration, missing values, duplicate timestamps, and memory use.

COSMED exports often have metadata above the real data table. The app searches the first 50 rows for known COSMED column names such as `t`, `VO2`, `VCO2`, `VE`, `Rf`, `VT`, `RQ`, `Phase`, and `Marker`. It then reports the detected header row and a confidence score.

If confidence is low, the app shows a warning and displays the first 20 rows so you can inspect the file manually.

## Selecting variables

After clicking **Run Analysis**, choose variables from the multi-select box. Common supported variables include:

- `VO2`
- `VCO2`
- `VE`
- `Rf`
- `VT`
- `RQ`
- `VO2/kg`
- `METS`
- `FeO2`
- `FeCO2`
- `PetO2`
- `PetCO2`
- `HR`, if present
- `GPS Speed`, if present
- `Phase`, if present
- `Marker`, if present

## Filtering by time

Use the start and end time boxes to limit the analysis window.

You can type times as seconds, `mm:ss`, or `hh:mm:ss`.

Examples:

- `30`
- `00:30`
- `02:30`
- `00:02:30`

## Event markers and epochs

You can type manual event markers in the text area.

Example:

```text
Baseline start, 00:30
Baseline end, 02:30
Movement start, 03:00
Movement end, 04:00
Recovery start, 04:30
```

The notebook pairs `start` and `end` markers with the same label to create epochs. It then calculates average values for each epoch.

If the file includes `Phase` or `Marker` columns, the notebook also lists the unique values it finds.

## Results in the app

Click **Run Analysis** to show these results directly inside the app:

- Cleaned preview table after header detection, time conversion, filtering, resampling, and smoothing.
- Enhanced variable summary with valid count, missing count, missing percentage, mean, median, standard deviation, min, max, IQR, first/last values, absolute change, percent change, slope, area under the curve, peak value/time, and minimum value/time.
- Phase summaries with mean, median, standard deviation, min, max, baseline-relative change, slope, area under the curve, QC count, and usable percentage.
- Interactive time-series plot with zoom/range tools, event lines, and QC markers.
- Phase comparison plot.
- Distribution plots.
- Relationship/scatterplot analysis with Pearson and Spearman correlations.
- QC overview with flag categories and missingness by variable.

The normal beginner workflow does not require opening separate CSV or Excel files. The results appear in the app tabs.

Downloads are available from the **Downloads** tab when you want them:

- Filtered data CSV
- Filtered data Excel
- Variable summary CSV
- Phase summary CSV
- QC report CSV
- Event marker CSV
- Analysis manifest TXT

## Possible speaking artifact

The notebook can flag patterns that may be consistent with speaking during breath-by-breath testing, such as abrupt `Rf`, `VE`, `VT`, `VO2`, or `VCO2` changes.

Important: this is only a possible artifact flag. It does not prove that speaking happened.

## Possible movement artifact

The notebook can flag patterns that may be consistent with movement, such as abrupt changes in `GPS Speed`, `VE`, `Rf`, or `VT`, multiple simultaneous jumps, or movement-related text in `Phase` or `Marker`.

Important: this is only a possible artifact flag. It does not prove that movement happened.

## Example data

The `examples/` folder includes a synthetic COSMED-style Excel file created for testing. It does not contain participant information, PHI, or PII.

Use it first if you want to confirm the notebook works before loading a real export.

## Limitations

- This is a simple notebook app, not a validated clinical or research production pipeline.
- Artifact flags are rule-based screening prompts, not definitive labels.
- COSMED export formats can vary; very unusual files may need manual inspection.
- Always review outputs before using them for reports, publications, or decisions.

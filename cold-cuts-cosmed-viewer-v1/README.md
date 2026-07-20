# COLD-CUTS COSMED Viewer v1.0

A beginner-friendly Jupyter notebook mini-app for exploring COSMED K5 Excel/CSV exports.

The app helps you load a messy COSMED export, detect the real data table, choose variables, filter by time, define simple event epochs, flag possible artifacts, make plots, and view the results directly in the notebook app.

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
- `notebooks/COSMED_Viewer_v1.ipynb`
- `examples/synthetic_cosmed_export.xlsx`
- `outputs/`

If you are starting from this folder on your computer, you can also upload the files through the GitHub web page by clicking **Add file** and then **Upload files**.

## Quick start in GitHub Codespaces

1. Open this folder in GitHub Codespaces.
2. Install the requirements:

   ```bash
   pip install -r requirements.txt
   ```

3. Start Jupyter:

   ```bash
   jupyter notebook
   ```

4. Open:

   `notebooks/COSMED_Viewer_v1.ipynb`

5. Run the notebook from top to bottom.

In Codespaces, Jupyter may open inside VS Code. If it asks for a kernel, choose the Python environment where you installed `requirements.txt`.

## Loading a COSMED file

The notebook gives you two beginner-friendly options:

- Paste a file path into the file path box.
- Upload a file using the upload widget.

Supported file types:

- `.xlsx`
- `.csv`
- `.txt`
- `.tsv`

COSMED exports often have metadata above the real data table. The notebook searches the first 50 rows for known COSMED column names such as `t`, `VO2`, `VCO2`, `VE`, `Rf`, `VT`, `RQ`, `Phase`, and `Marker`. It then reports the detected header row and a confidence score.

If confidence is low, the notebook shows a warning and prints the first 20 rows so you can inspect the file manually.

## Selecting variables

After loading a file, choose variables from the multi-select box. Common supported variables include:

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

Click **Run Analysis** to show these results directly inside the notebook:

- Cleaned preview table after header detection, time conversion, filtering, resampling, and smoothing.
- Summary statistics with mean, median, min, max, standard deviation, valid count, and missing count.
- Epoch summary with averages for each manual epoch.
- QC report with row-level warnings and review flags.
- Plot of selected variables over time.

The normal beginner workflow does not require opening separate CSV or Excel files. The results appear in the app output area below the button.

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

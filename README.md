# COLD-CUTS Streamlit Viewer

A beginner-friendly Streamlit app for COSMED K5 files and basic BIOPAC / Laser Doppler text files.

## Files You Need

Your GitHub repo should contain these files at the top level:

```text
app.py
cosmed_utils.py
requirements.txt
README.md
.streamlit/config.toml
examples/synthetic_cosmed_export.xlsx
examples/synthetic_biopac_laser_doppler.txt
```

`app.py` must be visible immediately when you open the repo. It should not be hidden inside another folder.

## Run Locally Or In Codespaces

Open a terminal in the repo and run:

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

If you are in GitHub Codespaces, click **Open in Browser** when it offers port `8501`.

## Deploy On Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io).
2. Click **Deploy a public app from GitHub**.
3. Choose your GitHub repo.
4. Use branch:

```text
main
```

5. Use main file path:

```text
app.py
```

6. Pick an app URL, for example:

```text
cold-cuts-cosmed-viewer
```

7. Click **Deploy**.

## First Test

When the app opens:

1. Leave **Use synthetic COSMED demo** on.
2. Click **Run Analysis**.
3. Confirm you see these tabs:

```text
Data Overview
Time Series
Phase Analysis
Relationships
Quality Control
Downloads
```

## Use Real Data

For COSMED:

1. Choose **COSMED K5 (.xlsx/.csv/.txt/.tsv)**.
2. Upload your COSMED export.
3. Click **Run Analysis**.

For BIOPAC / Laser Doppler:

1. Choose **BIOPAC / Laser Doppler (.txt)**.
2. Upload your `.txt` export.
3. Click **Run Analysis**.

## Notes

QC flags are review prompts only. They do not prove speaking, movement, sensor failure, disease, or any specific event.

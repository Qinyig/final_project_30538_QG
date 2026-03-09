# Money in Medicine: Structural and Geographic Concentration of Industry Payments (2023)

**Author:** Quinn Gan  
**Course:** 30538 Data Analytics and Visualization for Public Policy 
**GitHub Username:** Qinyig

---

## Project Overview

This project analyzes the 2023 CMS Open Payments dataset to examine how pharmaceutical and medical device industry payments are distributed across medical specialties, payment types, and geographic regions. By integrating CMS data with American Community Survey (ACS) socioeconomic indicators, the project investigates whether industry payments align with healthcare need or regional wealth.

**Research Questions:**
1. How are payments distributed across medical specialties and payment categories?
2. Which states exhibit the highest payment intensity per household?
3. Is there a relationship between state median household income and payment intensity?

---

## Streamlit Dashboard

**Live App:** [https://qgdashboard.streamlit.app/](https://qgdashboard.streamlit.app/)

The dashboard loads data automatically from Google Drive — no local setup required to view it.

---

## Repository Structure

```
final_project_30538_QG/
├── Final_project.qmd          # Main writeup and all static visualizations
├── environment.yml            # Conda environment specification
├── requirements.txt           # Pip requirements (used by Streamlit Cloud)
├── README.md
├── .gitignore
├── code/
│   ├── preprocessing.qmd      # Data downloading, cleaning, standardization
│   ├── plot1_specialty.qmd
│   ├── plot2_payment_type.qmd
│   ├── plot3_map.qmd
│   ├── plot4_wealth_alignment.qmd
│   └── plot5_lorenz.qmd
├── data/
│   ├── raw-data/              # Raw input data (see below)
│   └── derived-data/
│       └── acs_state_clean.csv  # Cleaned ACS state-level indicators (included)
└── streamlit-app/
    └── app.py                 # Streamlit dashboard source
```

---

## Data Sources

### 1. CMS Open Payments (2023)
- **Source:** [CMS Open Payments](https://openpaymentsdata.cms.gov)
- **Description:** General payments from pharmaceutical and medical device manufacturers to physicians and teaching hospitals
- **Note:** Raw file (`data/raw-data/open_payments_2023_national.csv`) and cleaned file (available at [https://drive.google.com/file/d/1h5VC-j6Q1SwLTChTP7PBJtrd6WsbHKo9/view?usp=drive_link]) are excluded from this repository due to file size (>100MB). The raw file is downloaded automatically via CMS API when running `code/preprocessing.qmd`.

### 2. American Community Survey (ACS, 2023)
- **Source:** [U.S. Census Bureau](https://data.census.gov)
- **Table:** ACSDP1Y2023.DP03
- **Description:** State-level median household income and total household counts
- **Access:** Must be manually downloaded and placed in `data/raw-data/ACSDP1Y2023.DP03-2026-02-27T224607.csv`
---

## How to Reproduce

### 1. Set up the environment

```bash
conda env create -f environment.yml
conda activate cms_analysis
```

### 2. Download ACS data

Download the ACS DP03 table from [data.census.gov](https://data.census.gov) and save it to:
```
data/raw-data/ACSDP1Y2023.DP03-2026-02-27T224607.csv
```

### 3. Run preprocessing

Run from the project root:
```bash
quarto render code/preprocessing.qmd
```

This will:
- Automatically download the CMS Open Payments data via API
- Clean and standardize both datasets
- Save outputs to `data/derived-data/`:
  - `cms_payments_clean.csv` — row-level cleaned CMS payments (gitignored)
  - `acs_state_clean.csv` — cleaned ACS state-level indicators

### 4. Render the main analysis

```bash
quarto render Final_project.qmd --to pdf
```

### 5. Launch the dashboard locally (optional)

```bash
streamlit run streamlit-app/app.py
```

Note: The live dashboard at [https://qgdashboard.streamlit.app/](https://qgdashboard.streamlit.app/) downloads the first 800,000 records of the cleaned CMS data automatically from Google Drive and does not require local setup.

---

## Notes

- `data/derived-data/cms_payments_clean.csv` is excluded from this repository (>1GB). Generate it by running `code/preprocessing.qmd`.
- Do not rename any downloaded files. File paths are defined relative to the project root.
- The preprocessing step requires an internet connection to download the CMS dataset via API.

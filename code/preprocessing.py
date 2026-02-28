import os
import requests
import pandas as pd
import numpy as np
from scipy import stats

# --- STEP 1. Path Configuration (Relative to project root) ---
RAW_DATA_DIR = "data/raw-data"
DERIVED_DATA_DIR = "data/derived-data"
CMS_RAW_PATH = os.path.join(RAW_DATA_DIR, "open_payments_2023_national.csv")
# Use relative path instead of /Users/quinn/...
ACS_RAW_PATH = os.path.join(RAW_DATA_DIR, "ACSDP1Y2023.DP03-2026-02-27T224607.csv")
FINAL_OUTPUT_PATH = os.path.join(DERIVED_DATA_DIR, "cms_acs_merged_2023.csv")

os.makedirs(RAW_DATA_DIR, exist_ok=True)
os.makedirs(DERIVED_DATA_DIR, exist_ok=True)

def run_preprocessing():
    # --- STEP 2. Load or Fetch CMS Data ---
    if os.path.exists(CMS_RAW_PATH):
        print("Loading CMS data from cache...")
        payments_df = pd.read_csv(CMS_RAW_PATH)
    else:
        print("Fetching CMS data from API...")
        url = "https://openpaymentsdata.cms.gov/api/1/metastore/schemas/dataset/items/fb3a65aa-c901-4a38-a813-b04b00dfa2a9"
        r = requests.get(url)
        r.raise_for_status()
        csv_url = r.json()["distribution"][0]["downloadURL"]

        # Specify columns for efficiency
        usecols = [
            "Covered_Recipient_Profile_ID", "Covered_Recipient_Specialty_1", 
            "Total_Amount_of_Payment_USDollars", "Date_of_Payment", 
            "Nature_of_Payment_or_Transfer_of_Value", "Recipient_State"
        ]

        print("Downloading chunks...")
        chunks = pd.read_csv(csv_url, usecols=usecols, chunksize=200_000, low_memory=False)
        payments_df = pd.concat(chunks, ignore_index=True)
        
        # Cache the raw data
        payments_df.to_csv(CMS_RAW_PATH, index=False)

    # --- STEP 3: CMS Data Cleaning ---
    print("Cleaning CMS data...")
    # Basic filtering
    payments_df = payments_df[payments_df["Total_Amount_of_Payment_USDollars"] > 0].copy()
    
    # Standardize column names
    payments_df.columns = payments_df.columns.str.lower()
    payments_df = payments_df.rename(columns={
        "nature_of_payment_or_transfer_of_value": "payment_type",
        "total_amount_of_payment_usdollars": "payment_amount",
        "recipient_state": "state",
        "covered_recipient_specialty_1": "specialty"
    })

    # Clean specialty names
    payments_df["specialty_clean"] = (
    payments_df["specialty"]
    .str.split("|")
    .str[-1]
    .str.strip()
    .fillna("Unknown")
)
    
    # Mapping for Nature of Payments (Cleaning up long descriptions)
    nature_map = {    
    "Compensation for services other than consulting, including serving as faculty or as a speaker at a venue other than a continuing education program": "Non-consulting professional services",
    "Consulting Fee": "Consulting",
    "Food and Beverage": "Food & Beverage",
    "Travel and Lodging": "Travel & Lodging",
    "Royalty or License": "Royalty / License",
    "Honoraria": "Honoraria",
    "Education": "Education",
    "Grant": "Grant",
    "Acquisitions": "Acquisitions",
    "Entertainment": "Entertainment",
    "Long term medical supply or device loan": "Device / Supply Loan"
    }

    # create a new column with the cleaned payment type categories
    payments_df["payment_type_clean"] = (
        payments_df["payment_type"]
        .map(nature_map)
        .fillna("Other")
    )
    payments_df["state"] = payments_df["state"].fillna("Unknown")

    # --- STEP 4: ACS Data Preparation ---
    print("Processing ACS Census data...")
    if not os.path.exists(ACS_RAW_PATH):
        raise FileNotFoundError(f"Missing ACS file at {ACS_RAW_PATH}. Please ensure it is in data/raw-data/")

    df_acs_raw = pd.read_csv(ACS_RAW_PATH).set_index('Label (Grouping)')
    
    # Transpose to get states as rows
    estimate_cols = [c for c in df_acs_raw.columns if "!!Estimate" in c]
    df_estimates = df_acs_raw[estimate_cols].T

    # Extract indicators
    income_lbl = [idx for idx in df_acs_raw.index if "Median household income (dollars)" in idx][0]
    hh_lbl = [idx for idx in df_acs_raw.index if "Total households" in idx][0]

    df_policy_acs = df_estimates[[income_lbl, hh_lbl]].copy()
    df_policy_acs.columns = ['median_income', 'total_households']

    # Convert to numeric
    for col in df_policy_acs.columns:
        df_policy_acs[col] = pd.to_numeric(df_policy_acs[col].astype(str).str.replace(',', ''), errors='coerce')

    # Map State Names to Abbreviations
    df_policy_acs.index = df_policy_acs.index.str.replace("!!Estimate", "")
    df_policy_acs = df_policy_acs.reset_index().rename(columns={'index': 'state_name'})
    
    state_to_abbr = {
        "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
        "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA",
        "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA",
        "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
        "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO",
        "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
        "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
        "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
        "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
        "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
        "District of Columbia": "DC"
    }
    df_policy_acs['state_abbr'] = df_policy_acs['state_name'].map(state_to_abbr)

    # --- STEP 5: Merge CMS & ACS ---
    print("Merging datasets...")
    state_summary = payments_df.groupby('state')['payment_amount'].sum().reset_index()
    map_data = pd.merge(state_summary, df_policy_acs, left_on='state', right_on='state_abbr', how='inner')
    map_data['payment_per_household'] = map_data['payment_amount'] / map_data['total_households']
    
    # Normalize
    map_data.to_csv("data/derived-data/cms_acs_state_summary.csv", index=False)

    # --- STEP 6: Save to Derived Data ---
    detail_data = payments_df.groupby(['state', 'specialty_clean', 'payment_type_clean'])['payment_amount'].sum().reset_index()
    detail_data.to_csv("data/derived-data/cms_payments_details.csv", index=False)
    print("Preprocessing complete! Saved state summary and detailed payment files.")

if __name__ == "__main__":
    run_preprocessing()
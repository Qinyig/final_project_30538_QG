import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
from vega_datasets import data

st.set_page_config(layout="wide", page_title="Healthcare Industry Payment Dashboard")

# --------------------------
# 1. Load Data
# --------------------------
@st.cache_data
def load_data():
    import gdown
    import os
    cms_path = "/tmp/cms_payments_clean.csv"
    if not os.path.exists(cms_path):
        gdown.download(
            f"https://drive.google.com/uc?id=1h5VC-j6Q1SwLTChTP7PBJtrd6WsbHKo9",
            cms_path,
            quiet=False
        )
    df_cms = pd.read_csv(cms_path)
    df_acs = pd.read_csv("data/derived-data/acs_state_clean.csv")

    # Compute specialty_grouped
    conditions = [
        df_cms['specialty_clean'] == 'Unknown',
        df_cms['specialty_clean'].str.contains('Orthopaedic|Orthopedic', case=False, na=False) &
            ~df_cms['specialty_clean'].str.contains('Orthodontic', case=False, na=False),
        df_cms['specialty_clean'].str.contains('Cardio|Heart', case=False, na=False),
        df_cms['specialty_clean'].str.contains('Oncology|Hematolog', case=False, na=False),
        df_cms['specialty_clean'].str.contains('Neurolog|Neurosurg|Neuroradio', case=False, na=False),
        df_cms['specialty_clean'].str.contains('Psychiatr|Mental Health', case=False, na=False),
        df_cms['specialty_clean'].str.contains('Internal Medicine|Family Medicine|Family Health|General Practice|Primary Care|Adult Medicine', case=False, na=False),
        df_cms['specialty_clean'].str.contains('Nurse|Physician Assistant', case=False, na=False),
        df_cms['specialty_clean'].str.contains('Dermatolog', case=False, na=False),
        df_cms['specialty_clean'].str.contains('Surgery|Surgeon', case=False, na=False),
    ]
    choices = [
        'Unknown (Researchers & Institutions)',
        'Orthopedics',
        'Cardiology',
        'Oncology & Hematology',
        'Neurology & Neurosurgery',
        'Psychiatry & Mental Health',
        'Internal Med & Primary Care',
        'Advanced Practice Providers',
        'Dermatology',
        'General & Other Surgery',
    ]
    df_cms['specialty_grouped'] = np.select(conditions, choices, default=df_cms['specialty_clean'])

    # Merge and compute payment intensity
    state_payments = df_cms.groupby('state')['payment_amount'].sum().reset_index()
    df_states = pd.merge(state_payments, df_acs, left_on='state', right_on='state_abbr', how='inner')
    df_states['payment_per_household'] = df_states['payment_amount'] / df_states['total_households']

    return df_cms, df_states

df_cms, df_states = load_data()

# --------------------------
# 2. Prepare State Data
# --------------------------
fips_map = {
    'AL': 1, 'AK': 2, 'AZ': 4, 'AR': 5, 'CA': 6, 'CO': 8, 'CT': 9, 'DE': 10,
    'FL': 12, 'GA': 13, 'HI': 15, 'ID': 16, 'IL': 17, 'IN': 18, 'IA': 19,
    'KS': 20, 'KY': 21, 'LA': 22, 'ME': 23, 'MD': 24, 'MA': 25, 'MI': 26,
    'MN': 27, 'MS': 28, 'MO': 29, 'MT': 30, 'NE': 31, 'NV': 32, 'NH': 33,
    'NJ': 34, 'NM': 35, 'NY': 36, 'NC': 37, 'ND': 38, 'OH': 39, 'OK': 40,
    'OR': 41, 'PA': 42, 'RI': 44, 'SC': 45, 'SD': 46, 'TN': 47, 'TX': 48,
    'UT': 49, 'VT': 50, 'VA': 51, 'WA': 53, 'WV': 54, 'WI': 55, 'WY': 56, 'DC': 11
}

df_states['fips_code'] = df_states['state'].map(fips_map)
df_states['income_percentile'] = df_states['median_income'].rank(pct=True) * 100

# --------------------------
# 3. Sidebar Filters
# --------------------------
st.sidebar.title("Dashboard Controls")

all_states = sorted(df_states['state'].unique())
selected_states = st.sidebar.multiselect(
    "Select States",
    options=all_states,
    default=all_states
)

all_specialties = sorted(df_cms['specialty_grouped'].unique())
selected_specialty = st.sidebar.multiselect(
    "Select Medical Specialties",
    options=all_specialties,
    default=["Orthopedics", "Internal Med & Primary Care"] 
)

income_range = st.sidebar.slider(
    "Filter by State Income Percentile",
    0, 100, (0, 100)
)

top_percent = st.sidebar.slider(
    "Show Top % of Payments by Amount",
    1.0, 100.0, 100.0
)

# --------------------------
# 4. Filter Logic
# --------------------------
wealth_eligible_states = df_states[
    (df_states['income_percentile'] >= income_range[0]) &
    (df_states['income_percentile'] <= income_range[1])
]['state']

final_state_list = [s for s in selected_states if s in wealth_eligible_states.values]

filtered_df = df_cms[
    (df_cms['specialty_grouped'].isin(selected_specialty)) &
    (df_cms['state'].isin(final_state_list))
]

if top_percent < 100 and len(filtered_df) > 0:
    threshold = filtered_df['payment_amount'].quantile(1 - top_percent / 100)
    filtered_df = filtered_df[filtered_df['payment_amount'] >= threshold]

# --------------------------
# 5. KPI Metrics
# --------------------------
st.title("Healthcare Industry Payment Dashboard")

total_payments = filtered_df['payment_amount'].sum()

top_1_share = 0
if total_payments > 0:
    ind_df = filtered_df[filtered_df['specialty_grouped'] != 'Unknown (Researchers & Institutions)']
    if len(ind_df) > 0:
        recip_totals = ind_df.groupby('recipient_id')['payment_amount'].sum()
        top_1_threshold = recip_totals.quantile(0.99)
        top_1_sum = recip_totals[recip_totals >= top_1_threshold].sum()
        top_1_share = top_1_sum / recip_totals.sum()

c1, c2, c3 = st.columns(3)
c1.metric("Total Payments", f"${total_payments / 1e6:.1f}M")
c2.metric("Top 1% Share (Individuals)", f"{top_1_share:.1%}")
c3.metric("Number of Transactions", f"{len(filtered_df):,}")

st.divider()

# --------------------------
# 6. Tabs
# --------------------------
tab1, tab2, tab3 = st.tabs(["Specialty Breakdown", "Payment Concentration", "Geographic Distribution"])

with tab1:
    st.subheader("Total Payments by Specialty")
    if len(filtered_df) > 0:
        spec_agg = (
            filtered_df.groupby('specialty_grouped')['payment_amount']
            .sum()
            .reset_index()
            .sort_values('payment_amount', ascending=False)
        )
        spec_bar = alt.Chart(spec_agg).mark_bar().encode(
            x=alt.X('payment_amount:Q', title='Total Payment (USD)', axis=alt.Axis(format='$.2s')),
            y=alt.Y('specialty_grouped:N', sort='-x', title='Specialty'),
            color=alt.value('#2166ac')
        ).properties(height=400)
        st.altair_chart(spec_bar, use_container_width=True)
    else:
        st.warning("No data available for the selected filters.")

with tab2:
    st.subheader("Payment Concentration (Lorenz Curve for Individual Clinicians)")
    st.markdown("*Note: Teaching Hospitals are excluded from this curve to accurately reflect individual wealth concentration.*")
    
    ind_df = filtered_df[filtered_df['specialty_grouped'] != 'Unknown (Researchers & Institutions)']
    
    if len(ind_df) > 0:
        lorenz_df = ind_df.groupby('recipient_id')['payment_amount'].sum().sort_values(ascending=True).reset_index()
        
        lorenz_df['cum_percent_money'] = (
            lorenz_df['payment_amount'].cumsum() / lorenz_df['payment_amount'].sum()
        )
        lorenz_df['cum_percent_people'] = (
            np.arange(1, len(lorenz_df) + 1) / len(lorenz_df)
        )

        if len(lorenz_df) > 5000:
            lorenz_df = lorenz_df.sample(n=5000, random_state=42).sort_values('cum_percent_people')

        equality = alt.Chart(
            pd.DataFrame({'x': [0, 1], 'y': [0, 1]})
        ).mark_line(strokeDash=[5, 5], color='gray').encode(x='x', y='y')

        lorenz = alt.Chart(lorenz_df).mark_line(color='#e63946', size=3).encode(
            x=alt.X('cum_percent_people:Q', title='Cumulative Share of Individual Recipients', axis=alt.Axis(format='%')),
            y=alt.Y('cum_percent_money:Q', title='Cumulative Share of Payments', axis=alt.Axis(format='%')),
            tooltip=[alt.Tooltip('cum_percent_people', format='.1%'), alt.Tooltip('cum_percent_money', format='.1%')]
        )
        st.altair_chart(equality + lorenz, use_container_width=True)
    else:
        st.warning("No individual clinician data available for the selected filters.")

with tab3:
    st.subheader("Payment Intensity by State (per Household)")
    states_geo = alt.topo_feature(data.us_10m.url, 'states')

    map_chart = alt.Chart(states_geo).mark_geoshape().encode(
        color=alt.Color(
            'payment_per_household:Q',
            scale=alt.Scale(scheme='tealblues'),
            title='Payment per Household ($)'
        ),
        tooltip=[
            alt.Tooltip('state_name:N', title='State'),
            alt.Tooltip('payment_per_household:Q', format='$,.2f', title='Payment per Household')
        ]
    ).transform_lookup(
        lookup='id',
        from_=alt.LookupData(df_states, 'fips_code', ['payment_per_household', 'state_name'])
    ).project(type='albersUsa').properties(height=500)

    st.altair_chart(map_chart, use_container_width=True)

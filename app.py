import streamlit as st
import pandas as pd
import altair as alt
import numpy as np
from vega_datasets import data

st.set_page_config(layout="wide", page_title="Healthcare Industry Payment Inequality Dashboard")

# --------------------------
# 1. Load Data
# --------------------------
@st.cache_data
def load_data():
    df_details = pd.read_csv("data/derived-data/cms_payments_details.csv")
    df_states = pd.read_csv("data/derived-data/cms_acs_state_summary.csv")
    return df_details, df_states

df_details, df_states = load_data()

# --------------------------
# 2. Check and Prepare State Data
# --------------------------
# Detect the correct income column name
income_options = ['median_household_income', 'median_income', 'household_income']
income_col = next((col for col in income_options if col in df_states.columns), None)

if not income_col:
    st.error(f"Income column not found. Available columns: {list(df_states.columns)}")
    st.stop()

fips_map = {
    'AL': 1,'AK': 2,'AZ': 4,'AR': 5,'CA': 6,'CO': 8,'CT': 9,'DE': 10,
    'FL': 12,'GA': 13,'HI': 15,'ID': 16,'IL': 17,'IN': 18,'IA': 19,
    'KS': 20,'KY': 21,'LA': 22,'ME': 23,'MD': 24,'MA': 25,'MI': 26,
    'MN': 27,'MS': 28,'MO': 29,'MT': 30,'NE': 31,'NV': 32,'NH': 33,
    'NJ': 34,'NM': 35,'NY': 36,'NC': 37,'ND': 38,'OH': 39,'OK': 40,
    'OR': 41,'PA': 42,'RI': 44,'SC': 45,'SD': 46,'TN': 47,'TX': 48,
    'UT': 49,'VT': 50,'VA': 51,'WA': 53,'WV': 54,'WI': 55,'WY': 56,'DC': 11
}

df_states['fips_code'] = df_states['state'].map(fips_map)
df_states['income_percentile'] = df_states[income_col].rank(pct=True) * 100
df_states['state_name'] = df_states['state']

# --------------------------
# 3. Sidebar Filters
# --------------------------
st.sidebar.title("🔍 Policy Simulation Controls")

# Added: Direct State Selection
all_states = sorted(df_states['state'].unique())
selected_states = st.sidebar.multiselect(
    "Select Specific States",
    options=all_states,
    default=all_states # Defaults to all states
)

selected_specialty = st.sidebar.multiselect(
    "Medical Specialties",
    sorted(df_details['specialty_clean'].unique()),
    default=["Orthopaedic Surgery", "Internal Medicine"]
)

income_range = st.sidebar.slider(
    "State Income Percentile Range",
    0, 100, (0, 100)
)

top_percent = st.sidebar.slider(
    "Focus on Top % Recipients (by Payment Amount)",
    1.0, 100.0, 100.0
)

# --------------------------
# 4. Filter Logic
# --------------------------
# Filter states by the wealth/income percentile slider
wealth_eligible_states = df_states[
    (df_states['income_percentile'] >= income_range[0]) &
    (df_states['income_percentile'] <= income_range[1])
]['state']

# Combined logic: Must be in selected_states AND satisfy income percentile
final_state_list = [s for s in selected_states if s in wealth_eligible_states.values]

filtered_df = df_details[
    (df_details['specialty_clean'].isin(selected_specialty)) &
    (df_details['state'].isin(final_state_list))
]

# Apply Top X% concentration logic
if top_percent < 100 and len(filtered_df) > 0:
    threshold = filtered_df['payment_amount'].quantile(1 - top_percent/100)
    filtered_df = filtered_df[filtered_df['payment_amount'] >= threshold]

# --------------------------
# 5. KPI Metrics
# --------------------------
st.title("💰 Healthcare Industry Payment Inequality Dashboard")

total_payments = filtered_df['payment_amount'].sum()

# Dynamic Top 1% Share calculation
if total_payments > 0:
    top_1_threshold = filtered_df['payment_amount'].quantile(0.99)
    top_1_sum = filtered_df[filtered_df['payment_amount'] >= top_1_threshold]['payment_amount'].sum()
    top_1_share = top_1_sum / total_payments
else:
    top_1_share = 0

c1, c2, c3 = st.columns(3)
c1.metric("Total Filtered Payments", f"${total_payments/1e6:.1f}M")
c2.metric("Top 1% Share", f"{top_1_share:.1%}")
c3.metric("Number of Payments", f"{len(filtered_df):,}")

st.divider()

# --------------------------
# 6. Tabs
# --------------------------
tab1, tab2, tab3 = st.tabs(["📊 Structure", "📈 Inequality", "🗺 Map"])

with tab1:
    st.subheader("Funding by Specialty")
    spec_bar = alt.Chart(filtered_df).mark_bar().encode(
        x=alt.X("sum(payment_amount):Q", title="Total Payment (USD)"),
        y=alt.Y("specialty_clean:N", sort='-x', title="Specialty"),
        color=alt.value("#457b9d")
    ).properties(height=400)
    st.altair_chart(spec_bar, use_container_width=True)

with tab2:
    st.subheader("Financial Concentration (Lorenz Curve)")
    if len(filtered_df) > 0:
        lorenz_df = filtered_df.sort_values("payment_amount")
        lorenz_df['cum_money'] = lorenz_df['payment_amount'].cumsum()
        lorenz_df['cum_percent_money'] = lorenz_df['cum_money'] / lorenz_df['payment_amount'].sum()
        lorenz_df['cum_percent_people'] = np.arange(1, len(lorenz_df) + 1) / len(lorenz_df)

        equality = alt.Chart(pd.DataFrame({'x':[0,1],'y':[0,1]})).mark_line(strokeDash=[5,5], color='gray').encode(x='x',y='y')
        lorenz = alt.Chart(lorenz_df).mark_line(color='#e63946', size=3).encode(
            x=alt.X('cum_percent_people:Q', title='Cumulative Share of Recipients', axis=alt.Axis(format='%')),
            y=alt.Y('cum_percent_money:Q', title='Cumulative Share of Payments', axis=alt.Axis(format='%')),
            tooltip=[alt.Tooltip('cum_percent_people', format='.1%'), alt.Tooltip('cum_percent_money', format='.1%')]
        )
        st.altair_chart(equality + lorenz, use_container_width=True)

with tab3:
    st.subheader("Geographic Payment Intensity")
    # Using Altair's TopoJSON lookup
    states_geo = alt.topo_feature(data.us_10m.url, 'states')
    
    # We must reference a column for the map intensity, e.g., 'payment_per_household'
    intensity_col = 'payment_per_household'
    
    map_chart = alt.Chart(states_geo).mark_geoshape().encode(
        color=alt.Color(f'{intensity_col}:Q', scale=alt.Scale(scheme='blues'), title="USD per Household"),
        tooltip=[alt.Tooltip('state_name:N'), alt.Tooltip(f'{intensity_col}:Q', format='$,.2f')]
    ).transform_lookup(
        lookup='id',
        from_=alt.LookupData(df_states, 'fips_code', [intensity_col, 'state_name'])
    ).project(type='albersUsa').properties(height=500)

    st.altair_chart(map_chart, use_container_width=True)
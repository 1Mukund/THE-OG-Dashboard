# app.py

import streamlit as st
import pandas as pd
import gspread
import re
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- Streamlit Page Config ---
st.set_page_config(page_title="Unified Lead Dashboard", layout="wide")
st.title("📊 Unified Lead + Web Behavior Dashboard")

# --- Auth + Load GSheet ---
@st.cache_resource
def load_sheet(sheet_url):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        dict(st.secrets["google_service_account"]), scope
    )
    client = gspread.authorize(creds)
    sheet_id = re.findall(r"/d/([a-zA-Z0-9-_]+)", sheet_url)[0]
    return client.open_by_key(sheet_id)

# --- Fetch Basic Data ---
@st.cache_data
def fetch_basic_data():
    sheets = st.secrets["google_sheets"]
    dfs = []
    for name, url in sheets.items():
        sheet = load_sheet(url)
        try:
            df = pd.DataFrame(sheet.sheet1.get_all_records())
            df['Project'] = name.replace('_', ' ').title()
            dfs.append(df)
        except:
            st.warning(f"❌ Could not fetch: {name}")
    return pd.concat(dfs, ignore_index=True)

# --- Page-level KPI Calculations ---
def calculate_web_metrics(df):
    page_cols = ['Home', 'Plans', 'Price', 'Location', 'Specification', 'Amenities', 'Media']
    df[page_cols] = df[page_cols].fillna(0)
    df['Page Depth'] = (df[page_cols] > 0).sum(axis=1)
    df['Total Time'] = df[page_cols].sum(axis=1)
    df['Last Active'] = pd.to_datetime(df['Last Event Timestamp'], errors='coerce')
    df['Recency (Days)'] = (datetime.now() - df['Last Active']).dt.days
    return df

# --- Filters ---
def apply_filters(df, web_df):
    st.sidebar.header("🔍 Filters")

    # Project
    proj_options = sorted(df['Project'].unique())
    project = st.sidebar.selectbox("Select Project", proj_options)
    df = df[df['Project'] == project]

    # Call Duration
    if 'Call Duration' in df:
        call_min, call_max = int(df['Call Duration'].min()), int(df['Call Duration'].max())
        call_filter = st.sidebar.slider("Call Duration (min)", call_min, call_max, (call_min, call_max))
        df = df[df['Call Duration'].between(*call_filter)]

    # Score Bucket
    if 'Score' in df:
        score_filter = st.sidebar.slider("Score Range", 0.0, 1.0, (0.0, 1.0))
        df = df[df['Score'].between(*score_filter)]

    # Orange Answers
    if 'Orange' in df.columns and df['Orange'].any():
        orange_df = df[df['Orange'] == True]
        for col in ['Buying Reason', 'SFT', 'Budget', 'Floor', 'Handover', 'SiteVisitPreference']:
            if col in orange_df.columns:
                unique_vals = sorted(orange_df[col].dropna().unique())
                selected = st.sidebar.multiselect(col, unique_vals)
                if selected:
                    df = df[df[col].isin(selected)]

    # Micro Market
    if 'Micro Market' in df:
        mm_vals = sorted(df['Micro Market'].dropna().unique())
        micro_filter = st.sidebar.multiselect("Micro Market", mm_vals)
        if micro_filter:
            df = df[df['Micro Market'].isin(micro_filter)]

    # Source & NI
    for col in ['Source', 'NI Reason']:
        if col in df:
            vals = sorted(df[col].dropna().unique())
            pick = st.sidebar.multiselect(col, vals)
            if pick:
                df = df[df[col].isin(pick)]

    # Web filters (if present)
    if web_df is not None:
        st.sidebar.markdown("---")
        st.sidebar.subheader("🧠 Web Events Filters")
        for page in ['Home', 'Plans', 'Price', 'Location', 'Specification', 'Amenities', 'Media']:
            op = st.sidebar.selectbox(f"{page} Filter", ["None", ">", ">=", "<", "<=", "="])
            val = st.sidebar.number_input(f"{page} Time", value=0, step=1)
            if op != "None":
                expr = f"`{page}` {op} {val}"
                df = df.query(expr)

        # Page Depth
        pd_op = st.sidebar.selectbox("Page Depth", ["None", ">", ">=", "<", "<=", "="])
        pd_val = st.sidebar.number_input("Page Depth Val", value=0, step=1)
        if pd_op != "None":
            df = df.query(f"`Page Depth` {pd_op} {pd_val}")

        # Recency
        rec_op = st.sidebar.selectbox("Recency (Days)", ["None", ">", ">=", "<", "<=", "="])
        rec_val = st.sidebar.number_input("Recency Value", value=0, step=1)
        if rec_op != "None":
            df = df.query(f"`Recency (Days)` {rec_op} {rec_val}")

    return df

# --- Main ---
with st.spinner("🔄 Fetching data..."):
    base_df = fetch_basic_data()

st.success("✅ Basic data loaded")

web_file = st.file_uploader("📁 Upload Web Events Sheet", type="xlsx")
if web_file:
    web_df = pd.read_excel(web_file, sheet_name=0)
    web_df.columns = web_df.columns.str.strip()
    web_df = calculate_web_metrics(web_df)
    merged_df = base_df.merge(web_df, on='masterLeadId', how='left')
    filtered = apply_filters(merged_df, web_df)
else:
    filtered = apply_filters(base_df, None)

# --- Show Data ---
st.subheader("📋 Filtered Leads")
st.dataframe(filtered, use_container_width=True)

# --- Web KPIs ---
if web_file and not filtered.empty:
    st.subheader("📈 Web Engagement KPIs")
    kpi_cols = ['Page Depth', 'Total Time', 'Recency (Days)']
    st.bar_chart(filtered[kpi_cols])

# --- Footer ---
st.caption("Built by Mukund x ChatGPT x Perplexity | Project-Agnostic Dashboard")

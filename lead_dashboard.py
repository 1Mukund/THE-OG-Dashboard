import streamlit as st
import pandas as pd
import gspread
import re
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from io import BytesIO

# --- Streamlit Page Config ---
st.set_page_config(page_title="Unified Lead Dashboard", layout="wide")
st.title("📊 Unified Lead Intelligence Dashboard")

# --- Auth: Google Sheets ---
@st.cache_resource
def load_sheet(sheet_url):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        dict(st.secrets["google_service_account"]), scope
    )
    client = gspread.authorize(creds)
    sheet_id = re.findall(r"/d/([a-zA-Z0-9-_]+)", sheet_url)[0]
    return client.open_by_key(sheet_id)

# --- Fetch data from Google Sheets ---
@st.cache_data
def fetch_basic_data():
    try:
        sheets = {
            "Broadway": st.secrets["BROADWAY_SHEET_URL"],
            "Loft_Part1": st.secrets["LOFT_PART1_SHEET_URL"],
            "Loft_Part2": st.secrets["LOFT_PART2_SHEET_URL"],
            "Spectra": st.secrets["SPECTRA_SHEET_URL"],
            "Springs": st.secrets["SPRINGS_SHEET_URL"],
            "Landmark": st.secrets["LANDMARK_SHEET_URL"]
        }
        dfs = []
        for name, url in sheets.items():
            sheet = load_sheet(url)
            df = pd.DataFrame(sheet.sheet1.get_all_records())
            df['Project'] = name
            dfs.append(df)
        return pd.concat(dfs, ignore_index=True)
    except Exception as e:
        st.error(f"❌ Failed to load Google Sheets: {e}")
        st.stop()

# --- File Upload ---
st.sidebar.header("📁 Upload Web Events Sheet")
web_file = st.sidebar.file_uploader("Upload Web Events Excel", type=["xlsx"])

# --- Load basic data ---
with st.spinner("🔄 Loading basic lead data from all projects..."):
    basic_df = fetch_basic_data()

# --- Display toggle ---
view_option = st.sidebar.radio("Choose data view:", ["Unified Basic Data", "Combined with Web Events"])

# --- Helper: Clean Columns ---
def clean_columns(df):
    df.columns = df.columns.str.strip()
    return df

# --- Web Metrics Calculation ---
def calculate_web_metrics(df):
    if df.empty:
        return df
    page_cols = ['Home', 'Plans', 'Price', 'Location', 'Specification', 'Amenities', 'Media']
    df[page_cols] = df[page_cols].fillna(0)
    df['Total Time Spent'] = df[page_cols].sum(axis=1)
    df['Page Depth'] = df[page_cols].gt(0).sum(axis=1)
    df['Recency'] = pd.to_datetime(df['Timestamp'], errors='coerce')
    df['Recency'] = (datetime.now() - df['Recency']).dt.days
    return df

# --- Combine Basic and Web Data ---
if web_file:
    with st.spinner("🔄 Processing uploaded web events sheet..."):
        try:
            web_df = pd.read_excel(web_file, sheet_name="Main")
            web_df = clean_columns(web_df)
            web_df = calculate_web_metrics(web_df)

            # Merge on masterLeadId
            merged_df = basic_df.merge(web_df, on="masterLeadId", how="left", suffixes=("", "_web"))
        except Exception as e:
            st.error(f"❌ Failed to process uploaded file: {e}")
            st.stop()
else:
    merged_df = basic_df.copy()

# --- Sidebar Filters ---
st.sidebar.header("🔍 Filters")

# Page-level time filters
page_cols = ['Home', 'Plans', 'Price', 'Location', 'Specification', 'Amenities', 'Media']
selected_pages = st.sidebar.multiselect("Select Pages for Time Filter", options=page_cols)
if selected_pages:
    condition_type = st.sidebar.radio("Condition Type", ["AND", "OR"])
    operator = st.sidebar.selectbox("Operator", [">", ">=", "=", "<", "<="])
    threshold = st.sidebar.number_input("Threshold (in seconds)", min_value=0, value=10)
    if condition_type == "AND":
        for col in selected_pages:
            merged_df = merged_df.query(f"`{col}` {operator} @threshold")
    else:
        condition = " | ".join([f"`{col}` {operator} @threshold" for col in selected_pages])
        merged_df = merged_df.query(condition)

# Other filters
if "Call Duration" in merged_df.columns:
    call_duration = st.sidebar.slider("Call Duration (mins)", 0, 60, (0, 60))
    merged_df = merged_df[merged_df["Call Duration"].between(*call_duration)]

if "Score" in merged_df.columns:
    score_range = st.sidebar.slider("Score Range", 0.0, 1.0, (0.0, 1.0))
    merged_df = merged_df[merged_df["Score"].between(*score_range)]

if "Micro Market" in merged_df.columns:
    micro_options = merged_df["Micro Market"].dropna().unique().tolist()
    selected_micro = st.sidebar.multiselect("Micro Market", options=micro_options)
    if selected_micro:
        merged_df = merged_df[merged_df["Micro Market"].isin(selected_micro)]

if "Orange" in merged_df.columns:
    if st.sidebar.checkbox("Filter Only Orange Leads"):
        merged_df = merged_df[merged_df["Orange"] == True]
        orange_filters = ["Buying Reason", "SFT", "Budget", "Floor", "Handover", "SiteVisitPreference"]
        for col in orange_filters:
            if col in merged_df.columns:
                options = merged_df[col].dropna().unique().tolist()
                selected = st.sidebar.multiselect(col, options=options)
                if selected:
                    merged_df = merged_df[merged_df[col].isin(selected)]

if "Source" in merged_df.columns:
    source_options = merged_df["Source"].dropna().unique().tolist()
    selected_source = st.sidebar.multiselect("Source", options=source_options)
    if selected_source:
        merged_df = merged_df[merged_df["Source"].isin(selected_source)]

if "NI Reason" in merged_df.columns:
    ni_options = merged_df["NI Reason"].dropna().unique().tolist()
    selected_ni = st.sidebar.multiselect("NI Reason", options=ni_options)
    if selected_ni:
        merged_df = merged_df[merged_df["NI Reason"].isin(selected_ni)]

# --- Show Final Output ---
st.subheader("📋 Final Filtered Data")
st.dataframe(merged_df, use_container_width=True)

# --- KPI Section ---
st.subheader("📊 KPI Analysis")
kpi_cols = []
if "Total Time Spent" in merged_df.columns:
    kpi_cols.append("Total Time Spent")
if "Page Depth" in merged_df.columns:
    kpi_cols.append("Page Depth")
if "Recency" in merged_df.columns:
    kpi_cols.append("Recency")

if kpi_cols:
    st.bar_chart(merged_df[kpi_cols])
else:
    st.info("Upload web events sheet to see KPIs.")

# --- Footer ---
st.caption("Built by Mukund x ChatGPT x Perplexity | Project-Agnostic Dashboard")

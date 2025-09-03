import streamlit as st
import pandas as pd
import gspread
import re
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- Streamlit Page Config ---
st.set_page_config(page_title="Unified Lead Dashboard", layout="wide")
st.title("📊 Unified Project Dashboard")

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

# --- Fetch data from all Sheets ---
@st.cache_data
def fetch_all_data():
    try:
        sheets = {}
        sheets["Loft_Part1"] = pd.DataFrame(load_sheet(st.secrets["LOFT_PART1_SHEET_URL"]).sheet1.get_all_records())
        sheets["Loft_Part2"] = pd.DataFrame(load_sheet(st.secrets["LOFT_PART2_SHEET_URL"]).sheet1.get_all_records())
        sheets["Spectra"] = pd.DataFrame(load_sheet(st.secrets["SPECTRA_SHEET_URL"]).sheet1.get_all_records())
        sheets["Springs"] = pd.DataFrame(load_sheet(st.secrets["SPRINGS_SHEET_URL"]).sheet1.get_all_records())
        sheets["Landmark"] = pd.DataFrame(load_sheet(st.secrets["LANDMARK_SHEET_URL"]).sheet1.get_all_records())
        return sheets
    except Exception as e:
        st.error(f"❌ Failed to load Google Sheets: {e}")
        st.stop()

# --- KPI Calculator for Web Events ---
def calculate_web_metrics(df):
    page_cols = [col for col in df.columns if col.lower() in ["home", "plans", "price", "location", "specification", "amenities", "media"]]
    if not page_cols:
        st.warning("⚠️ No valid page-level time columns found in uploaded file.")
        return df
    df[page_cols] = df[page_cols].fillna(0)
    df["Page Depth"] = (df[page_cols] > 0).sum(axis=1)
    df["Page Recency"] = df[page_cols].apply(lambda row: row[row > 0].index[-1] if any(row > 0) else None, axis=1)
    df["Total Time"] = df[page_cols].sum(axis=1)
    return df

# --- Load All Data ---
with st.spinner("🔄 Loading basic project data from Google Sheets..."):
    all_data = fetch_all_data()

# --- Sidebar: Project Selector ---
selected_project = st.sidebar.selectbox("Select Project", list(all_data.keys()))
basic_df = all_data[selected_project].copy()

# --- Sidebar: Web Events Upload ---
st.sidebar.markdown("---")
st.sidebar.subheader("📂 Upload Web Events")
web_file = st.sidebar.file_uploader("Upload Web Events .xlsx", type=["xlsx"])

# --- Process if file uploaded ---
if web_file is not None:
    web_df = pd.read_excel(web_file, sheet_name=0)
    if "masterLeadId" not in web_df.columns:
        st.error("❌ 'masterLeadId' column missing in uploaded file.")
        st.stop()
    web_df = calculate_web_metrics(web_df)
    merged_df = pd.merge(basic_df, web_df, on="masterLeadId", how="left")
else:
    merged_df = basic_df.copy()

# --- Sidebar Filters ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 Filters")

# Call Duration
if "Call Duration" in merged_df.columns:
    call_min, call_max = int(merged_df["Call Duration"].min()), int(merged_df["Call Duration"].max())
    call_range = st.sidebar.slider("Call Duration (sec)", call_min, call_max, (call_min, call_max))
    merged_df = merged_df[(merged_df["Call Duration"] >= call_range[0]) & (merged_df["Call Duration"] <= call_range[1])]

# Score Buckets
if "Score" in merged_df.columns:
    score_min, score_max = float(merged_df["Score"].min()), float(merged_df["Score"].max())
    score_range = st.sidebar.slider("Lead Score", score_min, score_max, (score_min, score_max))
    merged_df = merged_df[(merged_df["Score"] >= score_range[0]) & (merged_df["Score"] <= score_range[1])]

# Micro Market Filter
if "Micro Market" in merged_df.columns:
    micromarkets = st.sidebar.multiselect("Micro Market", options=merged_df["Micro Market"].dropna().unique())
    if micromarkets:
        merged_df = merged_df[merged_df["Micro Market"].isin(micromarkets)]

# Orange Questions
if "Orange" in merged_df.columns and merged_df["Orange"].astype(str).str.lower().eq("true").any():
    st.sidebar.markdown("**Orange Lead Responses:**")
    orange_df = merged_df[merged_df["Orange"].astype(str).str.lower() == "true"]
    for col in ["Buying Reason", "SFT", "Budget", "Floor", "Handover", "SiteVisitPreference"]:
        if col in orange_df.columns:
            options = st.sidebar.multiselect(f"{col}", options=orange_df[col].dropna().unique())
            if options:
                merged_df = merged_df[merged_df[col].isin(options)]

# Source + NI Reason
for col in ["Source", "NI Reason"]:
    if col in merged_df.columns:
        options = st.sidebar.multiselect(f"{col}", options=merged_df[col].dropna().unique())
        if options:
            merged_df = merged_df[merged_df[col].isin(options)]

# Page Time Filters
if web_file is not None:
    st.sidebar.markdown("---")
    st.sidebar.subheader("🧠 Page-Level Filters")
    logic_type = st.sidebar.radio("Logic", ["AND", "OR"], horizontal=True)
    page_cols = [col for col in web_df.columns if col.lower() in ["home", "plans", "price", "location", "specification", "amenities", "media"]]
    filters = []
    for col in page_cols:
        op = st.sidebar.selectbox(f"{col} operator", [">", ">=", "<", "<=", "=="], key=f"op_{col}")
        val = st.sidebar.number_input(f"{col} time", min_value=0, key=f"val_{col}")
        filters.append((col, op, val))

    if logic_type == "AND":
        for col, op, val in filters:
            merged_df = merged_df.query(f"`{col}` {op} @val")
    else:
        or_query = " | ".join([f"`{col}` {op} @val" for col, op, val in filters])
        merged_df = merged_df.query(or_query)

# --- Output Table ---
st.subheader("📋 Combined Data View")
st.dataframe(merged_df, use_container_width=True)

# --- KPI View ---
if web_file is not None:
    st.subheader("📈 Web Engagement KPIs")
    kpi_cols = ["Page Depth", "Total Time"]
    st.bar_chart(merged_df[kpi_cols])

# --- Done ---

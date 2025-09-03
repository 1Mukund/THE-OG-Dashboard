import streamlit as st
import pandas as pd
import gspread
import re
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from io import BytesIO

# --- Streamlit Page Config ---
st.set_page_config(page_title="Unified Project Dashboard", layout="wide")
st.title("📊 Unified Lead + Web Events Dashboard")

# --- Google Sheets Auth ---
@st.cache_resource
def get_gsheet_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(st.secrets["google_service_account"]), scope)
    return gspread.authorize(creds)

def load_sheet(sheet_url):
    try:
        client = get_gsheet_client()
        sheet_id = re.findall(r"/d/([a-zA-Z0-9-_]+)", sheet_url)[0]
        return pd.DataFrame(client.open_by_key(sheet_id).sheet1.get_all_records())
    except Exception as e:
        st.warning(f"❌ Error loading sheet: {e}")
        return pd.DataFrame()

# --- Hardcoded URLs (bypass secrets if keys are missing) ---
def get_project_sheets():
    return {
        "Loft_Part1": "https://docs.google.com/spreadsheets/d/1RHg1ndf9JJpSL2hFFkzImtVsiX8-VE28ZEWPzmRzRg0",
        "Loft_Part2": "https://docs.google.com/spreadsheets/d/13KF8bupHECjLqW5iyLvzEiZP7UY2gCESAgqLPSRy4fA",
        "Spectra": "https://docs.google.com/spreadsheets/d/1WlN3O8V5wpw1TJQpmc-GfVSmuu4GmKnJ5yMVMu0PQ5Y",
        "Springs": "https://docs.google.com/spreadsheets/d/11bbM5p_Qotd-NZvD33CcepD5grdpI-0hiVi8JwNyeQs",
        "Landmark": "https://docs.google.com/spreadsheets/d/1hmWBJMYCRmTajIr971kNZXgWcnMOY9kKkUpSK93WCwE"
    }

@st.cache_data
def load_all_basic_data():
    data = {}
    for name, url in get_project_sheets().items():
        df = load_sheet(url)
        if not df.empty:
            df['Project'] = name
            data[name] = df
    return pd.concat(data.values(), ignore_index=True) if data else pd.DataFrame()

# --- Upload Web Events ---
uploaded_events = st.file_uploader("Upload Web Events Sheet (.xlsx)", type=["xlsx"])
basic_data = load_all_basic_data()

if not basic_data.empty:
    st.success(f"✅ Loaded {len(basic_data)} leads from basic sheets.")
else:
    st.error("❌ Could not load basic data. Check sheet access or URLs.")
    st.stop()

# --- Process Web Events ---
if uploaded_events:
    events_df = pd.read_excel(uploaded_events, sheet_name=None)
    web_df = events_df.get("Main")

    if web_df is None:
        st.error("❌ 'Main' sheet not found in uploaded file.")
        st.stop()

    merged_df = basic_data.merge(web_df, on="masterLeadId", how="left")
    st.success(f"✅ Merged {len(merged_df)} leads. Displaying combined dashboard...")

    # --- Sidebar Filters ---
    st.sidebar.header("🔍 Filters")
    call_duration = st.sidebar.slider("Min Call Duration", 0, 1000, 0)
    score_range = st.sidebar.slider("Score Range", 0.0, 1.0, (0.0, 1.0))
    micro = st.sidebar.multiselect("Micro Market", merged_df["Micro Market"].dropna().unique())
    source = st.sidebar.multiselect("Source", merged_df["Source"].dropna().unique())
    orange_only = st.sidebar.checkbox("🟠 Orange Leads Only")
    orange_fields = ["Buying Reason", "SFT", "Budget", "Floor", "Handover", "SiteVisitPreference"]

    st.sidebar.subheader("📄 Page Filters")
    page = st.sidebar.selectbox("Select Page", ["Home", "Plans", "Price", "Location", "Specification", "Amenities", "Media"])
    operator = st.sidebar.selectbox("Condition", [">", ">=", "=", "<", "<="])
    page_time = st.sidebar.number_input("Time (seconds)", min_value=0)

    # --- Filtering Logic ---
    filtered = merged_df.copy()
    filtered = filtered[filtered["Call Duration"] >= call_duration]
    filtered = filtered[(filtered["Score"] >= score_range[0]) & (filtered["Score"] <= score_range[1])]
    if micro:
        filtered = filtered[filtered["Micro Market"].isin(micro)]
    if source:
        filtered = filtered[filtered["Source"].isin(source)]
    if orange_only:
        filtered = filtered[filtered["Orange"] == True]
        for field in orange_fields:
            values = st.sidebar.multiselect(field, filtered[field].dropna().unique())
            if values:
                filtered = filtered[filtered[field].isin(values)]

    col = page + " Page Time"
    if col in filtered.columns:
        if operator == ">":
            filtered = filtered[filtered[col] > page_time]
        elif operator == ">=":
            filtered = filtered[filtered[col] >= page_time]
        elif operator == "=":
            filtered = filtered[filtered[col] == page_time]
        elif operator == "<":
            filtered = filtered[filtered[col] < page_time]
        elif operator == "<=":
            filtered = filtered[filtered[col] <= page_time]

    # --- Web Events KPI ---
    st.subheader("📊 Web Behavior KPIs")
    web_cols = [c for c in merged_df.columns if c.endswith("Page Time")]
    filtered["Page Depth"] = filtered[web_cols].notna().sum(axis=1)
    filtered["Total Time"] = filtered[web_cols].sum(axis=1)
    filtered["Recency"] = pd.to_datetime(filtered.get("Last_Visit_Timestamp", datetime.now()), errors="coerce")

    k1, k2, k3 = st.columns(3)
    k1.metric("Avg Page Depth", round(filtered["Page Depth"].mean(), 2))
    k2.metric("Avg Total Time", round(filtered["Total Time"].mean(), 2))
    k3.metric("Recent Visit", str(filtered["Recency"].max().date()) if not filtered["Recency"].isna().all() else "NA")

    st.subheader("📋 Filtered Leads")
    st.dataframe(filtered, use_container_width=True)
else:
    st.info("Upload a Web Events Sheet to begin analysis.")

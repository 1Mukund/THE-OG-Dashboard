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
def load_sheet(sheet_url):
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        dict(st.secrets["google_service_account"]), scope
    )
    client = gspread.authorize(creds)
    sheet_id = re.findall(r"/d/([a-zA-Z0-9-_]+)", sheet_url)[0]
    return client.open_by_key(sheet_id)

# --- Auto-load all basic project sheets ---
@st.cache_data
def load_all_basic_data():
    sheets = {
        "Broadway": st.secrets["BROADWAY_BASIC_URL"],
        "Loft_Part1": st.secrets["LOFT_PART1_BASIC_URL"],
        "Loft_Part2": st.secrets["LOFT_PART2_BASIC_URL"],
        "Spectra": st.secrets["SPECTRA_BASIC_URL"],
        "Springs": st.secrets["SPRINGS_BASIC_URL"],
        "Landmark": st.secrets["LANDMARK_BASIC_URL"]
    }
    data = {}
    for name, url in sheets.items():
        try:
            sheet = load_sheet(url)
            df = pd.DataFrame(sheet.sheet1.get_all_records())
            df['Project'] = name
            data[name] = df
        except Exception as e:
            st.warning(f"Couldn't load sheet for {name}: {e}")
    return pd.concat(data.values(), ignore_index=True)

# --- Upload Web Events ---
uploaded_events = st.file_uploader("📤 Upload Web Events Sheet (.xlsx)", type=["xlsx"])
basic_data = load_all_basic_data()

# --- Process Web Events ---
if uploaded_events:
    events_df = pd.read_excel(uploaded_events, sheet_name=None)
    web_df = events_df.get("Main")

    if web_df is None:
        st.error("❌ 'Main' sheet not found in uploaded file.")
        st.stop()

    # Match by masterLeadId
    merged_df = basic_data.merge(web_df, on="masterLeadId", how="left")

    st.success(f"✅ Merged {len(merged_df)} leads. Displaying combined dashboard...")

    # --- Sidebar Filters ---
    st.sidebar.header("🔍 Filters")
    call_duration = st.sidebar.slider("Min Call Duration", 0, 1000, 0)
    score_range = st.sidebar.slider("Score Range", 0.0, 1.0, (0.0, 1.0))
    micro = st.sidebar.multiselect("Micro Market", merged_df["Micro Market"].dropna().unique())
    source = st.sidebar.multiselect("Source", merged_df["Source"].dropna().unique())

    # Orange-only filters
    orange_only = st.sidebar.checkbox("🟠 Orange Leads Only")
    orange_fields = ["Buying Reason", "SFT", "Budget", "Floor", "Handover", "SiteVisitPreference"]

    # Page-level filters (example for Home/Price page)
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
    if page:
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

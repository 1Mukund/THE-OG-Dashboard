import streamlit as st
import pandas as pd
import gspread
import re
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# --- Streamlit Page Config ---
st.set_page_config(page_title="Unified Lead + Web Events Dashboard", layout="wide")
st.title("\U0001F4CA Unified Lead + Web Events Dashboard")

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

# --- Load all Basic Sheets ---
@st.cache_data
def load_all_basic_data():
    sheets = {
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

# --- Upload Web Events Sheet ---
uploaded_events = st.file_uploader("Upload Web Events Sheet (.xlsx)", type=["xlsx"])
basic_data = load_all_basic_data()

# --- Web Events Upload Logic ---
if uploaded_events:
    events_df = pd.read_excel(uploaded_events, sheet_name=None)
    web_df = events_df.get("Main")

    if web_df is None:
        st.error("❌ 'Main' sheet not found in uploaded file.")
        st.stop()

    # Merge
    merged_df = basic_data.merge(web_df, on="masterLeadId", how="left")

    st.success(f"✅ Merged {len(merged_df)} leads. Displaying combined dashboard...")

    # --- Optional Debug Expander ---
    with st.expander("🧾 Available Columns in Merged Data"):
        st.write(merged_df.columns.tolist())

    # --- Sidebar Filters ---
    st.sidebar.header("\U0001F50D Filters")
    call_duration = st.sidebar.slider("Min Call Duration", 0, 1000, 0)
    score_range = st.sidebar.slider("Score Range", 0.0, 1.0, (0.0, 1.0))

    # Safe Micro Market filter
    if "Micro Market" in merged_df.columns:
        micro = st.sidebar.multiselect("Micro Market", merged_df["Micro Market"].dropna().unique())
        if micro:
            merged_df = merged_df[merged_df["Micro Market"].isin(micro)]

    # Safe Source filter
    if "Source" in merged_df.columns:
        source = st.sidebar.multiselect("Source", merged_df["Source"].dropna().unique())
        if source:
            merged_df = merged_df[merged_df["Source"].isin(source)]

    # Orange-only filters
    orange_only = st.sidebar.checkbox("🟠 Orange Leads Only")
    orange_fields = ["Buying Reason", "SFT", "Budget", "Floor", "Handover", "SiteVisitPreference"]
    if orange_only:
        if "Orange" in merged_df.columns:
            merged_df = merged_df[merged_df["Orange"] == True]
        for field in orange_fields:
            if field in merged_df.columns:
                values = st.sidebar.multiselect(field, merged_df[field].dropna().unique())
                if values:
                    merged_df = merged_df[merged_df[field].isin(values)]

    # Page-level filters (example for Home/Price page)
    st.sidebar.subheader("\U0001F4C4 Page Filters")
    page_options = [c.replace(" Page Time", "") for c in merged_df.columns if c.endswith("Page Time")]
    page = st.sidebar.selectbox("Select Page", page_options)
    operator = st.sidebar.selectbox("Condition", [">", ">=", "=", "<", "<="])
    page_time = st.sidebar.number_input("Time (seconds)", min_value=0)

    col = page + " Page Time"
    if col in merged_df.columns:
        if operator == ">":
            merged_df = merged_df[merged_df[col] > page_time]
        elif operator == ">=":
            merged_df = merged_df[merged_df[col] >= page_time]
        elif operator == "=":
            merged_df = merged_df[merged_df[col] == page_time]
        elif operator == "<":
            merged_df = merged_df[merged_df[col] < page_time]
        elif operator == "<=":
            merged_df = merged_df[merged_df[col] <= page_time]

    # Score & Call Duration
    if "Call Duration" in merged_df.columns:
        merged_df = merged_df[merged_df["Call Duration"] >= call_duration]
    if "Score" in merged_df.columns:
        merged_df = merged_df[(merged_df["Score"] >= score_range[0]) & (merged_df["Score"] <= score_range[1])]

    # --- Web Events KPI ---
    st.subheader("\U0001F4CA Web Behavior KPIs")
    web_cols = [c for c in merged_df.columns if c.endswith("Page Time")]
    merged_df["Page Depth"] = merged_df[web_cols].notna().sum(axis=1)
    merged_df["Total Time"] = merged_df[web_cols].sum(axis=1)
    if "Last_Visit_Timestamp" in merged_df.columns:
        merged_df["Recency"] = pd.to_datetime(merged_df["Last_Visit_Timestamp"], errors="coerce")
    else:
        merged_df["Recency"] = pd.NaT

    k1, k2, k3 = st.columns(3)
    k1.metric("Avg Page Depth", round(merged_df["Page Depth"].mean(), 2))
    k2.metric("Avg Total Time", round(merged_df["Total Time"].mean(), 2))
    k3.metric("Recent Visit", str(merged_df["Recency"].max().date()) if not merged_df["Recency"].isna().all() else "NA")

    # --- Data Table ---
    st.subheader("\U0001F4CB Filtered Leads")
    st.dataframe(merged_df, use_container_width=True)

else:
    st.info("Upload a Web Events Sheet to begin analysis.")

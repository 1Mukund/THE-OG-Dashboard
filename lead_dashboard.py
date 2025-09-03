import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import re
from datetime import datetime

# --- Streamlit Page Config ---
st.set_page_config(page_title="OG Lead Dashboard", layout="wide")
st.title("📊 Unified Project Lead Dashboard")

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

# --- Fetch Project Data ---
@st.cache_data
def fetch_basic_data():
    try:
        project_sheets = {
            "Loft Part 1": st.secrets["LOFT_PART1_SHEET_URL"],
            "Loft Part 2": st.secrets["LOFT_PART2_SHEET_URL"],
            "Spectra": st.secrets["SPECTRA_SHEET_URL"],
            "Springs": st.secrets["SPRINGS_SHEET_URL"],
            "Landmark": st.secrets["LANDMARK_SHEET_URL"],
        }
        dfs = {}
        for name, url in project_sheets.items():
            sheet = load_sheet(url)
            df = pd.DataFrame(sheet.worksheet("Sheet1").get_all_records())
            df["Project"] = name
            dfs[name] = df
        return pd.concat(dfs.values(), ignore_index=True)
    except Exception as e:
        st.error(f"❌ Failed to load Google Sheets: {e}")
        st.stop()

# --- Web Events Metrics Calculator ---
def calculate_web_metrics(df):
    page_cols = ["Home", "Plans", "Price", "Location", "Specification", "Amenities", "Media"]
    existing_page_cols = [col for col in page_cols if col in df.columns]

    if not existing_page_cols:
        st.warning("⚠️ None of the expected page columns found in the uploaded Web Events sheet.")
        return df

    df[existing_page_cols] = df[existing_page_cols].fillna(0)
    df["Page Depth"] = df[existing_page_cols].gt(0).sum(axis=1)
    df["Recency Score"] = df[existing_page_cols].apply(lambda row: row.last_valid_index(), axis=1)
    return df

# --- Start Loading ---
st.sidebar.success("✅ All systems go!")

basic_df = fetch_basic_data()

st.sidebar.header("📤 Upload Web Events Sheet")
web_file = st.sidebar.file_uploader("Upload XLSX file", type=["xlsx"])

if web_file:
    try:
        web_df = pd.read_excel(web_file, sheet_name=0)
        web_df.columns = web_df.columns.str.strip()
        web_df = calculate_web_metrics(web_df)

        # Merge logic using masterLeadId
        if "masterLeadId" in web_df.columns and "masterLeadId" in basic_df.columns:
            merged_df = basic_df.merge(web_df, on="masterLeadId", how="left")
            st.success("🔗 Successfully matched Web Events with Basic Data")
        else:
            st.error("❌ 'masterLeadId' column missing in one of the sheets.")
            st.stop()
    except Exception as e:
        st.error(f"❌ Failed to process uploaded file: {e}")
        st.stop()
else:
    st.info("Please upload a Web Events Sheet to begin.")
    st.stop()

# --- Filters ---
st.sidebar.header("🔍 Filters")

# Score filter
score_range = st.sidebar.slider("Score Range", 0.0, 1.0, (0.0, 1.0), step=0.01)

# Call Duration filter
min_call = int(merged_df["Call Duration"].min()) if "Call Duration" in merged_df else 0
max_call = int(merged_df["Call Duration"].max()) if "Call Duration" in merged_df else 300
call_dur = st.sidebar.slider("Call Duration (sec)", min_call, max_call, (min_call, max_call))

# Micro Market
if "Micro Market" in merged_df:
    micro = st.sidebar.multiselect("Micro Market", merged_df["Micro Market"].dropna().unique())
else:
    micro = []

# Orange only fields
if "Orange" in merged_df:
    if st.sidebar.checkbox("Orange Leads Only"):
        merged_df = merged_df[merged_df["Orange"] == True]

    orange_fields = ["Buying Reason", "SFT", "Budget", "Floor", "Handover", "SiteVisitPreference"]
    for col in orange_fields:
        if col in merged_df:
            selected = st.sidebar.multiselect(col, merged_df[col].dropna().unique())
            if selected:
                merged_df = merged_df[merged_df[col].isin(selected)]

# Source and NI
for col in ["Source", "NI Reason"]:
    if col in merged_df:
        selected = st.sidebar.multiselect(col, merged_df[col].dropna().unique())
        if selected:
            merged_df = merged_df[merged_df[col].isin(selected)]

# Page-level AND/OR filtering (basic version)
st.sidebar.markdown("---")
st.sidebar.subheader("📄 Page-Level Filters")
logic_type = st.sidebar.radio("Apply Logic", ["AND", "OR"], index=0)

page_inputs = {}
page_cols = ["Home", "Plans", "Price", "Location", "Specification", "Amenities", "Media"]
for page in page_cols:
    if page in merged_df:
        op = st.sidebar.selectbox(f"{page} Operator", [">=", ">", "=", "<", "<="], key=f"op_{page}")
        val = st.sidebar.number_input(f"{page} Value", value=0, key=f"val_{page}")
        page_inputs[page] = (op, val)

# Apply page logic
for page, (op, val) in page_inputs.items():
    if op and page in merged_df:
        if logic_type == "AND":
            merged_df = merged_df.query(f"`{page}` {op} {val}")
        else:
            temp = merged_df.query(f"`{page}` {op} {val}")
            merged_df = pd.concat([merged_df, temp]).drop_duplicates()

# Final Filters
merged_df = merged_df[(merged_df["Score"] >= score_range[0]) & (merged_df["Score"] <= score_range[1])]
merged_df = merged_df[(merged_df["Call Duration"] >= call_dur[0]) & (merged_df["Call Duration"] <= call_dur[1])]

# --- Output ---
st.subheader("📊 Final Combined Lead Dataset")
st.dataframe(merged_df, use_container_width=True)

# --- Web Metrics Summary ---
st.subheader("📈 Web Event KPIs")
if "Page Depth" in merged_df:
    st.metric("Average Page Depth", round(merged_df["Page Depth"].mean(), 2))
    st.bar_chart(merged_df["Page Depth"].value_counts().sort_index())


# --- Footer ---
st.caption("Built by Mukund x ChatGPT x Perplexity | Project-Agnostic Dashboard")

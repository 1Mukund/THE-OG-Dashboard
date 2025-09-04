import streamlit as st
import pandas as pd
import gspread
from google.oauth2 import service_account

st.set_page_config(page_title="Unified Lead + Web Events Dashboard", layout="wide")

st.title("Unified Lead + Web Events Dashboard")

# -------------------------
# 1. Authenticate Google Sheets
# -------------------------
@st.cache_resource
def get_gspread_client():
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["google_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    return gspread.authorize(credentials)

client = get_gspread_client()

# -------------------------
# 2. Load Each Sheet
# -------------------------
PROJECT_SHEETS = {
    "Broadway": "1smMVEgiadMWc5HB8TayEsai22qnFy1e5xKkoue3B3G8",
    "Loft_Part2": "13KF8bupHECjLqW5iyLvzEiZP7UY2gCESAgqLPSRy4fA",
    "Spire": "1iOb3nml_6eOMm68vDKTi-3qe-PnwFbzspqKcNeDBrVU",
    "Springs": "11bbM5p_Qotd-NZvD33CcepD5grdpI-0hiVi8JwNyeQs",
    "Spectra": "1WlN3O8V5wpw1TJQpmc-GfVSmuu4GmKnJ5yMVMu0PQ5Y",
    "Landmark": "1hmWBJMYCRmTajIr971kNZXgWcnMOY9kKkUpSK93WCwE",
    "Loft_Part1": "1RHg1ndf9JJpSL2hFFkzImtVsiX8-VE28ZEWPzmRzRg0"
}

@st.cache_data
def load_basic_data():
    data = {}
    for name, sheet_id in PROJECT_SHEETS.items():
        try:
            sh = client.open_by_key(sheet_id)
            ws = sh.sheet1
            df = pd.DataFrame(ws.get_all_records())
            df['Project'] = name
            data[name] = df
        except Exception as e:
            st.warning(f"Couldn't load sheet for {name}: {e}")
    if not data:
        st.error("None of the basic data sheets could be loaded. Please check sheets or permissions.")
    return pd.concat(data.values(), ignore_index=True) if data else pd.DataFrame()

basic_data = load_basic_data()

# -------------------------
# 3. Upload Web Events File
# -------------------------
st.subheader("Upload Web Events Sheet (.xlsx)")
uploaded_file = st.file_uploader("Drag and drop file here", type="xlsx")

if uploaded_file:
    try:
        web_data = pd.read_excel(uploaded_file)
        if 'masterLeadId' not in web_data.columns:
            st.error("Uploaded file must contain 'masterLeadId' column.")
        else:
            # Clean web data
            web_data['masterLeadId'] = web_data['masterLeadId'].astype(str)
            basic_data['masterLeadId'] = basic_data['masterLeadId'].astype(str)

            # Merge
            merged = pd.merge(basic_data, web_data, on='masterLeadId', how='inner')

            # Filters
            st.sidebar.header("Filters")

            min_call = st.sidebar.slider("Min Call Duration", 0, 1000, 60)
            score_range = st.sidebar.slider("Score Range", 0.0, 1.0, (0.05, 0.9))

            filtered = merged[
                (merged.get("call_duration", 0) >= min_call) &
                (merged.get("score", 0) >= score_range[0]) &
                (merged.get("score", 0) <= score_range[1])
            ]

            st.success(f"Loaded and matched {len(filtered)} leads out of {len(basic_data)}")

            st.dataframe(filtered)

    except Exception as e:
        st.error(f"Error processing uploaded web sheet: {e}")
else:
    st.info("Please upload the Web Events Sheet (.xlsx) to begin analysis.")

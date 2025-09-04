import streamlit as st
import pandas as pd
import gspread
import json
from datetime import datetime

st.set_page_config(page_title="📊 Unified Lead + Web Events Dashboard", layout="wide")
st.title("\ud83d\udcca Unified Lead + Web Events Dashboard")

# Upload Web Events Sheet
uploaded_file = st.file_uploader("\ud83d\udcc2 Upload Web Events Sheet (.xlsx)", type=["xlsx"])

# Google Sheet URLs (use your real links here)
sheet_urls = {
    "Broadway": "https://docs.google.com/spreadsheets/d/1smMVEgiadMWc5HB8TayEsai22qnFy1e5xKkoue3B3G8",
    "Loft_Part1": "https://docs.google.com/spreadsheets/d/1RHg1ndf9JJpSL2hFFkzImtVsiX8-VE28ZEWPzmRzRg0",
    "Loft_Part2": "https://docs.google.com/spreadsheets/d/13KF8bupHECjLqW5iyLvzEiZP7UY2gCESAgqLPSRy4fA",
    "Spire": "https://docs.google.com/spreadsheets/d/1iOb3nml_6eOMm68vDKTi-3qe-PnwFbzspqKcNeDBrVU",
    "Springs": "https://docs.google.com/spreadsheets/d/11bbM5p_Qotd-NZvD33CcepD5grdpI-0hiVi8JwNyeQs",
    "Spectra": "https://docs.google.com/spreadsheets/d/1WlN3O8V5wpw1TJQpmc-GfVSmuu4GmKnJ5yMVMu0PQ5Y",
    "Landmark": "https://docs.google.com/spreadsheets/d/1hmWBJMYCRmTajIr971kNZXgWcnMOY9kKkUpSK93WCwE"
}

@st.cache_data(show_spinner=False)
def load_all_basic_data():
    data = {}
    try:
        creds = json.loads(st.secrets["GOOGLE_SHEET_CREDS"])
        gc = gspread.service_account_from_dict(creds)

        for name, url in sheet_urls.items():
            try:
                sh = gc.open_by_url(url)
                worksheet = sh.get_worksheet(0)
                df = pd.DataFrame(worksheet.get_all_records())
                df["SourceProject"] = name
                data[name] = df
            except Exception as e:
                st.warning(f"Couldn't load sheet for {name}: {e}")
        return pd.concat(data.values(), ignore_index=True)
    except Exception as e:
        st.error("None of the basic data sheets could be loaded. Please check secrets or permissions.")
        return pd.DataFrame()

# Load all Basic Data Sheets
basic_data = load_all_basic_data()

# Display basic data stats if loaded
if not basic_data.empty:
    st.success(f"Loaded {len(basic_data)} rows from {len(sheet_urls)} basic data sheets.")

    # Additional Filters + Logic go here
    st.subheader("\ud83d\udd0d Basic Filters")
    project_filter = st.multiselect("Filter by Source Project", options=basic_data.SourceProject.unique())
    if project_filter:
        basic_data = basic_data[basic_data.SourceProject.isin(project_filter)]

    st.dataframe(basic_data.head(), use_container_width=True)

# Once web events sheet is uploaded
if uploaded_file is not None:
    try:
        web_events = pd.read_excel(uploaded_file)
        st.success("Web Events sheet uploaded successfully")

        # Merge with basic data (assuming common column `masterLeadId`)
        if not basic_data.empty:
            if "masterLeadId" in web_events.columns and "masterLeadId" in basic_data.columns:
                merged = pd.merge(basic_data, web_events, on="masterLeadId", how="inner")

                st.subheader("\ud83d\udcca Merged Dashboard View")
                st.write(f"Total Merged Leads: {len(merged)}")
                st.dataframe(merged.head(), use_container_width=True)

                # Add your filters here as needed
                # Example: Score filter
                if "score" in merged.columns:
                    score_range = st.slider("Score Range", float(merged.score.min()), float(merged.score.max()), (float(merged.score.min()), float(merged.score.max())))
                    merged = merged[(merged.score >= score_range[0]) & (merged.score <= score_range[1])]

                # Call Duration
                if "call_duration" in merged.columns:
                    call_dur = st.slider("Call Duration (in sec)", 0, int(merged.call_duration.max()), (0, int(merged.call_duration.max())))
                    merged = merged[(merged.call_duration >= call_dur[0]) & (merged.call_duration <= call_dur[1])]

                st.dataframe(merged, use_container_width=True)
            else:
                st.error("Missing `masterLeadId` column in either sheet. Merge not possible.")

    except Exception as e:
        st.error(f"Error processing Web Events Sheet: {e}")

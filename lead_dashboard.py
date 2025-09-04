# Unified Dashboard using Public Google Sheet CSV URLs
# No service account needed

import streamlit as st
import pandas as pd
from datetime import datetime

# -------------------------
# Streamlit Page Setup
# -------------------------
st.set_page_config(page_title="📊 Unified Dashboard", layout="wide")
st.title("📊 Unified Lead + Web Events Dashboard")

# -------------------------
# Load Public Google Sheets as CSV
# -------------------------
@st.cache_data
def load_public_basic_sheets():
    urls = {
        "Broadway": "https://docs.google.com/spreadsheets/d/1smMVEgiadMWc5HB8TayEsai22qnFy1e5xKkoue3B3G8/export?format=csv",
        "Loft Part 1": "https://docs.google.com/spreadsheets/d/1RHg1ndf9JJpSL2hFFkzImtVsiX8-VE28ZEWPzmRzRg0/export?format=csv",
        "Loft Part 2": "https://docs.google.com/spreadsheets/d/13KF8bupHECjLqW5iyLvzEiZP7UY2gCESAgqLPSRy4fA/export?format=csv",
        "Spire": "https://docs.google.com/spreadsheets/d/1iOb3nml_6eOMm68vDKTi-3qe-PnwFbzspqKcNeDBrVU/export?format=csv",
        "Spectra": "https://docs.google.com/spreadsheets/d/1WlN3O8V5wpw1TJQpmc-GfVSmuu4GmKnJ5yMVMu0PQ5Y/export?format=csv",
        "Springs": "https://docs.google.com/spreadsheets/d/11bbM5p_Qotd-NZvD33CcepD5grdpI-0hiVi8JwNyeQs/export?format=csv",
        "Landmark": "https://docs.google.com/spreadsheets/d/1hmWBJMYCRmTajIr971kNZXgWcnMOY9kKkUpSK93WCwE/export?format=csv"
    }
    dfs = []
    for project, url in urls.items():
        try:
            df = pd.read_csv(url)
            df['Project'] = project
            dfs.append(df)
        except Exception as e:
            st.warning(f"Couldn't load {project}: {e}")
    return pd.concat(dfs, ignore_index=True)

basic_df = load_public_basic_sheets()
st.success(f"✅ Loaded {len(basic_df)} total leads from public sheets.")

# -------------------------
# Web Events Sheet Upload
# -------------------------
uploaded = st.file_uploader("📂 Upload Web Events Sheet", type="xlsx")
if uploaded:
    try:
        events_data = pd.read_excel(uploaded, sheet_name=None)
        web_df = events_data.get("Main")
        if web_df is None:
            st.error("Main sheet not found in uploaded file.")
        else:
            merged_df = basic_df.merge(web_df, on="masterLeadId", how="left")
            st.success(f"✅ Merged {len(merged_df)} rows.")

            # KPIs
            st.subheader("Web Engagement KPIs")
            time_cols = [c for c in merged_df.columns if c.endswith("Page Time")]
            merged_df['Page Depth'] = merged_df[time_cols].notna().sum(axis=1)
            merged_df['Total Time'] = merged_df[time_cols].sum(axis=1)
            if 'Last_Visit_Timestamp' in merged_df.columns:
                merged_df['Recency'] = pd.to_datetime(merged_df['Last_Visit_Timestamp'], errors='coerce')

            col1, col2, col3 = st.columns(3)
            col1.metric("Avg Page Depth", round(merged_df['Page Depth'].mean(), 2))
            col2.metric("Avg Total Time", round(merged_df['Total Time'].mean(), 2))
            if 'Recency' in merged_df.columns:
                latest = merged_df['Recency'].dropna().max()
                col3.metric("Most Recent Visit", latest.date() if pd.notna(latest) else "NA")

            # Filters
            st.sidebar.header("🔍 Filters")
            score_range = st.sidebar.slider("Score Range", 0.0, 1.0, (0.0, 1.0))
            micro = st.sidebar.multiselect("Micro Market", merged_df["Micro Market"].dropna().unique())
            call_dur = st.sidebar.slider("Min Call Duration", 0, 1000, 0)

            orange_only = st.sidebar.checkbox("🟠 Orange Leads Only")
            if orange_only:
                merged_df = merged_df[merged_df["Orange"] == True]

            # Apply Filters
            filtered = merged_df.copy()
            filtered = filtered[(filtered["Score"] >= score_range[0]) & (filtered["Score"] <= score_range[1])]
            filtered = filtered[filtered["Call Duration"] >= call_dur]
            if micro:
                filtered = filtered[filtered["Micro Market"].isin(micro)]

            st.subheader("Filtered Leads")
            st.dataframe(filtered, use_container_width=True)

    except Exception as e:
        st.error(f"Failed to process uploaded sheet: {e}")
else:
    st.info("Upload a Web Events file to proceed.")

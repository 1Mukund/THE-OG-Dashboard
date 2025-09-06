import streamlit as st
import pandas as pd
import re
import requests
from io import StringIO
from datetime import datetime
import plotly.express as px
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

st.set_page_config(page_title="Unified Lead + Web Events Dashboard", layout="wide")
st.title("📊 Unified Lead + Web Events Dashboard")

project_sheet_map = {
    "Broadway": "https://docs.google.com/spreadsheets/d/1smMVEgiadMWc5HB8TayEsai22qnFy1e5xKkoue3B3G8/export?format=csv",
    "Loft Part 1": "https://docs.google.com/spreadsheets/d/1RHg1ndf9JJpSL2hFFkzImtVsiX8-VE28ZEWPzmRzRg0/export?format=csv",
    "Loft Part 2": "https://docs.google.com/spreadsheets/d/13KF8bupHECjLqW5iyLvzEiZP7UY2gCESAgqLPSRy4fA/export?format=csv",
    "Spire": "https://docs.google.com/spreadsheets/d/1iOb3nml_6eOMm68vDKTi-3qe-PnwFbzspqKcNeDBrVU/export?format=csv",
    "Springs": "https://docs.google.com/spreadsheets/d/11bbM5p_Qotd-NZvD33CcepD5grdpI-0hiVi8JwNyeQs/export?format=csv",
    "Spectra": "https://docs.google.com/spreadsheets/d/1WlN3O8V5wpw1TJQpmc-GfVSmuu4GmKnJ5yMVMu0PQ5Y/export?format=csv",
    "Landmark": "https://docs.google.com/spreadsheets/d/1hmWBJMYCRmTajIr971kNZXgWcnMOY9kKkUpSK93WCwE/export?format=csv"
}

@st.cache_data(show_spinner=False)
def load_basic_sheet(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            df = pd.read_csv(StringIO(response.text))
            return df
        else:
            st.error("❌ Failed to fetch sheet.")
            return None
    except Exception as e:
        st.error(f"❌ Error: {e}")
        return None

st.subheader("Select Project")
selected_project = st.selectbox("Select Project", list(project_sheet_map.keys()))
sheet_url = project_sheet_map.get(selected_project)
basic_df = load_basic_sheet(sheet_url) if sheet_url else None

if basic_df is None:
    st.stop()

st.subheader("📤 Upload Web Events Sheet (.xlsx)")
uploaded_file = st.file_uploader("Upload Web Events Sheet", type=["xlsx"])

if uploaded_file:
    web_df = pd.read_excel(uploaded_file)
    basic_df.columns = basic_df.columns.str.strip()
    web_df.columns = web_df.columns.str.strip()

    if "masterLeadId" in basic_df.columns and "masterLeadId" in web_df.columns:
        merged_df = pd.merge(basic_df, web_df, on="masterLeadId", how="inner")
        st.success(f"✅ Merged {len(merged_df)} leads.")

        for col in merged_df.columns:
            if '_VIEW_events' in col or '_CLICK_events' in col:
                merged_df[col] = pd.to_numeric(merged_df[col], errors='coerce')

        merged_df["PageDepth"] = merged_df.filter(like="_VIEW_events").sum(axis=1, numeric_only=True)
        merged_df["TotalClickEvents"] = merged_df.filter(like="_CLICK_events").sum(axis=1, numeric_only=True)
        merged_df["AvgTimePerPage"] = merged_df["TotalTimeSpent"] / merged_df["PageDepth"]
        merged_df["AvgTimePerPage"] = merged_df["AvgTimePerPage"].fillna(0)

        if "Born Date_x" in merged_df.columns:
            merged_df["Born Date_x"] = pd.to_datetime(merged_df["Born Date_x"], errors="coerce")

        st.sidebar.header("🔍 Filters")
        for col in ["Stage_x", "Source_x", "NI Reason_x"]:
            if col in merged_df.columns:
                options = st.sidebar.multiselect(f"Filter by {col.replace('_x', '')}", merged_df[col].dropna().unique())
                if options:
                    merged_df = merged_df[merged_df[col].isin(options)]

        for col, label in {
            "callDuration(secs)": "Call Duration",
            "Lead Age (in Days)_x": "Lead Age",
            "PageDepth": "Page Depth",
            "TotalTimeSpent": "Total Time Spent"
        }.items():
            if col in merged_df.columns and merged_df[col].notna().any():
                min_val, max_val = merged_df[col].min(), merged_df[col].max()
                if not pd.isnull(min_val) and not pd.isnull(max_val) and min_val < max_val:
                    rng = st.sidebar.slider(label, float(min_val), float(max_val), (float(min_val), float(max_val)))
                    merged_df = merged_df[(merged_df[col] >= rng[0]) & (merged_df[col] <= rng[1])]

        if "Born Date_x" in merged_df.columns and merged_df["Born Date_x"].notna().any():
            min_date = merged_df["Born Date_x"].min().date()
            max_date = merged_df["Born Date_x"].max().date()
            date_range = st.sidebar.date_input("Born Date Range", [min_date, max_date])
            if len(date_range) == 2:
                merged_df = merged_df[(merged_df["Born Date_x"] >= pd.to_datetime(date_range[0])) & (merged_df["Born Date_x"] <= pd.to_datetime(date_range[1]))]

        st.subheader("📌 Merged Lead Data")
        st.dataframe(merged_df.head(500), use_container_width=True)

        st.subheader("📈 KPIs")
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Leads", len(merged_df))
        k2.metric("Avg Page Depth", round(merged_df["PageDepth"].mean(), 2))
        k3.metric("Avg Time/Page", round(merged_df["AvgTimePerPage"].mean(), 2))
        k4.metric("Total Click Events", int(merged_df["TotalClickEvents"].sum()))

        k5, k6, k7, k8 = st.columns(4)
        k5.metric("Avg Call Duration", round(merged_df["callDuration(secs)"].mean(), 2) if "callDuration(secs)" in merged_df.columns else 0)
        k6.metric("% Purple Leads", f"{round(100 * merged_df['Purple'].sum() / len(merged_df), 1)}%" if 'Purple' in merged_df.columns else "-")
        k7.metric("% Orange Leads", f"{round(100 * merged_df['Orange'].sum() / len(merged_df), 1)}%" if 'Orange' in merged_df.columns else "-")
        k8.metric("Avg Lead Age", round(merged_df["Lead Age (in Days)_x"].mean(), 1) if "Lead Age (in Days)_x" in merged_df.columns else 0)

        st.subheader("📊 Visuals")
        if "Stage_x" in merged_df.columns:
            stage_chart = merged_df["Stage_x"].value_counts().reset_index()
            st.plotly_chart(px.bar(stage_chart, x="index", y="Stage_x", title="Stage Distribution", labels={"index": "Stage", "Stage_x": "Count"}), use_container_width=True)

        if "Source_x" in merged_df.columns:
            source_chart = merged_df["Source_x"].value_counts().reset_index()
            st.plotly_chart(px.pie(source_chart, names="index", values="Source_x", title="Lead Source Share"), use_container_width=True)

        if "NI Reason_x" in merged_df.columns:
            ni_chart = merged_df["NI Reason_x"].value_counts().reset_index()
            st.plotly_chart(px.bar(ni_chart, x="index", y="NI Reason_x", title="NI Reason Distribution", labels={"index": "NI Reason", "NI Reason_x": "Count"}), use_container_width=True)

        if "callDuration(secs)" in merged_df.columns:
            st.plotly_chart(px.histogram(merged_df, x="callDuration(secs)", title="Call Duration Distribution"), use_container_width=True)

        if "PageDepth" in merged_df.columns and "TotalClickEvents" in merged_df.columns:
            st.plotly_chart(px.scatter(merged_df, x="PageDepth", y="TotalClickEvents", title="Page Depth vs Total Click Events"), use_container_width=True)

        if "Stage_x" in merged_df.columns and "AvgTimePerPage" in merged_df.columns:
            stage_time = merged_df.groupby("Stage_x")["AvgTimePerPage"].mean().reset_index()
            st.plotly_chart(px.bar(stage_time, x="Stage_x", y="AvgTimePerPage", title="Avg Time per Page by Stage"), use_container_width=True)

        st.subheader("🌡️ Heatmap: Time Spent per Page")
        heat_cols = [col for col in merged_df.columns if "_VIEW_events" in col]
        if heat_cols:
            heat_data = merged_df.groupby("Stage_x")[heat_cols].mean()
            fig, ax = plt.subplots(figsize=(10, 6))
            sns.heatmap(heat_data, annot=True, fmt=".1f", cmap="YlGnBu", ax=ax)
            st.pyplot(fig)

        st.subheader("📊 Conversion Funnel")
        funnel_data = merged_df["Stage_x"].value_counts().sort_index(ascending=False).reset_index()
        funnel_data.columns = ["Stage", "Count"]
        st.plotly_chart(px.funnel(funnel_data, x="Count", y="Stage", title="Stage-wise Conversion Funnel"), use_container_width=True)

        st.subheader("🧠 Lead Scoring & Intent Tagging")
        merged_df["LeadScore"] = (
            0.4 * merged_df["PageDepth"] +
            0.4 * merged_df["TotalClickEvents"] +
            0.2 * merged_df["callDuration(secs)"].fillna(0)
        )
        merged_df["IntentTag"] = pd.cut(
            merged_df["LeadScore"],
            bins=[-1, 10, 50, 100, float("inf")],
            labels=["Cold", "Warm", "Hot", "Very Hot"]
        )
        st.dataframe(merged_df[["masterLeadId", "LeadScore", "IntentTag"]].head(10), use_container_width=True)

        st.subheader("🔍 Lead Journey Tracker")
        lead_id = st.selectbox("Choose Lead ID", merged_df["masterLeadId"].unique())
        stage = st.selectbox("Choose Stage", merged_df["Stage_x"].unique())
        lead_row = merged_df[(merged_df["masterLeadId"] == lead_id) & (merged_df["Stage_x"] == stage)]
        view_cols = [col for col in lead_row.columns if '_VIEW_events' in col]
        click_cols = [col for col in lead_row.columns if '_CLICK_events' in col]
        journey_cols = ["Stage_x"] + view_cols + click_cols + ["TotalTimeSpent", "PageDepth", "LeadScore", "IntentTag"]
        st.dataframe(lead_row[journey_cols], use_container_width=True)

    else:
        st.error("❌ 'masterLeadId' column missing in either file.")
else:
    st.warning("📎 Upload web events sheet to continue.")

st.markdown("---")
st.markdown("<center><sub>✨ Built with ❤️ by Mukund for Growth Intelligence ✨</sub></center>", unsafe_allow_html=True)

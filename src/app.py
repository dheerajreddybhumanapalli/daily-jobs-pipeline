import sys
from pathlib import Path

# Ensure project root is in sys.path when running via `streamlit run src/app.py`
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import streamlit as st
import pandas as pd
import asyncio
from datetime import datetime

from src.db.storage import query_jobs, get_stats, get_db
from src.pipeline import run_pipeline

st.set_page_config(
    page_title="GCC & MNC Job Hunter - India / Hyderabad",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 15px;
        border-left: 5px solid #0066cc;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .badge-hyd {
        background-color: #e3f2fd;
        color: #0d47a1;
        padding: 3px 8px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85em;
    }
    .badge-india {
        background-color: #e8f5e9;
        color: #1b5e20;
        padding: 3px 8px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85em;
    }
    .job-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #111827;
        text-decoration: none;
    }
    .company-tag {
        color: #4b5563;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# Top Bar Header
st.title("💼 GCC & MNC Job Hunter (India & Hyderabad)")
st.caption("Zero-block, automated job aggregator fetching directly from official ATS boards (Greenhouse, Lever, Ashby) and public job APIs.")

# Sidebar Controls
st.sidebar.header("🎯 Filters & Search")

search_kw = st.sidebar.text_input("Role / Keyword", placeholder="e.g. Software Engineer, Data, Frontend, Analyst")
location_filter = st.sidebar.radio("Location Filter", ["Hyderabad Only", "All India", "Worldwide (All)"], index=0)

hyd_only = (location_filter == "Hyderabad Only")
india_only = (location_filter == "All India")

# Source / Company filters
db = get_db()
companies = sorted([row["company"] for row in db.query("SELECT DISTINCT company FROM jobs") if row["company"]])
selected_company = st.sidebar.selectbox("Filter by Company", ["All Companies"] + companies)

sources = sorted([row["source"] for row in db.query("SELECT DISTINCT source FROM jobs") if row["source"]])
selected_source = st.sidebar.selectbox("Filter by Source ATS/API", ["All Sources"] + sources)

st.sidebar.divider()
st.sidebar.subheader("⚡ Live Sync Pipeline")
scrape_button = st.sidebar.button("🔄 Fetch Latest Jobs Now", use_container_width=True)

if scrape_button:
    with st.spinner("Scraping ATS endpoints & job APIs concurrently without bans..."):
        stats = asyncio.run(run_pipeline(role_filter=None))
        st.sidebar.success(f"Fetched {stats['fetched_total']} total jobs! ({stats['india_jobs']} India, {stats['hyderabad_jobs']} Hyderabad)")
        st.rerun()

# Overview Metrics
stats = get_stats()
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Total Jobs Tracked", stats["total"])
with col2:
    st.metric("India Openings", stats["india"])
with col3:
    st.metric("Hyderabad Openings", stats["hyderabad"])
with col4:
    st.metric("Companies Monitored", stats["companies"])

st.markdown("---")

# Query jobs
jobs_data = query_jobs(
    search_query=search_kw,
    india_only=india_only,
    hyderabad_only=hyd_only,
    company=None if selected_company == "All Companies" else selected_company,
    source=None if selected_source == "All Sources" else selected_source,
    limit=500
)

# Display Jobs
if not jobs_data:
    st.info("No jobs match your current search criteria. Try broadening your keywords or clicking **'Fetch Latest Jobs Now'** in the sidebar!")
else:
    st.subheader(f"Results ({len(jobs_data)} positions found)")
    
    # Export options
    df = pd.DataFrame(jobs_data)
    export_df = df[["company", "title", "location", "source", "job_type", "url", "posted_date"]]
    
    c_csv, c_json = st.columns([1, 1])
    with c_csv:
        csv_data = export_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Results as CSV",
            data=csv_data,
            file_name=f"jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv",
        )
    with c_json:
        json_data = export_df.to_json(orient="records", indent=2).encode('utf-8')
        st.download_button(
            label="📥 Download Results as JSON",
            data=json_data,
            file_name=f"jobs_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
        )

    # Job listing view
    for job in jobs_data:
        with st.container(border=True):
            cols = st.columns([4, 1])
            with cols[0]:
                st.markdown(f"### [{job['title']}]({job['url']})")
                tag_hyd = "<span class='badge-hyd'>📍 Hyderabad</span> " if job.get("is_hyderabad") else ""
                tag_ind = "<span class='badge-india'>🇮🇳 India</span> " if (job.get("is_india") and not job.get("is_hyderabad")) else ""
                st.markdown(
                    f"**Company:** `{job['company']}` | **Location:** {job['location']} {tag_hyd}{tag_ind} | **Source:** `{job['source']}`",
                    unsafe_allow_html=True
                )
                if job.get("posted_date"):
                    st.caption(f"Posted/Updated: {job['posted_date']}")
            with cols[1]:
                st.link_button("Apply Directly ↗", job['url'], use_container_width=True)


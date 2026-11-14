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
from src.config.companies import (
    CURATED_BOARDS,
    add_discovered_companies,
    get_all_companies,
)
from src.scrapers.discovery import ATS_SPECS, discover_boards

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

search_kw = st.sidebar.text_input(
    "Role / Keyword",
    placeholder="e.g. AI, Data Eng, Frontend, Analyst",
    help=(
        "Partial, case-insensitive search. Try 'AI' for AI Engineer, GenAI or AI/ML roles, "
        "or 'data eng' for Data Engineer openings."
    ),
)
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

st.sidebar.divider()
st.sidebar.subheader("🏢 Monitored Boards")

_message = st.session_state.pop("board_message", None)
if _message:
    _level, _text = _message
    getattr(st.sidebar, _level, st.sidebar.info)(_text)

boards = get_all_companies()
curated_total = sum(len(items) for items in CURATED_BOARDS.values())
active_total = sum(len(items) for items in boards.values())
st.sidebar.caption(
    f"Greenhouse {len(boards['greenhouse'])} · Lever {len(boards['lever'])} · "
    f"Ashby {len(boards['ashby'])} · Workable {len(boards['workable'])}"
)
st.sidebar.caption(f"{active_total} boards total ({active_total - curated_total} discovered)")

with st.sidebar.expander(
    "🔎 Discover companies to add",
    expanded=bool(st.session_state.get("discovery_result")),
):
    st.caption(
        "Checks public Greenhouse, Lever and Ashby boards. Nothing is added "
        "until you select companies and confirm."
    )
    ats_choices = st.multiselect(
        "Search these ATS boards",
        options=list(ATS_SPECS),
        default=list(ATS_SPECS),
        format_func=str.title,
    )
    tokens_per_ats = st.slider("Boards to check per ATS", 10, 200, 40, 10)

    if st.button("🔍 Find companies", use_container_width=True):
        if not ats_choices:
            st.session_state["board_message"] = (
                "warning",
                "Select at least one ATS board to search.",
            )
        else:
            with st.spinner("Checking public boards..."):
                try:
                    result = asyncio.run(
                        discover_boards(
                            ats_sources=ats_choices,
                            max_candidates_per_ats=tokens_per_ats,
                            offsets=st.session_state.get("discovery_offsets", {}),
                        )
                    )
                    st.session_state["discovery_result"] = result
                    st.session_state["discovery_offsets"] = result.get("next_offsets", {})
                    found = result.get("candidates_total", 0)
                    if found:
                        st.session_state["board_message"] = (
                            "success",
                            f"Found {found} live companies. Select the ones to add.",
                        )
                    else:
                        st.session_state["board_message"] = (
                            "info",
                            "No new live companies in this batch. Run discovery again for the next batch.",
                        )
                except Exception as exc:
                    st.session_state.pop("discovery_result", None)
                    st.session_state["board_message"] = (
                        "error",
                        f"Discovery failed: {exc}. Existing boards were not changed.",
                    )
        st.rerun()

    discovery = st.session_state.get("discovery_result")
    if discovery:
        for error in discovery.get("errors", []):
            st.warning(error)

        options = []
        lookup = {}
        for ats, info in discovery["by_ats"].items():
            for board in info.get("candidates", []):
                label = (
                    f"{board['name']} · {ats} · {board['token']} "
                    f"({board['jobs']} job{'s' if board['jobs'] != 1 else ''})"
                )
                options.append(label)
                lookup[label] = {"ats": ats, **board}

        if options:
            selected = st.multiselect("Select companies to add", options=options)
            if st.button("➕ Add selected companies", use_container_width=True):
                if not selected:
                    st.warning("Select at least one company first.")
                else:
                    selections = {}
                    for label in selected:
                        record = lookup[label]
                        selections.setdefault(record["ats"], []).append(record)
                    try:
                        summary = add_discovered_companies(selections)
                    except Exception as exc:
                        st.session_state["board_message"] = (
                            "error",
                            f"Could not save companies: {exc}. Existing boards were not changed.",
                        )
                    else:
                        parts = []
                        if summary["added_count"]:
                            parts.append(f"{summary['added_count']} added")
                        if summary["updated_count"]:
                            parts.append(f"{summary['updated_count']} updated")
                        if summary["unchanged_count"]:
                            parts.append(f"{summary['unchanged_count']} already configured")
                        if summary["invalid_count"]:
                            parts.append(f"{summary['invalid_count']} invalid")
                        detail = (": " + ", ".join(parts)) if parts else ""
                        if summary["added_count"] or summary["updated_count"]:
                            message = "Board list updated" + detail + "."
                            level = "success"
                        else:
                            message = "No changes" + detail + "."
                            level = "warning" if summary["invalid_count"] else "info"
                        st.session_state["board_message"] = (level, message)
                        st.session_state.pop("discovery_result", None)
                    st.rerun()
        else:
            st.info("No new live companies in this batch. Run discovery again to check more.")

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
    if search_kw and search_kw.strip():
        st.subheader(f"Results for “{search_kw.strip()}” ({len(jobs_data)} positions found)")
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


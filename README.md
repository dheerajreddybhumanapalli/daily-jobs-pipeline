# GCC & MNC Job Hunter (India & Hyderabad) 💼🇮🇳

An end-to-end job fetching and tracking application built to collect open jobs for your target roles from Global Capability Centers (GCCs), Big MNCs, and Tech Giants **completely free and without getting blocked or IP banned**.

---

## 💡 How It Avoids Getting Blocked (Zero-Block Architecture)
Traditional scrapers scrape HTML from sites like LinkedIn, Indeed, or Glassdoor, which employ aggressive Cloudflare WAF, CAPTCHAs, and IP rate limits.

This pipeline eliminates ban risk entirely by querying:
1. **Direct Public ATS APIs**: High-volume, official JSON endpoints powering company career sites (**Greenhouse**, **Lever**, and **Ashby**). Companies intentionally leave these open for candidate applications.
2. **Free Public Job Aggregator APIs**: Official public feeds (**Jobicy**, **Arbeitnow**) with no ban mechanisms.
3. **Async Rate-Limiter with Semaphores & Polite User-Agents**: Built using `httpx` async client with automatic concurrency throttling and exponential backoff.

---

## 🚀 Features
- **Targeted for India & Hyderabad**: Automatically detects Hyderabad and India-wide openings from GCCs and MNCs (e.g., Coinbase, Stripe, Notion, Databricks, Snowflake, Palantir, Cloudflare, etc.).
- **Deduplication Engine**: Uses SQLite FTS and SHA-256 fingerprinting to prevent duplicate job entries across multiple runs.
- **Interactive Streamlit Web Dashboard**:
  - Filter by Role keyword with **partial, case-insensitive matching** (e.g. *AI* finds *AI Engineer*, *GenAI* and *AI/ML* roles; *Data Eng* finds *Data Engineer* roles).
  - Quick location toggle: **Hyderabad Only**, **All India**, or **Worldwide**.
  - Filter by Company or ATS source.
  - One-click live fetch: Trigger fresh pipeline runs directly from the UI.
  - **Exporting**: Download filtered jobs as **CSV** or **JSON** for offline application tracking.

---

## 🛠️ Quick Start

### 1. Run the Web Dashboard
```bash
uv run streamlit run src/app.py
```
Or with plain python:
```bash
streamlit run src/app.py
```
Open [http://localhost:8501](http://localhost:8501) in your browser.

> **Note**: A local `.streamlit/` configuration has been pre-configured in this repository (`headless = true`, `gatherUsageStats = false`, and an initialized credentials file) to prevent interactive email prompt blocks and permission errors when starting Streamlit.

### 2. Run the Fetch Pipeline via CLI (or Cron / Task Scheduler)
To run a background fetch without opening the web UI:
```bash
uv run python -m src.pipeline
```

---

## 🏢 Adding More Companies
You can easily add any company using Greenhouse, Lever, or Ashby by adding their token in [`src/config/companies.py`](file:///d:/github/daily-jobs-pipeline/src/config/companies.py):
```python
GREENHOUSE_COMPANIES.append({"name": "Company Name", "token": "board_token"})
```


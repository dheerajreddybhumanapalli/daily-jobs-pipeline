# GCC & MNC Job Hunter (India & Hyderabad) 💼🇮🇳

An end-to-end job fetching and tracking application built to collect open jobs
for your target roles from Global Capability Centers (GCCs), Big MNCs, and tech
companies — **without scraping LinkedIn/Indeed, and without API keys or paid
services.**

It pulls jobs from official company ATS boards and free public job APIs, stores
everything in a local SQLite database, and serves a Streamlit dashboard for
searching, filtering, and exporting results.

---

## How it avoids getting blocked

Traditional scrapers parse HTML from sites like LinkedIn, Indeed, or Glassdoor,
which use aggressive WAFs, CAPTCHAs, and IP rate limits. This project avoids
that entirely:

1. **Official public ATS APIs** — the same JSON endpoints that power company
   career pages: **Greenhouse**, **Lever**, and **Ashby**. These are intentionally
   public and meant to be consumed.
2. **Free public job aggregator APIs** — **Jobicy** and **Arbeitnow**, with no
   authentication and no ban mechanisms.
3. **Bounded async concurrency** — an `httpx.AsyncClient` runs requests through
   an `asyncio.Semaphore(10)` with a small jitter, polite User-Agent headers,
   and per-request timeouts. A failing board is skipped instead of retried
   aggressively.

There is no retry/backoff loop: a failed request returns no jobs and the next
scheduled run tries again.

---

## Features

- **India & Hyderabad targeting** — classifies openings using location and title
  keywords, with Hyderabad-specific badges in the UI.
- **Multiple sources** — 22 Greenhouse boards, 4 Lever boards, 10 Ashby boards,
  plus Jobicy and Arbeitnow feeds (configurable in
  [`src/config/companies.py`](src/config/companies.py)).
- **Deduplication** — stable per-source job IDs (ATS-native IDs where available,
  SHA-256 fingerprints otherwise) are the SQLite primary key; re-runs upsert
  instead of duplicating.
- **Token-aware role search** — `AI` matches *AI Engineer*, *GenAI*, and
  *AI/ML* without matching *Affairs* or *Spain*; `data eng` matches
  *Senior Data Platform Engineer*. See [docs/configuration.md](docs/configuration.md#role-search-behavior).
- **Streamlit dashboard** — filters for role keyword, location
  (*Hyderabad Only* / *All India* / *Worldwide*), company, and source; metrics;
  one-click live fetch; CSV/JSON export.
- **Local-first** — one SQLite file (`jobs.db`), no server, no accounts, no
  credentials.

---

## Requirements

- **Python 3.12+** (see `.python-version`)
- **[uv](https://docs.astral.sh/uv/)** for dependency management (recommended;
  `uv.lock` is committed)
- Network access to the job APIs

If you prefer not to use uv, install the dependencies listed in `pyproject.toml`
into an activated virtualenv; the commands below use `uv`.

---

## Setup

```bash
git clone <repository-url>
cd daily-jobs-pipeline
uv sync
```

`uv sync` creates `.venv/` and installs the locked dependencies.

All commands should be run from the repository root: the database path
(`jobs.db`) is relative to the current working directory.

---

## Usage

### Run the dashboard

```bash
uv run streamlit run src/app.py
```

Open <http://localhost:8501>. If you prefer plain Python with an activated
virtualenv:

```bash
streamlit run src/app.py
```

The sidebar has filters, a **Fetch Latest Jobs Now** button that runs the
pipeline in-process, and CSV/JSON download buttons for the current result set.
The default view is **Hyderabad Only**, limited to the 500 most recent matches.

> Streamlit may ask for an email address the first time it runs interactively.
> Set `STREAMLIT_BROWSER_GATHER_USAGE_STATS=false` or create a local
> `.streamlit/config.toml` (gitignored) to suppress it. No Streamlit config is
> committed to the repository.

### Run the fetch pipeline

```bash
uv run python -m src.pipeline
```

This fetches from every configured source, classifies locations, upserts results
into `jobs.db`, and prints a summary. The command accepts **no flags**; the
pipeline is configured in code (see [docs/configuration.md](docs/configuration.md)).

### Programmatic use

```python
import asyncio
from src.pipeline import run_pipeline

stats = asyncio.run(run_pipeline(role_filter="data engineer"))
print(stats)
```

`run_pipeline()` returns:

```python
{
    "fetched_total": 1234,      # jobs returned by all sources
    "matched_criteria": 56,     # jobs remaining after role_filter
    "saved_upserted": 56,       # records upserted (not necessarily new)
    "india_jobs": 40,
    "hyderabad_jobs": 12,
}
```

---

## Configuration

The two files you are most likely to edit:

| File | Purpose |
| --- | --- |
| [`src/config/companies.py`](src/config/companies.py) | ATS board tokens and India/Hyderabad keyword lists |
| [`src/db/storage.py`](src/db/storage.py) | SQLite path (`DB_PATH = Path("jobs.db")`) |

Add a company by appending its public board token:

```python
GREENHOUSE_COMPANIES.append({"name": "Company Name", "token": "board_token"})
```

Full details — adding companies, adding a new ATS source, tuning concurrency,
search semantics, and all runtime options — are in
[docs/configuration.md](docs/configuration.md).

---

## Project structure

```
src/
  app.py                    Streamlit dashboard
  pipeline.py               Async orchestration and summary stats
  config/companies.py       Board tokens + location keywords
  db/models.py              JobItem schema
  db/storage.py             SQLite create/upsert/query/stats
  db/search.py              Token-aware partial role matching
  scrapers/                 Greenhouse, Lever, Ashby, Jobicy, Arbeitnow adapters
docs/                       Architecture, configuration, operations
AGENTS.md                   Contributor/agent guidance
```

## Data

- `jobs.db` is created automatically in the working directory on first use.
- It is gitignored; it contains only public job postings.
- Table `jobs` is keyed by `id`, with an FTS index on title, company, location,
  and description.
- Re-running the pipeline updates existing rows and adds new ones. Closed
  postings are **not** deleted automatically.

See [docs/operations.md](docs/operations.md) for backup, reset, and inspection
commands.

---

## Documentation

- [docs/README.md](docs/README.md) — documentation index
- [docs/architecture.md](docs/architecture.md) — pipeline flow, modules, data model
- [docs/configuration.md](docs/configuration.md) — sources, keywords, runtime options
- [docs/operations.md](docs/operations.md) — setup, scheduling, troubleshooting
- [AGENTS.md](AGENTS.md) — repository conventions for contributors and coding agents

---

## Known limitations

- ATS board tokens can change or disappear; such boards return 404 and are
  skipped for that run. Check the endpoint before reporting a missing company.
- There is no retry/backoff and no pagination beyond each API's defaults.
- No tests, linter, or CI are configured yet.
- `WORKABLE_COMPANIES` is present in the config but **not wired into the
  pipeline**.
- The `daily-jobs-pipeline` console script in `pyproject.toml` is a placeholder;
  use `python -m src.pipeline` instead.
- Descriptions are truncated to 2,000 characters where the source provides one,
  and salary is not populated by any current adapter.

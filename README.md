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
- **Opt-in company discovery** — search public Greenhouse, Lever, and Ashby
  boards, then add only the companies you select. Nothing is added
  automatically, repeated selections are idempotent, and a failed discovery
  never changes existing configuration.
- **Deduplication** — stable per-source job IDs (ATS-native IDs where available,
  SHA-256 fingerprints otherwise) are the SQLite primary key; re-runs upsert
  instead of duplicating.
- **Token-aware role search** — `AI` matches *AI Engineer*, *GenAI*, and
  *AI/ML* without matching *Affairs* or *Spain*; `data eng` matches
  *Senior Data Platform Engineer*. See
  [docs/configuration.md](docs/configuration.md#role-search-behavior).
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
pipeline in-process, a **Discover companies to add** panel, and CSV/JSON
download buttons for the current result set. The default view is
**Hyderabad Only**, limited to the 500 most recent matches.

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
pipeline is configured in code and the discovered-board cache (see
[docs/configuration.md](docs/configuration.md)).

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

## Supported sources

| ATS / API | Endpoint | Configured boards |
| --- | --- | --- |
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/{token}/jobs` | 22 |
| Lever | `https://api.lever.co/v0/postings/{token}?mode=json` | 4 |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/{token}` | 10 |
| Workable | `https://apply.workable.com/api/v3/accounts/{token}/jobs` | 2 (not fetched yet) |
| Jobicy | `https://jobicy.com/api/v2/remote-jobs` | feed |
| Arbeitnow | `https://www.arbeitnow.com/api/job-board-api` | feed |

The curated boards live in
[`src/config/companies.py`](src/config/companies.py). Workable tokens are
present but no Workable adapter is wired into the pipeline.

---

## Add a company

### Option 1 — Curated list (always active)

Append a known board token to the matching list in
[`src/config/companies.py`](src/config/companies.py):

```python
GREENHOUSE_COMPANIES.append({"name": "Company Name", "token": "board_token"})
```

Confirm the endpoint responds before relying on it:

```bash
uv run python -c "import httpx; r=httpx.get('https://boards-api.greenhouse.io/v1/boards/<token>/jobs', timeout=15); print(r.status_code, len(r.json().get('jobs', [])))"
```

### Option 2 — Discover companies from public boards (opt-in)

ATS APIs are per-company, so discovery reads a public token index, validates
each candidate against the live API, and shows only boards that currently have
jobs.

From the dashboard:

1. Open **🏢 Monitored Boards** → **🔎 Discover companies to add**.
2. Choose the ATS boards to search and how many tokens to check per ATS.
3. Click **Find companies**.
4. Select the companies you want in the **Select companies to add** list.
5. Click **Add selected companies**.

From the CLI:

```bash
# List validated candidates only. This does not change configuration.
uv run python -m src.discover_boards

# Search fewer tokens or continue from a different offset.
uv run python -m src.discover_boards --ats greenhouse,lever --candidates 50 --offset 100

# Add only the companies you explicitly select.
uv run python -m src.discover_boards --add greenhouse=stripe --add lever=palantir
```

Selection guarantees:

- Only selected companies are written; discovery by itself is read-only.
- Selecting a company that is already configured is a no-op, not a duplicate.
- Existing curated entries are never modified.
- Writes are atomic and refuse to overwrite a malformed
  `src/config/discovered_boards.json`.
- A network or index failure leaves the existing configuration untouched and is
  reported in the UI or CLI.
- The discovery cache is gitignored. Delete it to return to the curated list
  only.

Full details are in [docs/configuration.md](docs/configuration.md).

---

## Project structure

```
src/
  app.py                    Streamlit dashboard
  pipeline.py               Async orchestration and summary stats
  discover_boards.py        Opt-in discovery CLI
  config/companies.py       Curated boards, discovery cache merge/save, keywords
  db/models.py              JobItem schema
  db/storage.py             SQLite create/upsert/query/stats
  db/search.py              Token-aware partial role matching
  scrapers/discovery.py     Board index loading and live token validation
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
- [docs/configuration.md](docs/configuration.md) — sources, discovery, runtime options
- [docs/operations.md](docs/operations.md) — setup, scheduling, troubleshooting
- [AGENTS.md](AGENTS.md) — repository conventions for contributors and coding agents

---

## Known limitations

- ATS board tokens can change or disappear; such boards return 404 and are
  skipped for that run. Check the endpoint before reporting a missing company.
- Discovery depends on a public, community-maintained token index. If the index
  is unavailable, the workflow reports an error and configured boards keep
  working.
- There is no retry/backoff and no pagination beyond each API's defaults.
- No tests, linter, or CI are configured yet.
- `WORKABLE_COMPANIES` is present in the config but **not wired into the
  pipeline**.
- The `daily-jobs-pipeline` console script in `pyproject.toml` is a placeholder;
  use `python -m src.pipeline` instead.
- Descriptions are truncated to 2,000 characters where the source provides one,
  and salary is not populated by any current adapter.

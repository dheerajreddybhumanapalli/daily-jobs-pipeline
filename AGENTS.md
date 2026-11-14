# AGENTS.md

Guidance for contributors and coding agents working on **daily-jobs-pipeline**.

## What this project is

An async Python job-aggregation pipeline plus a Streamlit dashboard. It fetches
public job listings from official ATS JSON APIs (Greenhouse, Lever, Ashby) and
free job APIs (Jobicy, Arbeitnow), classifies India/Hyderabad roles, and upserts
them into a local SQLite database (`jobs.db`). The dashboard queries that
database and can trigger a live fetch.

There is **no web backend, no authentication, and no required environment
variables**. Everything runs locally.

## Requirements

- Python **3.12+** (`.python-version` pins 3.12; `pyproject.toml` requires `>=3.12`)
- [uv](https://docs.astral.sh/uv/) (recommended; `uv.lock` is committed)
- Network access to the public job APIs

## Commands

Run all commands from the **repository root** — the database path is relative to
the current working directory.

| Task | Command |
| --- | --- |
| Install/sync dependencies | `uv sync` |
| Run the dashboard | `uv run streamlit run src/app.py` |
| Run the fetch pipeline | `uv run python -m src.pipeline` |
| Run a module as a script | `uv run python -m src.<module>` |
| Syntax-check all sources | `uv run python -m compileall -q src` |
| Upgrade locked dependencies | `uv lock --upgrade` |

Notes:

- The dashboard listens on <http://localhost:8501> by default. Override with
  `--server.port 8502` or set `headless` via a local `.streamlit/config.toml`.
- `python -m src.pipeline` accepts **no CLI flags**. Configure a run by calling
  `run_pipeline(...)` from Python or by editing `src/config/companies.py`.
- `src/app.py` inserts the project root into `sys.path`, so it must be launched
  as `streamlit run src/app.py` (not imported by another package).
- Do not use the `daily-jobs-pipeline` console script from `pyproject.toml`; it
  currently points at a placeholder `daily_jobs_pipeline:main` that only prints
  a greeting.

## Repository layout

```
src/
  app.py                    Streamlit UI: filters, metrics, CSV/JSON export, live fetch
  pipeline.py               Async orchestration, concurrency limits, save + summary stats
  config/companies.py       ATS board tokens, location keyword lists (edit targets here)
  db/models.py              Pydantic JobItem schema
  db/storage.py             SQLite schema creation, upsert, query, stats
  db/search.py              Token-aware partial role matcher (also registered in SQLite)
  scrapers/utils.py         Job ID hashing, location classification, user agents
  scrapers/greenhouse.py    Greenhouse ATS adapter
  scrapers/lever.py         Lever ATS adapter
  scrapers/ashby.py         Ashby ATS adapter
  scrapers/free_apis.py     Jobicy + Arbeitnow adapters
  daily_jobs_pipeline/      Packaging placeholder
docs/                       Architecture, configuration, and operations guides
```

`jobs.db` is created at runtime in the working directory and is **gitignored**.
`.venv/` and `.streamlit/` are also gitignored.

## Architecture in one paragraph

`run_pipeline()` creates one `httpx.AsyncClient`, builds one task per company
board plus one task per free API, and runs them through an
`asyncio.Semaphore(10)` with a 50 ms jitter before each request. Each adapter
returns `list[JobItem]`, swallowing per-board HTTP/parse errors and returning an
empty list. Results are optionally filtered with `partial_match()` against the
job title, then `save_jobs()` performs `upsert_all` keyed on `JobItem.id`. The
dashboard calls `run_pipeline(role_filter=None)` for live sync and otherwise
reads through `query_jobs()`.

See [docs/architecture.md](docs/architecture.md) for the full flow and schema,
[docs/configuration.md](docs/configuration.md) for settings and recipes, and
[docs/operations.md](docs/operations.md) for running and troubleshooting.

## Conventions

- **Imports are absolute** from the project root: `from src.db.models import JobItem`.
  Do not use relative imports across `src.*` subpackages.
- **New scrapers** must use the async signature
  `(client: httpx.AsyncClient, company: dict[str, str]) -> list[JobItem]` for ATS
  boards, or `(client, ...)` for API-wide feeds, and must:
  1. Build a deterministic ID (reuse the source's native ID when available;
     otherwise call `make_job_id`).
  2. Call `check_location(location, title)` for `is_india` / `is_hyderabad`.
  3. Catch exceptions, log at `debug` with the company name, and return `[]` so
     one failing board cannot abort the pipeline.
  4. Use a polite `USER_AGENTS` entry and a 12 s request timeout.
- **Wire every new source into `src/pipeline.py`** behind an `include_*` flag and
  export it through the returned stats dict. The dashboard's source filter is
  populated from the database, so no UI change is needed.
- **Schema changes** must update all of: `JobItem` (`db/models.py`), the table
  definition in `get_db()` (`db/storage.py`), the FTS column list if the field
  should be searchable, and both `save_jobs()` / `query_jobs()` if relevant.
  There are no migrations — delete `jobs.db` to recreate it.
- **Search:** use `partial_match()` (token-aware) rather than `LIKE '%...%'`.
  It deliberately avoids substring false positives such as `AI` matching
  `Affairs`. It is registered as a SQLite UDF in `get_db()`.
- **Job IDs are the deduplication key.** Do not change an ID scheme casually; a
  changed formula re-inserts existing jobs as new rows. IDs are permanent per
  source posting (native ID) or per (source, company, title, location, URL) when
  the fallback hash is used.
- **Keep docs and commands in sync.** If you change a command, path, default, or
  config location, update `README.md` and the relevant file under `docs/`.
- Match the existing style: typed function signatures, short docstrings, `rich`
  only in the CLI entry point, and no extra dependencies unless necessary.

## Adding a company (most common change)

1. Find the company's public board token (the slug in its careers URL).
2. Append `{"name": "...", "token": "..."}` to the matching list in
   `src/config/companies.py`: `GREENHOUSE_COMPANIES`, `LEVER_COMPANIES`, or
   `ASHBY_COMPANIES`.
3. Verify the endpoint directly, e.g.
   `https://boards-api.greenhouse.io/v1/boards/<token>/jobs`.
4. Run `uv run python -m src.pipeline` and confirm the company appears in
   `SELECT DISTINCT company FROM jobs`.

`WORKABLE_COMPANIES` exists in the config but **no Workable scraper is wired
into the pipeline**. Adding one requires a new adapter and pipeline task; do not
assume the existing list is active.

## Verification (no test suite exists)

There are currently no tests, linters, or CI. Before finishing a change:

```bash
uv run python -m compileall -q src
uv run python -c "from src.pipeline import run_pipeline; from src.db.storage import query_jobs, get_stats; from src.db.search import partial_match; print('imports ok')"
uv run python -c "from src.db.search import partial_match; assert partial_match('AI', 'GenAI Engineer'); assert not partial_match('AI', 'Business Affairs'); print('search ok')"
```

Then exercise the affected path:

- Pipeline change: `uv run python -m src.pipeline`
- UI change: `uv run streamlit run src/app.py` and load the page
- DB change: run a fetch and check `get_stats()` / `query_jobs()` output

If you add tests, put them under `tests/`, add `pytest` as a dev dependency
(`uv add --dev pytest`), and document the command in `README.md` and here.

## Do not commit

- `jobs.db` (local data, gitignored)
- `.venv/`, `.streamlit/`, `__pycache__/`
- Credentials or personal data

## Known quirks

- No retry/backoff logic exists. A failed request is skipped; rerun to retry.
- `save_jobs()` reports records processed, not rows newly inserted (`upsert_all`
  updates existing primary keys). `created_at` is refreshed on every upsert, so
  it behaves like "last seen" rather than "first seen".
- Removed/closed postings are never deleted from `jobs.db`.
- The FTS index on `jobs` is created but `query_jobs()` performs role search
  with the `partial_match` UDF, not FTS.
- `python-dotenv` is a declared dependency but nothing loads `.env` files yet.
- Board tokens can go stale (404); the pipeline keeps going and logs at `INFO`
  for HTTP status via `httpx`.

# Configuration

Everything is configured in code or with command-line options to Streamlit.
There are **no environment variables, secrets, or config files required**.

Run all commands from the repository root so relative paths resolve correctly.

## Where settings live

| Setting | Location | Current value |
| --- | --- | --- |
| ATS companies | `src/config/companies.py` | 22 Greenhouse, 4 Lever, 10 Ashby |
| Location keywords | `src/config/companies.py` | `HYDERABAD_KEYWORDS`, `INDIA_KEYWORDS` |
| Database path | `src/db/storage.py` | `DB_PATH = Path("jobs.db")` |
| Concurrency | `run_pipeline()` in `src/pipeline.py` | `asyncio.Semaphore(10)`, 50 ms jitter |
| HTTP limits | `run_pipeline()` in `src/pipeline.py` | 20 keep-alive / 30 max connections, 15 s client timeout |
| Per-request timeout | Each adapter | 12 s |
| Dashboard result cap | `src/app.py` | `limit=500` |
| Default location view | `src/app.py` | `Hyderabad Only` |
| Search thresholds | `src/db/search.py` | prefix length 3, compact length 4 |
| Python version | `.python-version`, `pyproject.toml` | 3.12, `>=3.12` |

## Sources

### Greenhouse (22 boards)

Public endpoint: `https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true`

```python
GREENHOUSE_COMPANIES = [
    {"name": "Stripe", "token": "stripe"},
    {"name": "Coinbase", "token": "coinbase"},
    # ...
]
```

### Lever (4 boards)

Public endpoint: `https://api.lever.co/v0/postings/{token}?mode=json`

```python
LEVER_COMPANIES = [
    {"name": "Palantir", "token": "palantir"},
    {"name": "FullStory", "token": "fullstory"},
    {"name": "Affirm", "token": "affirm"},
    {"name": "Coursera", "token": "coursera"},
]
```

### Ashby (10 boards)

Public endpoint: `https://api.ashbyhq.com/posting-api/job-board/{token}`

```python
ASHBY_COMPANIES = [
    {"name": "Ramp", "token": "ramp"},
    {"name": "Notion", "token": "notion"},
    # ...
]
```

### Jobicy and Arbeitnow (no company list)

- Jobicy: `https://jobicy.com/api/v2/remote-jobs?count=50` (optionally `&tag=<role_filter>`
  when a role filter is passed to the pipeline).
- Arbeitnow: `https://www.arbeitnow.com/api/job-board-api` (first page only).

### Workable (configured, not active)

`WORKABLE_COMPANIES` lists two boards but **no Workable adapter exists and no
task is created** in `run_pipeline()`. Editing that list has no effect until a
scraper is implemented.

## Add a company

1. Identify the ATS and board token. The token is the slug in the public careers
   URL, for example:
   - `boards.greenhouse.io/<token>`
   - `jobs.lever.co/<token>`
   - `jobs.ashbyhq.com/<token>`
2. Confirm the JSON endpoint responds with jobs before editing code:

   ```bash
   uv run python -c "import httpx; u='https://boards-api.greenhouse.io/v1/boards/<token>/jobs'; r=httpx.get(u, timeout=15); print(r.status_code, len(r.json().get('jobs', [])))"
   ```

3. Append to the correct list in `src/config/companies.py`:

   ```python
   GREENHOUSE_COMPANIES.append({"name": "Company Name", "token": "board_token"})
   ```

4. Run `uv run python -m src.pipeline` and confirm the company appears:

   ```bash
   uv run sqlite-utils jobs.db "select company, count(*) from jobs where company = 'Company Name' group by company"
   ```

If the board returns 404, the token is wrong, the company moved ATS, or the
board is private. The pipeline skips it without failing.

## Add a new ATS or job API

1. Create `src/scrapers/<name>.py` with an async function returning
   `list[JobItem]`:

   ```python
   import httpx
   from src.db.models import JobItem
   from src.scrapers.utils import make_job_id, check_location, USER_AGENTS

   async def fetch_example_jobs(client: httpx.AsyncClient, company: dict) -> list[JobItem]:
       ...
   ```

2. Follow the existing adapter contract:
   - Reuse the source's native job ID when available; otherwise call
     `make_job_id(...)`.
   - Set `source` to a short stable label; it appears in the dashboard filter.
   - Call `check_location(location, title)` for the two boolean flags.
   - Pass a `USER_AGENTS` value and a 12 s timeout.
   - Catch exceptions, log at `debug` with context, and return `[]`.
3. Wire it into `src/pipeline.py` behind an `include_<name>` parameter and add
   the task to the `tasks` list.
4. Include any new counts in the returned stats dict if useful.
5. Update [Architecture](architecture.md) and this page.

No dashboard change is needed: the source dropdown is populated from
`SELECT DISTINCT source FROM jobs`.

## Location rules

Edit the lists in `src/config/companies.py`:

```python
HYDERABAD_KEYWORDS = [
    "hyderabad", "telangana", "hitec city", "gachibowli",
    "madhapur", "kondapur", "cyberabad",
]

INDIA_KEYWORDS = [
    "india", "bengaluru", "bangalore", "hyderabad", "pune", "mumbai",
    "gurgaon", "gurugram", "noida", "chennai", "delhi",
    "remote - india", "india - remote",
]
```

- Matching is lowercase with `\b` word boundaries against
  `"<location> <title>"`.
- Every Hyderabad match also sets `is_india`.
- Add abbreviations or city spellings here (for example `hyd`, `hitech city`,
  `bengaluru remote`) rather than changing `check_location()`.
- Existing rows keep their flags until refetched. To reclassify everything,
  delete `jobs.db` and rerun (see [Operations](operations.md#reset-the-database)).

## Runtime options

`run_pipeline()` in `src/pipeline.py` accepts:

| Parameter | Default | Effect |
| --- | --- | --- |
| `include_greenhouse` | `True` | Include all Greenhouse boards. |
| `include_lever` | `True` | Include all Lever boards. |
| `include_ashby` | `True` | Include all Ashby boards. |
| `include_apis` | `True` | Include Jobicy and Arbeitnow. |
| `role_filter` | `None` | If set, keep only titles matching `partial_match()`; also sent to Jobicy as `tag`. |
| `progress_callback` | `None` | Called as `(message, completed, total)` after each task finishes. |

Example: Ashby + APIs only, filtered to data engineering roles:

```python
import asyncio
from src.pipeline import run_pipeline

stats = asyncio.run(run_pipeline(
    include_greenhouse=False,
    include_lever=False,
    include_ashby=True,
    include_apis=True,
    role_filter="data engineer",
))
print(stats)
```

The CLI does not expose these flags; call the function from Python when you need
a partial run. Note that a partial run does **not** delete jobs from sources you
skip; it only upserts what it fetched.

### Concurrency and timeouts

Current values, all in code:

| Knob | Location | Value |
| --- | --- | --- |
| Max concurrent requests | `run_pipeline()` | `asyncio.Semaphore(10)` |
| Pre-request jitter | `run_pipeline()` | `asyncio.sleep(0.05)` |
| Client connection limits | `run_pipeline()` | keep-alive 20, max 30 |
| Client timeout | `run_pipeline()` | 15.0 s |
| Adapter timeout | `src/scrapers/*.py` | 12.0 s |

Lower the semaphore if you see repeated timeouts or blocked requests; raise it
only if you understand the target APIs' tolerance. There is no retry loop, so a
failed request simply returns no jobs for that source in that run.

## Role search behavior

`src/db/search.py` implements token-aware matching:

- Case-insensitive, AND across query words.
- Splits camelCase and punctuation: `GenAI` → `gen ai`, `AI/ML` → `ai ml`,
  `Front-End` → `front end`.
- Query tokens shorter than 3 characters match whole tokens only.
- Tokens of 3+ characters match token prefixes.
- Tokens of 4+ characters may also match across glued tokens
  (`frontend` → `front end`).

Examples:

| Query | Matches | Does not match |
| --- | --- | --- |
| `AI` | AI Engineer, GenAI, AI/ML | Business Affairs, Spain |
| `data eng` | Data Engineer, Senior Data Platform Engineer | Data Analyst |
| `frontend` | Front-End Developer, Front End Developer | Backend Developer |

The dashboard applies this to job titles, not descriptions. If you need
description search, the `jobs_fts` index exists but `query_jobs()` does not
currently use it.

Constants to tune in `src/db/search.py`:

- `_MIN_PREFIX_QUERY_LEN = 3`
- `_MIN_COMPACT_QUERY_LEN = 4`

Changing them affects both the dashboard and any Python caller, since the same
function is registered as a SQLite UDF in `get_db()`.

## Dashboard options

| Need | How |
| --- | --- |
| Change the port | `uv run streamlit run src/app.py --server.port 8502` |
| Run headless (no browser prompt) | `--server.headless true` |
| Suppress usage stats | `--browser.gatherUsageStats false` |
| Persist Streamlit settings | Create `.streamlit/config.toml` locally (gitignored) |
| Change the 500-row cap | `limit=500` in `src/app.py` |
| Change default location filter | `index=0` on the radio in `src/app.py` |
| Add/remove export columns | `export_df` selection in `src/app.py` |

Example local `.streamlit/config.toml`:

```toml
[server]
headless = true

[browser]
gatherUsageStats = false
```

Streamlit may otherwise ask for an email address on first interactive start.
`STREAMLIT_BROWSER_GATHER_USAGE_STATS=false` has the same effect for usage stats.

## Database location

`DB_PATH` in `src/db/storage.py` is `Path("jobs.db")`, resolved relative to the
**current working directory**. Running `uv run python -m src.pipeline` from a
different directory creates a separate database there.

To use a fixed location, change `DB_PATH` (for example
`Path.home() / "jobs.db"`). `save_jobs()`, `query_jobs()`, and `get_stats()`
also accept an explicit `db_path` argument for scripts and one-off queries.

## Environment and packaging

- No `.env` file is read. `python-dotenv` is declared but unused.
- `pyproject.toml` defines a `daily-jobs-pipeline` console script pointing at
  `src/daily_jobs_pipeline/__init__.py:main`, which only prints a greeting.
  Use `uv run python -m src.pipeline` instead, or replace the stub if you want a
  real entry point.
- Adding or updating dependencies: use `uv add <package>` or edit
  `pyproject.toml` then run `uv lock`, and commit both `pyproject.toml` and
  `uv.lock`.

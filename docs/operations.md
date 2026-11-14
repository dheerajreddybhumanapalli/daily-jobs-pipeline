# Operations

How to run, schedule, inspect, and troubleshoot the pipeline in normal use.

All commands assume the repository root as the current working directory.
`jobs.db` is created there on first use.

## First run checklist

```bash
uv sync
uv run python -m src.pipeline
uv run python -c "from src.db.storage import get_stats; print(get_stats())"
uv run streamlit run src/app.py
```

A successful first run prints a stats dict, and `get_stats()` returns a non-zero
`total`. Load <http://localhost:8501> and confirm the metric cards and job
list are populated.

## Running the pipeline

### Manual CLI run

```bash
uv run python -m src.pipeline
```

- Fetches every configured source, upserts results, and prints
  `fetched_total`, `matched_criteria`, `saved_upserted`, `india_jobs`, and
  `hyderabad_jobs`.
- Takes no arguments. `--help` is not handled and will start a real run.
- Logs HTTP requests at `INFO` via `httpx`; per-source failures are logged at
  `DEBUG` and are not shown with the default logging level.

### From the dashboard

Use **Fetch Latest Jobs Now** in the sidebar. This runs
`asyncio.run(run_pipeline(role_filter=None))` inside the Streamlit process and
then reruns the page. The UI is blocked while the fetch is in progress.

### Discover companies (opt-in)

Discovery is separate from fetching jobs and is always read-only until you
confirm a selection.

From the dashboard: **🏢 Monitored Boards** → **🔎 Discover companies to add** →
**Find companies** → select companies → **Add selected companies**.

From the CLI:

```bash
# List validated candidates only (no configuration changes).
uv run python -m src.discover_boards

# Inspect 50 tokens per ATS starting at offset 100.
uv run python -m src.discover_boards --ats greenhouse,lever --candidates 50 --offset 100

# Persist only the companies you explicitly choose.
uv run python -m src.discover_boards --add greenhouse=stripe --add lever=palantir
```

- Each discovery run reports how many tokens it checked and how many live boards
  it found. Dead tokens are skipped.
- The dashboard remembers the next offset for the current Streamlit session, so
  clicking again checks the next batch.
- A network/index failure prints an error and never edits existing boards.
- Selections are merged idempotently into `src/config/discovered_boards.json`.
- If that file is malformed, saving refuses to overwrite it; fix or delete the
  file and try again.

See [Configuration](configuration.md#discover-companies-from-public-boards) for
the merge rules.

### Programmatic partial run

```python
import asyncio
from src.pipeline import run_pipeline

stats = asyncio.run(run_pipeline(
    include_greenhouse=False,
    include_lever=False,
    include_ashby=True,
    include_apis=False,
))
print(stats)
```

See [Configuration](configuration.md#runtime-options) for all parameters.

## Scheduling

The pipeline is a normal short-lived process, so any scheduler works. Use the
absolute path to `uv` if the scheduler's `PATH` is minimal:

- Windows (typical): `%USERPROFILE%\.local\bin\uv.exe`
- Linux/macOS (typical): `~/.local/bin/uv`

### Windows Task Scheduler

Create a daily task with:

| Field | Value |
| --- | --- |
| Program/script | `powershell.exe` |
| Add arguments | `-NoProfile -NonInteractive -Command "Set-Location -LiteralPath 'C:\path\to\daily-jobs-pipeline'; & uv run python -m src.pipeline *>> pipeline.log"` |
| Start in | `C:\path\to\daily-jobs-pipeline` |

Or put the command in `run-daily.ps1` and schedule that file. In the task
settings, enable **Do not start a new instance** to prevent overlapping runs.

### cron (Linux/macOS)

```cron
0 8 * * * cd /path/to/daily-jobs-pipeline && /home/you/.local/bin/uv run python -m src.pipeline >> /path/to/pipeline.log 2>&1
```

For overlap protection on Linux, wrap the command in `flock`:

```cron
0 8 * * * cd /path/to/daily-jobs-pipeline && flock -n /tmp/jobs-pipeline.lock /home/you/.local/bin/uv run python -m src.pipeline >> /path/to/pipeline.log 2>&1
```

There is no built-in lock, so two simultaneous runs can contend for SQLite
writes. Avoid launching a manual run while a scheduled run is active.

## Logs and monitoring

- The CLI uses Python `logging` at `INFO` and `rich` for its start/finish
  messages. Redirect output to a file when scheduling.
- Expected per-request log lines look like
  `HTTP Request: GET https://... "HTTP/1.1 200 OK"`. A `404` usually means a
  stale board token.
- The process exits `0` when it completes, even if individual boards fail. A
  non-zero exit means an unhandled error (for example, an import failure or an
  unwritable database path).
- A run that completes with `fetched_total: 0` is not a success signal — check
  connectivity and the source endpoints.

Quick health check:

```bash
uv run python -c "from src.db.storage import get_stats; print(get_stats())"
```

The result always has the keys `total`, `india`, `hyderabad`, and `companies`.
Values grow over time and depend on which boards returned data, so treat them as
a liveness signal rather than fixed numbers.

## Inspecting the database

The `sqlite-utils` CLI is installed as a dependency.

```bash
# Jobs per source
uv run sqlite-utils jobs.db "select source, count(*) as jobs from jobs group by source order by jobs desc" --csv

# Top companies by stored job count
uv run sqlite-utils jobs.db "select company, count(*) as jobs from jobs group by company order by jobs desc limit 20" --csv

# Recent Hyderabad roles
uv run sqlite-utils jobs.db "select company, title, location, source, posted_date from jobs where is_hyderabad = 1 order by created_at desc limit 20" --csv

# Table schema
uv run sqlite-utils schema jobs.db
```

Python equivalents:

```python
from src.db.storage import get_stats, query_jobs

print(get_stats())
for job in query_jobs(search_query="data engineer", hyderabad_only=True, limit=10):
    print(job["company"], "|", job["title"], "|", job["url"])
```

Remember that `created_at` is refreshed on every upsert, so it means "last seen
in a successful fetch", not "first discovered".

## Backup

Stop writes for a fully consistent copy, or use SQLite's online backup:

```bash
uv run python -c "import sqlite3; s=sqlite3.connect('jobs.db'); d=sqlite3.connect('jobs-backup.db'); s.backup(d); d.close(); s.close()"
```

Simple file copies also work when the pipeline is not running:

```powershell
Copy-Item jobs.db "jobs-$(Get-Date -Format yyyyMMdd-HHmm).db"
```

```bash
cp jobs.db "jobs-$(date +%Y%m%d-%H%M).db"
```

`*.db` is gitignored, so backups stay local.

## Prune stale postings

Nothing is deleted automatically. A posting that disappears from a source stops
being updated, so its `created_at` ages while active postings keep refreshing.

Preview what would be removed:

```bash
uv run sqlite-utils jobs.db "select count(*) from jobs where created_at < strftime('%Y-%m-%dT%H:%M:%S', 'now', '-30 days')"
```

Delete it:

```bash
uv run sqlite-utils jobs.db "delete from jobs where created_at < strftime('%Y-%m-%dT%H:%M:%S', 'now', '-30 days')"
```

Caveats:

- Run this only after a successful full run; otherwise rows from a temporarily
  failing board can look stale.
- A short window is risky. 30–90 days is a reasonable starting point.
- FTS triggers keep the search index in sync with deletes.

## Reset the database

The file is disposable and rebuildable from public sources.

1. Stop the dashboard and any running pipeline.
2. Delete the file:
   - PowerShell: `Remove-Item jobs.db`
   - POSIX: `rm jobs.db`
3. Run `uv run python -m src.pipeline` (or just open the dashboard; `get_db()`
   recreates the schema).

Use a reset after changing the schema or job-ID logic. There are no migrations.

## Reset discovered boards

Discovery selections are stored separately from the curated list:

- PowerShell: `Remove-Item src/config/discovered_boards.json`
- POSIX: `rm src/config/discovered_boards.json`

The next pipeline run falls back to the curated boards only. The Streamlit
session also keeps discovery offsets in memory; restart the app to start a new
scan from the beginning, or use the CLI `--offset 0`.

If the file is malformed, normal pipeline runs ignore it, but saving a new
selection refuses to overwrite it. Delete the file (or fix the JSON) before
adding companies again.

## Upgrading

```bash
git pull
uv sync
uv run python -m src.pipeline
```

To refresh dependency versions within the declared ranges:

```bash
uv lock --upgrade
uv sync
```

Commit both `pyproject.toml` and `uv.lock` if you intentionally change
dependencies.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Dashboard says no jobs | Pipeline never ran, or it wrote to a different working directory | Run from the repo root; check `get_stats()` and `jobs.db` timestamps. |
| A company never appears | Wrong/stale board token, company moved ATS, or board is private | Verify the board URL/API directly; the pipeline skips 404 boards silently. |
| Discovery finds nothing | All checked tokens are dead or already configured | Raise **Boards to check per ATS**, run discovery again for the next batch, or use a different `--offset`. |
| Discovery fails | Public token index or ATS API is unreachable | Check connectivity and retry; existing configured boards are unaffected. |
| `discovered_boards.json is not valid JSON` when saving | Malformed discovery cache | Fix the JSON or delete `src/config/discovered_boards.json`, then rediscover. |
| Selected company is not in the list | It was already configured, or it was not checked in that batch | Check **Monitored Boards** counts; run discovery again or add the token to the curated list. |
| `ModuleNotFoundError: src` | Command run outside the repo root, or `src/app.py` imported instead of launched | `cd` to the repo root; use `uv run streamlit run src/app.py`. |
| `uv: command not found` | uv not installed or not on the scheduler's `PATH` | Install uv or use an absolute path; plain `python` works with an activated venv. |
| `database is locked` | Two writers (scheduled run + dashboard fetch, or two CLI runs) | Stop the other process; serialize scheduled runs. |
| Repeated timeouts / empty sources | Network, VPN, proxy, or API outage | Rerun; check the URLs in a browser; lower the semaphore if needed. |
| Streamlit asks for an email | First-run usage-stats prompt | Set `STREAMLIT_BROWSER_GATHER_USAGE_STATS=false` or add a local `.streamlit/config.toml`. |
| Port 8501 already in use | Another Streamlit instance | `uv run streamlit run src/app.py --server.port 8502`. |
| `--help` started a fetch | The CLI has no argument parser | Let it finish or press Ctrl+C; configure runs in Python. |
| Unexpected duplicates | Job-ID formula or fallback fields changed | Keep IDs stable; reset the DB if the change was intentional. |
| Missing job description | Ashby/Arbeitnow provide none; others are truncated to 2,000 chars | By design; click through to the listing. |
| `salary` is always empty | No adapter populates it | By design; use the source listing. |

For deeper diagnosis, raise logging to `DEBUG` around the failure or run the
adapter in isolation with a small `httpx` script against the same endpoint.

## Etiquette and constraints

- Only public, unauthenticated JSON endpoints are used. Do not add HTML scraping,
  CAPTCHA bypasses, or credential-based access.
- Keep concurrency modest (the current cap is 10). Increasing it may trigger rate
  limits and defeats the project's zero-block design.
- The database contains only public job-posting data. Do not add personal
  application tracking data without considering privacy.
- Validate board tokens before adding them; dead tokens add noise to every run.

## Operational verification

After any change, run:

```bash
uv run python -m compileall -q src
uv run python -m src.pipeline
uv run python -m src.discover_boards --ats greenhouse --candidates 5
uv run python -c "from src.db.storage import get_stats; print(get_stats())"
uv run streamlit run src/app.py
```

Then confirm the dashboard loads, filters return results, and the CSV/JSON export
buttons download the current selection.

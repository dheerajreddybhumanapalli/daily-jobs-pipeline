# Documentation

Project documentation for **daily-jobs-pipeline**. Start with the
[README](../README.md) for an overview and setup, then use these guides:

| Guide | Read it when you want to… |
| --- | --- |
| [Architecture](architecture.md) | Understand how data flows from APIs to the dashboard, the database schema, job IDs, location rules, and search behavior. |
| [Configuration](configuration.md) | Add companies manually or through opt-in discovery, change location keywords, tune concurrency, or configure a programmatic pipeline run. |
| [Operations](operations.md) | Run and schedule the pipeline, inspect or reset the database, upgrade dependencies, and troubleshoot failures. |
| [AGENTS.md](../AGENTS.md) | Contribute code or make changes as a coding agent; contains conventions and verification steps. |

## Quick reference

```bash
# From the repository root
uv sync                                      # install dependencies
uv run streamlit run src/app.py              # dashboard on http://localhost:8501
uv run python -m src.pipeline                # one fetch + upsert run
uv run python -m src.discover_boards         # list opt-in board candidates
uv run sqlite-utils jobs.db "select count(*) from jobs"   # inspect stored jobs
```

## The 30-second version

1. `run_pipeline()` requests job boards for every company in
   `src/config/companies.py` (plus any companies you explicitly added through
   discovery) and Jobicy and Arbeitnow, at most 10 requests at a time.
2. Each adapter converts API payloads into `JobItem` records, tags India and
   Hyderabad roles, and returns them.
3. Rows are upserted into `jobs.db` keyed by a deterministic job ID.
4. The Streamlit dashboard filters that table by role, location, company, and
   source, and exports CSV/JSON.
5. Discovery is a separate, opt-in step: it validates public boards and writes
   only the companies you select.

There are no API keys, no accounts, and no external services to run.

## Documentation conventions

- Commands assume the repository root as the working directory.
- Windows PowerShell and POSIX shells handle examples the same way unless
  stated otherwise.
- Examples use the checked-in configuration; counts may change as
  `src/config/companies.py` evolves.

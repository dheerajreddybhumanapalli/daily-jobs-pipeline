import asyncio
import httpx
import logging
from typing import List, Callable, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from src.db.models import JobItem
from src.db.storage import save_jobs
from src.db.search import partial_match
from src.config.companies import get_companies
from src.scrapers.greenhouse import fetch_greenhouse_jobs
from src.scrapers.lever import fetch_lever_jobs
from src.scrapers.ashby import fetch_ashby_jobs
from src.scrapers.free_apis import fetch_jobicy_jobs, fetch_arbeitnow_jobs

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pipeline")

async def run_pipeline(
    include_greenhouse: bool = True,
    include_lever: bool = True,
    include_ashby: bool = True,
    include_apis: bool = True,
    role_filter: Optional[str] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None
) -> dict:
    """
    Executes concurrent fetching across Greenhouse, Lever, Ashby, Jobicy, and Arbeitnow.
    Safely respects rate-limits with concurrency semaphore (max 10 concurrent requests).
    """
    sem = asyncio.Semaphore(10)
    all_jobs: List[JobItem] = []

    limits = httpx.Limits(max_keepalive_connections=20, max_connections=30)
    async with httpx.AsyncClient(limits=limits, timeout=15.0) as client:
        tasks = []

        async def sem_task(fn, *args):
            async with sem:
                await asyncio.sleep(0.05)  # gentle jitter
                return await fn(*args)

        if include_greenhouse:
            for comp in get_companies("greenhouse"):
                tasks.append(sem_task(fetch_greenhouse_jobs, client, comp))

        if include_lever:
            for comp in get_companies("lever"):
                tasks.append(sem_task(fetch_lever_jobs, client, comp))

        if include_ashby:
            for comp in get_companies("ashby"):
                tasks.append(sem_task(fetch_ashby_jobs, client, comp))

        if include_apis:
            tasks.append(sem_task(fetch_jobicy_jobs, client, role_filter))
            tasks.append(sem_task(fetch_arbeitnow_jobs, client))

        total_tasks = len(tasks)
        completed = 0

        for future in asyncio.as_completed(tasks):
            res = await future
            completed += 1
            if res:
                all_jobs.extend(res)
            if progress_callback:
                progress_callback(f"Scraped source {completed}/{total_tasks}", completed, total_tasks)

    # Filter by role_filter if supplied (partial, token-aware role matching)
    if role_filter and role_filter.strip():
        filtered_jobs = [j for j in all_jobs if partial_match(role_filter, j.title)]
    else:
        filtered_jobs = all_jobs

    saved_count = save_jobs(filtered_jobs)
    
    india_count = sum(1 for j in filtered_jobs if j.is_india)
    hyd_count = sum(1 for j in filtered_jobs if j.is_hyderabad)

    return {
        "fetched_total": len(all_jobs),
        "matched_criteria": len(filtered_jobs),
        "saved_upserted": saved_count,
        "india_jobs": india_count,
        "hyderabad_jobs": hyd_count
    }

if __name__ == "__main__":
    console.print("[bold green]Starting Daily Job Scraping Pipeline...[/bold green]")
    stats = asyncio.run(run_pipeline())
    console.print(f"[bold cyan]Pipeline completed successfully![/bold cyan]")
    console.print(stats)


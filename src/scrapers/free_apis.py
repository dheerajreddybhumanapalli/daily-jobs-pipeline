import httpx
import logging
from typing import List, Optional
from src.db.models import JobItem
from src.scrapers.utils import make_job_id, check_location, USER_AGENTS

logger = logging.getLogger(__name__)

async def fetch_jobicy_jobs(client: httpx.AsyncClient, tag: Optional[str] = None) -> List[JobItem]:
    """Fetch remote & tech jobs from Jobicy free public API."""
    url = "https://jobicy.com/api/v2/remote-jobs?count=50"
    if tag:
        url += f"&tag={tag}"
    
    jobs = []
    try:
        response = await client.get(url, headers={"User-Agent": USER_AGENTS[0]}, timeout=12.0)
        if response.status_code != 200:
            return []
        
        data = response.json()
        job_list = data.get("jobs", [])
        for item in job_list:
            company = item.get("companyName", "Unknown")
            title = item.get("jobTitle", "")
            loc = item.get("jobGeo", "Remote")
            job_url = item.get("url", "")
            job_id_source = item.get("id", "")
            job_type = item.get("jobType", ["Full-Time"])
            if isinstance(job_type, list):
                job_type = ", ".join(job_type)
            pub_date = item.get("pubDate", "")
            desc = item.get("jobDescription", "")

            is_ind, is_hyd = check_location(loc, title)

            jobs.append(
                JobItem(
                    id=f"jobicy_{job_id_source}" if job_id_source else make_job_id("Jobicy", company, title, loc, job_url),
                    source="Jobicy",
                    company=company,
                    title=title,
                    location=loc,
                    is_india=is_ind,
                    is_hyderabad=is_hyd,
                    job_type=job_type or "Full-Time",
                    url=job_url,
                    description=desc[:2000] if desc else "",
                    posted_date=pub_date
                )
            )
    except Exception as e:
        logger.debug(f"Error fetching Jobicy: {e}")
    return jobs

async def fetch_arbeitnow_jobs(client: httpx.AsyncClient) -> List[JobItem]:
    """Fetch jobs from Arbeitnow free public API."""
    url = "https://www.arbeitnow.com/api/job-board-api"
    jobs = []
    try:
        response = await client.get(url, headers={"User-Agent": USER_AGENTS[1]}, timeout=12.0)
        if response.status_code != 200:
            return []
        
        data = response.json()
        job_list = data.get("data", [])
        for item in job_list:
            company = item.get("company_name", "Unknown")
            title = item.get("title", "")
            loc = item.get("location", "Remote")
            job_url = item.get("url", "")
            slug = item.get("slug", "")
            job_types = item.get("job_types", ["Full-Time"])
            job_type = ", ".join(job_types) if isinstance(job_types, list) else str(job_types)

            is_ind, is_hyd = check_location(loc, title)

            jobs.append(
                JobItem(
                    id=f"arbeitnow_{slug}" if slug else make_job_id("Arbeitnow", company, title, loc, job_url),
                    source="Arbeitnow",
                    company=company,
                    title=title,
                    location=loc,
                    is_india=is_ind,
                    is_hyderabad=is_hyd,
                    job_type=job_type,
                    url=job_url,
                    description="",
                    posted_date=str(item.get("created_at", ""))
                )
            )
    except Exception as e:
        logger.debug(f"Error fetching Arbeitnow: {e}")
    return jobs


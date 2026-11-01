import httpx
import logging
from typing import List, Dict, Any
from src.db.models import JobItem
from src.scrapers.utils import make_job_id, check_location, USER_AGENTS

logger = logging.getLogger(__name__)

async def fetch_ashby_jobs(client: httpx.AsyncClient, company: Dict[str, str]) -> List[JobItem]:
    company_name = company["name"]
    token = company["token"]
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    jobs = []

    try:
        response = await client.get(url, headers={"User-Agent": USER_AGENTS[2]}, timeout=12.0)
        if response.status_code != 200:
            return []
        
        data = response.json()
        job_list = data.get("jobs", [])
        for item in job_list:
            title = item.get("title", "")
            loc = item.get("location", "Remote / Unspecified")
            job_url = item.get("jobUrl", "")
            job_id_source = item.get("id", "")
            employment_type = item.get("employmentType", "Full-time")
            published_at = item.get("publishedAt", "")

            # Ashby also provides secondaryLocations
            sec_locs = [s.get("location", "") for s in item.get("secondaryLocations", []) if isinstance(s, dict)]
            all_loc_str = f"{loc} {' '.join(sec_locs)}"

            is_ind, is_hyd = check_location(all_loc_str, title)

            jobs.append(
                JobItem(
                    id=f"ashby_{token}_{job_id_source}" if job_id_source else make_job_id("Ashby", company_name, title, loc, job_url),
                    source="Ashby",
                    company=company_name,
                    title=title,
                    location=loc,
                    is_india=is_ind,
                    is_hyderabad=is_hyd,
                    job_type=employment_type or "Full-time",
                    url=job_url,
                    description="",
                    posted_date=published_at
                )
            )
    except Exception as e:
        logger.debug(f"Error fetching Ashby for {company_name}: {e}")
    
    return jobs


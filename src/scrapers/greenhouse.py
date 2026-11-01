import httpx
import logging
from typing import List, Dict, Any
from src.db.models import JobItem
from src.scrapers.utils import make_job_id, check_location, USER_AGENTS

logger = logging.getLogger(__name__)

async def fetch_greenhouse_jobs(client: httpx.AsyncClient, company: Dict[str, str]) -> List[JobItem]:
    company_name = company["name"]
    token = company["token"]
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
    jobs = []

    try:
        response = await client.get(url, headers={"User-Agent": USER_AGENTS[0]}, timeout=12.0)
        if response.status_code != 200:
            return []
        
        data = response.json()
        job_list = data.get("jobs", [])
        for item in job_list:
            title = item.get("title", "")
            loc = (item.get("location") or {}).get("name", "Remote / Unspecified")
            job_url = item.get("absolute_url", "")
            job_id_source = item.get("id", "")
            updated_at = item.get("updated_at", "")
            content = item.get("content", "")

            is_ind, is_hyd = check_location(loc, title)

            jobs.append(
                JobItem(
                    id=f"gh_{token}_{job_id_source}" if job_id_source else make_job_id("Greenhouse", company_name, title, loc, job_url),
                    source="Greenhouse",
                    company=company_name,
                    title=title,
                    location=loc,
                    is_india=is_ind,
                    is_hyderabad=is_hyd,
                    job_type="Full-time",
                    url=job_url,
                    description=content[:2000] if content else "",
                    posted_date=updated_at
                )
            )
    except Exception as e:
        logger.debug(f"Error fetching Greenhouse for {company_name}: {e}")
    
    return jobs


import httpx
import logging
from typing import List, Dict, Any
from src.db.models import JobItem
from src.scrapers.utils import make_job_id, check_location, USER_AGENTS

logger = logging.getLogger(__name__)

async def fetch_lever_jobs(client: httpx.AsyncClient, company: Dict[str, str]) -> List[JobItem]:
    company_name = company["name"]
    token = company["token"]
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    jobs = []

    try:
        response = await client.get(url, headers={"User-Agent": USER_AGENTS[1]}, timeout=12.0)
        if response.status_code != 200:
            return []
        
        postings = response.json()
        if not isinstance(postings, list):
            return []

        for item in postings:
            title = item.get("text", "")
            categories = item.get("categories", {}) or {}
            loc = categories.get("location", "Remote / Unspecified")
            commitment = categories.get("commitment", "Full-time")
            job_url = item.get("hostedUrl", "")
            job_id_source = item.get("id", "")
            created_at_source = item.get("createdAt")
            description = item.get("descriptionPlain", "")

            is_ind, is_hyd = check_location(loc, title)

            jobs.append(
                JobItem(
                    id=f"lever_{token}_{job_id_source}" if job_id_source else make_job_id("Lever", company_name, title, loc, job_url),
                    source="Lever",
                    company=company_name,
                    title=title,
                    location=loc,
                    is_india=is_ind,
                    is_hyderabad=is_hyd,
                    job_type=commitment or "Full-time",
                    url=job_url,
                    description=description[:2000] if description else "",
                    posted_date=str(created_at_source) if created_at_source else ""
                )
            )
    except Exception as e:
        logger.debug(f"Error fetching Lever for {company_name}: {e}")
    
    return jobs


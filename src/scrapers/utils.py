import re
import hashlib
from typing import Tuple
from src.config.companies import HYDERABAD_KEYWORDS, INDIA_KEYWORDS

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
]

def make_job_id(source: str, company: str, title: str, location: str, url: str) -> str:
    raw = f"{source}:{company}:{title}:{location}:{url}".lower()
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

def check_location(location_str: str, title_str: str = "") -> Tuple[bool, bool]:
    """Returns (is_india, is_hyderabad)"""
    combined = f"{location_str} {title_str}".lower()
    
    is_hyd = any(re.search(rf"\b{re.escape(kw)}\b", combined) for kw in HYDERABAD_KEYWORDS)
    is_india = is_hyd or any(re.search(rf"\b{re.escape(kw)}\b", combined) for kw in INDIA_KEYWORDS)
    
    return is_india, is_hyd


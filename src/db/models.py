from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class JobItem(BaseModel):
    id: str  # Unique composite hash or source id
    source: str  # e.g., 'Greenhouse', 'Lever', 'Ashby', 'Jobicy', 'Arbeitnow', etc.
    company: str
    title: str
    location: str
    is_india: bool = False
    is_hyderabad: bool = False
    job_type: Optional[str] = "Full-time"
    url: str
    description: Optional[str] = ""
    salary: Optional[str] = None
    posted_date: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


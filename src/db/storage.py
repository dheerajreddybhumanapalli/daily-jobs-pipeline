import sqlite_utils
from pathlib import Path
from typing import List, Dict, Any, Optional
from src.db.models import JobItem
from src.db.search import partial_match

DB_PATH = Path("jobs.db")

def get_db(db_path: Path = DB_PATH) -> sqlite_utils.Database:
    db = sqlite_utils.Database(db_path)
    # Expose the partial role matcher to SQLite so query_jobs() can filter in SQL.
    db.conn.create_function(
        "partial_match",
        -1,
        lambda *args: int(partial_match(*args)),
        deterministic=True,
    )
    if "jobs" not in db.table_names():
        db["jobs"].create(
            {
                "id": str,
                "source": str,
                "company": str,
                "title": str,
                "location": str,
                "is_india": int,
                "is_hyderabad": int,
                "job_type": str,
                "url": str,
                "description": str,
                "salary": str,
                "posted_date": str,
                "created_at": str,
            },
            pk="id"
        )
        # Enable full text search on title, company, location, description
        db["jobs"].enable_fts(["title", "company", "location", "description"], create_triggers=True)
    return db

def save_jobs(jobs: List[JobItem], db_path: Path = DB_PATH) -> int:
    """Save jobs with upsert (deduplicated by primary key id). Returns number of jobs upserted."""
    if not jobs:
        return 0
    db = get_db(db_path)
    records = []
    for job in jobs:
        record = job.model_dump()
        record["is_india"] = 1 if job.is_india else 0
        record["is_hyderabad"] = 1 if job.is_hyderabad else 0
        records.append(record)
    
    db["jobs"].upsert_all(records, pk="id")
    return len(records)

def query_jobs(
    search_query: Optional[str] = None,
    india_only: bool = False,
    hyderabad_only: bool = False,
    company: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
    db_path: Path = DB_PATH
) -> List[Dict[str, Any]]:
    """Query stored jobs.

    ``search_query`` is a partial, case-insensitive role/title search:
    "AI" matches AI Engineer, GenAI and AI/ML roles, while "data eng"
    matches Data Engineer titles. Company and location have dedicated filters.
    """
    db = get_db(db_path)
    conditions = []
    params = []

    if search_query and search_query.strip():
        # Partial, token-aware role search: "AI" matches "AI Engineer", "GenAI",
        # "AI/ML", etc. without matching unrelated words like "Affairs" or "Spain".
        conditions.append("partial_match(?, coalesce(title, ''))")
        params.append(search_query.strip())

    if hyderabad_only:
        conditions.append("is_hyderabad = 1")
    elif india_only:
        conditions.append("is_india = 1")

    if company and company.strip():
        conditions.append("lower(company) = ?")
        params.append(company.strip().lower())

    if source and source.strip():
        conditions.append("source = ?")
        params.append(source.strip())

    where_clause = " AND ".join(conditions) if conditions else "1=1"
    sql = f"SELECT * FROM jobs WHERE {where_clause} ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}"
    
    return list(db.query(sql, params))

def get_stats(db_path: Path = DB_PATH) -> Dict[str, Any]:
    db = get_db(db_path)
    if "jobs" not in db.table_names():
        return {"total": 0, "india": 0, "hyderabad": 0, "companies": 0}
    
    total = db["jobs"].count
    india = db["jobs"].count_where("is_india = 1")
    hyd = db["jobs"].count_where("is_hyderabad = 1")
    companies = len(list(db.query("SELECT DISTINCT company FROM jobs")))
    return {
        "total": total,
        "india": india,
        "hyderabad": hyd,
        "companies": companies
    }


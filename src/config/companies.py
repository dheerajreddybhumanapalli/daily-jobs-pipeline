"""
Company target configurations for ATS boards (Greenhouse, Lever, Ashby, Workable)
Focusing on Top Global Capability Centers (GCCs), Tech Giants, and Unicorns with India / Hyderabad offices.

The lists below are the curated defaults. Boards discovered on demand (via
``src.scrapers.discovery``) are written to ``discovered_boards.json`` and merged
at read time by :func:`get_companies`. Until a discovery run happens, only the
curated boards are used.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent
DISCOVERED_BOARDS_FILE = CONFIG_DIR / "discovered_boards.json"

# ATS board tokens are URL slugs. Restrict them so a malformed discovery
# payload can never be written into the configuration cache.
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")


class DiscoveryConfigError(RuntimeError):
    """Raised when the discovered-board cache cannot be read or written safely."""

# Companies using Greenhouse ATS:
# API endpoint: https://boards-api.greenhouse.io/v1/boards/{token}/jobs
GREENHOUSE_COMPANIES = [
    # Top GCCs / MNCs / Tech leaders
    {"name": "Stripe", "token": "stripe"},
    {"name": "Coinbase", "token": "coinbase"},
    {"name": "Airbnb", "token": "airbnb"},
    {"name": "Pinterest", "token": "pinterest"},
    {"name": "GitLab", "token": "gitlab"},
    {"name": "Twilio", "token": "twilio"},
    {"name": "Cloudflare", "token": "cloudflare"},
    {"name": "Databricks", "token": "databricks"},
    {"name": "Figma", "token": "figma"},
    {"name": "Brex", "token": "brex"},
    {"name": "Instacart", "token": "instacart"},
    {"name": "Rubrik", "token": "rubrik"},
    {"name": "Okta", "token": "okta"},
    {"name": "MongoDB", "token": "mongodb"},
    {"name": "Samsara", "token": "samsara"},
    {"name": "Branch", "token": "branch"},
    {"name": "Qualtrics", "token": "qualtrics"},
    {"name": "Snowflake", "token": "snowflake"},
    {"name": "Confluent", "token": "confluent"},
    {"name": "Elastic", "token": "elastic"},
    {"name": "Toast", "token": "toast"},
    {"name": "ServiceTitan", "token": "servicetitan"},
]

# Companies using Lever ATS:
# API endpoint: https://api.lever.co/v0/postings/{token}?mode=json
LEVER_COMPANIES = [
    {"name": "Palantir", "token": "palantir"},
    {"name": "FullStory", "token": "fullstory"},
    {"name": "Affirm", "token": "affirm"},
    {"name": "Coursera", "token": "coursera"},
]

# Companies using Ashby ATS:
# API endpoint: https://api.ashbyhq.com/posting-api/job-board/{token}
ASHBY_COMPANIES = [
    {"name": "Ramp", "token": "ramp"},
    {"name": "Notion", "token": "notion"},
    {"name": "OpenAI", "token": "openai"},
    {"name": "Vercel", "token": "vercel"},
    {"name": "Perplexity", "token": "perplexity"},
    {"name": "Linear", "token": "linear"},
    {"name": "Deel", "token": "deel"},
    {"name": "Synthesia", "token": "synthesia"},
    {"name": "Luma", "token": "luma"},
    {"name": "Cursor", "token": "anysphere"},
]

# Workable ATS boards
# API endpoint: https://apply.workable.com/api/v3/accounts/{token}/jobs
WORKABLE_COMPANIES = [
    {"name": "InVideo", "token": "invideo"},
    {"name": "BrowserStack (Workable)", "token": "browserstack"},
]

# Keywords for location filtering
HYDERABAD_KEYWORDS = [
    "hyderabad", "telangana", "hitec city", "gachibowli", "madhapur", "kondapur", "cyberabad"
]

INDIA_KEYWORDS = [
    "india", "bengaluru", "bangalore", "hyderabad", "pune", "mumbai", "gurgaon", 
    "gurugram", "noida", "chennai", "delhi", "remote - india", "india - remote"
]

CURATED_BOARDS: Dict[str, List[Dict[str, str]]] = {
    "greenhouse": GREENHOUSE_COMPANIES,
    "lever": LEVER_COMPANIES,
    "ashby": ASHBY_COMPANIES,
    "workable": WORKABLE_COMPANIES,
}


def _read_discovered_payload(strict: bool) -> Dict[str, object]:
    """Read the raw discovery cache.

    Normal pipeline runs use ``strict=False`` so a missing or malformed cache is
    ignored. The save path uses ``strict=True`` so it refuses to overwrite a file
    it cannot understand.
    """
    if not DISCOVERED_BOARDS_FILE.exists():
        return {}

    try:
        raw = json.loads(DISCOVERED_BOARDS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        if strict:
            raise DiscoveryConfigError(
                f"{DISCOVERED_BOARDS_FILE} is not valid JSON; refusing to overwrite it ({exc})"
            ) from exc
        logger.warning("Could not read %s: %s", DISCOVERED_BOARDS_FILE, exc)
        return {}

    if not isinstance(raw, dict):
        if strict:
            raise DiscoveryConfigError(
                f"{DISCOVERED_BOARDS_FILE} must contain a JSON object; refusing to overwrite it"
            )
        logger.warning("Ignoring %s because it is not a JSON object", DISCOVERED_BOARDS_FILE)
        return {}

    return raw


def _write_discovered_payload(payload: Mapping[str, object]) -> None:
    """Atomically replace the discovery cache so a failed write cannot corrupt it."""
    DISCOVERED_BOARDS_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_path = DISCOVERED_BOARDS_FILE.with_name(DISCOVERED_BOARDS_FILE.name + ".tmp")
    try:
        temp_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temp_path.replace(DISCOVERED_BOARDS_FILE)
    except OSError as exc:
        raise DiscoveryConfigError(
            f"Could not write {DISCOVERED_BOARDS_FILE}: {exc}"
        ) from exc


def load_discovered_boards() -> Dict[str, List[Dict[str, str]]]:
    """Read the on-demand discovery cache (``discovered_boards.json``).

    Returns an empty mapping when the file does not exist or is malformed, so a
    missing cache never breaks a normal pipeline run.
    """
    raw = _read_discovered_payload(strict=False)
    return {
        ats: [board for board in boards if isinstance(board, dict) and board.get("token")]
        for ats, boards in raw.items()
        if isinstance(boards, list) and not ats.startswith("_")
    }


def add_discovered_companies(
    selections: Mapping[str, Iterable[Mapping[str, object]]],
) -> Dict[str, object]:
    """Add or update only the companies the caller selected.

    ``selections`` maps an ATS name to discovered board records. The operation is
    idempotent: a token already present in the curated list or the discovery
    cache is reported as unchanged instead of being inserted again. Nothing is
    written when no company is actually added or updated, and a malformed cache
    raises :class:`DiscoveryConfigError` instead of being overwritten.

    Returns a summary with ``added``, ``updated``, ``unchanged`` and ``invalid``
    record lists plus their counts and the resulting per-ATS totals.
    """
    payload = _read_discovered_payload(strict=True)
    now = datetime.now(timezone.utc).isoformat()
    added: List[Dict[str, str]] = []
    updated: List[Dict[str, str]] = []
    unchanged: List[Dict[str, str]] = []
    invalid: List[Dict[str, str]] = []
    changed = False

    for raw_ats, boards in selections.items():
        ats = str(raw_ats).strip().lower()
        if ats not in CURATED_BOARDS:
            invalid.append({"ats": ats, "name": "", "token": "", "reason": "unsupported ATS"})
            continue

        curated_tokens = {
            str(board.get("token", "")).strip().lower()
            for board in CURATED_BOARDS[ats]
            if board.get("token")
        }

        existing = payload.get(ats)
        if not isinstance(existing, list):
            existing = []
            payload[ats] = existing

        by_token: Dict[str, Dict[str, object]] = {}
        for record in existing:
            if not isinstance(record, dict):
                continue
            token = str(record.get("token", "")).strip()
            if token and token.lower() not in by_token:
                by_token[token.lower()] = record

        for raw_board in boards:
            if not isinstance(raw_board, Mapping):
                invalid.append({"ats": ats, "name": "", "token": "", "reason": "invalid record"})
                continue

            token = str(raw_board.get("token", "")).strip()
            name = str(raw_board.get("name") or token).strip() or token
            if not token or not TOKEN_PATTERN.fullmatch(token):
                invalid.append({"ats": ats, "name": name, "token": token, "reason": "invalid token"})
                continue

            key = token.lower()
            if key in curated_tokens:
                unchanged.append(
                    {"ats": ats, "name": name, "token": token, "reason": "curated"}
                )
                continue

            record = by_token.get(key)
            if record is not None:
                record_changed = False
                if name and record.get("name") != name:
                    record["name"] = name
                    record_changed = True

                jobs = raw_board.get("jobs")
                if isinstance(jobs, int) and jobs >= 0 and record.get("jobs") != jobs:
                    record["jobs"] = jobs
                    record_changed = True

                if record_changed:
                    updated.append({"ats": ats, "name": name, "token": token})
                    changed = True
                else:
                    unchanged.append({"ats": ats, "name": name, "token": token})
                continue

            new_record: Dict[str, object] = {
                "name": name,
                "token": token,
                "added_at": now,
            }
            jobs = raw_board.get("jobs")
            if isinstance(jobs, int) and jobs >= 0:
                new_record["jobs"] = jobs

            existing.append(new_record)
            by_token[key] = new_record
            added.append({"ats": ats, "name": name, "token": token})
            changed = True

    if changed:
        _write_discovered_payload(payload)

    return {
        "added": added,
        "updated": updated,
        "unchanged": unchanged,
        "invalid": invalid,
        "added_count": len(added),
        "updated_count": len(updated),
        "unchanged_count": len(unchanged),
        "invalid_count": len(invalid),
        "totals": {ats: len(get_companies(ats)) for ats in CURATED_BOARDS},
    }


def get_companies(ats: str) -> List[Dict[str, str]]:
    """Return curated + discovered boards for ``ats``, deduplicated by token."""
    ats = ats.strip().lower()
    boards: List[Dict[str, str]] = list(CURATED_BOARDS.get(ats, []))
    seen = {str(board.get("token", "")).lower() for board in boards}

    for board in load_discovered_boards().get(ats, []):
        token = str(board.get("token", "")).strip()
        if not token or token.lower() in seen:
            continue
        boards.append({"name": board.get("name") or token, "token": token})
        seen.add(token.lower())

    return boards


def get_all_companies() -> Dict[str, List[Dict[str, str]]]:
    """Return the effective board list for every supported ATS."""
    return {ats: get_companies(ats) for ats in CURATED_BOARDS}


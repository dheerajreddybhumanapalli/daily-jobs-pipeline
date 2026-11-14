"""Opt-in discovery of new ATS boards.

ATS vendors do not expose a global "list every board" endpoint. Instead this
module reads a community-maintained public index of board tokens and validates
each candidate against the live ATS API.

Discovery is read-only: it returns validated candidates but never changes the
configuration. The caller decides which companies to add, then persists only
those selections through
:func:`src.config.companies.add_discovered_companies`.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Callable, Dict, Iterable, List, Optional, Tuple

import httpx

from src.config.companies import TOKEN_PATTERN, get_companies
from src.scrapers.utils import USER_AGENTS

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int, int], None]

# Public, community-maintained token indexes. The primary file is a dict of
# ATS -> token list; the fallback repo publishes one JSON list per ATS.
PRIMARY_TOKEN_INDEX = (
    "https://raw.githubusercontent.com/veresk06/open-ats-feed/main/data/tokens.json"
)
FALLBACK_TOKEN_INDEX = (
    "https://raw.githubusercontent.com/Riley-Dorrington/job-board-aggregator"
    "/main/data/{ats}_companies.json"
)

HEADERS = {
    "User-Agent": USER_AGENTS[0],
    # Ashby serves brotli, which some httpx/brotli builds fail to decode.
    "Accept-Encoding": "gzip, deflate",
}

ATS_SPECS: Dict[str, Dict[str, object]] = {
    "greenhouse": {
        "validate_url": "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=false",
        "name_url": "https://boards-api.greenhouse.io/v1/boards/{token}",
        "jobs_key": "jobs",
        "skip_tokens": {"api", "embed", "job_board", "jobs", "sitemap.xml"},
    },
    "lever": {
        "validate_url": "https://api.lever.co/v0/postings/{token}?mode=json",
        "name_url": None,
        "jobs_key": None,  # Lever returns a top-level JSON list
        "skip_tokens": {"api", "embed"},
    },
    "ashby": {
        "validate_url": "https://api.ashbyhq.com/posting-api/job-board/{token}",
        "name_url": None,
        "jobs_key": "jobs",
        "skip_tokens": {"api", "embed"},
    },
}


def _report(
    callback: Optional[ProgressCallback], message: str, done: int = 0, total: int = 0
) -> None:
    if callback:
        try:
            callback(message, done, total)
        except Exception:  # a UI callback must never break discovery
            logger.debug("Progress callback failed", exc_info=True)


def _pretty_token(token: str) -> str:
    words = [word for word in re.split(r"[-_]+", token) if word]
    return " ".join(word[:1].upper() + word[1:] for word in words) or token


def _normalise_tokens(raw: object) -> List[str]:
    if not isinstance(raw, list):
        return []
    tokens: List[str] = []
    seen = set()
    for value in raw:
        if not isinstance(value, str):
            continue
        token = value.strip()
        key = token.lower()
        if not token or key in seen or not TOKEN_PATTERN.fullmatch(token):
            continue
        seen.add(key)
        tokens.append(token)
    return tokens


async def _fetch_token_index(
    client: httpx.AsyncClient, ats_sources: List[str], errors: List[str]
) -> Dict[str, List[str]]:
    """Fetch and merge public board-token indexes for the requested ATS sources.

    Failures are recorded in ``errors`` and skipped; one unavailable index must
    not stop the other sources from being searched.
    """
    index: Dict[str, List[str]] = {ats: [] for ats in ats_sources}
    seen: Dict[str, set] = {ats: set() for ats in ats_sources}

    def merge(ats: str, raw: object) -> None:
        for token in _normalise_tokens(raw):
            key = token.lower()
            if key in seen[ats]:
                continue
            seen[ats].add(key)
            index[ats].append(token)

    try:
        response = await client.get(PRIMARY_TOKEN_INDEX, headers=HEADERS, timeout=60.0)
        if response.status_code == 200:
            payload = response.json()
            if isinstance(payload, dict):
                for ats in ats_sources:
                    merge(ats, payload.get(ats))
                logger.info("Loaded primary token index")
            else:
                logger.warning("Primary token index returned an unexpected format")
        else:
            logger.warning("Primary token index returned %s", response.status_code)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Could not load primary token index: %s", exc)

    for ats in ats_sources:
        try:
            response = await client.get(
                FALLBACK_TOKEN_INDEX.format(ats=ats), headers=HEADERS, timeout=60.0
            )
            if response.status_code == 200:
                merge(ats, response.json())
        except (httpx.HTTPError, ValueError) as exc:
            logger.debug("Could not load fallback token index for %s: %s", ats, exc)

    for ats in ats_sources:
        if not index[ats]:
            errors.append(f"{ats}: no board tokens were available from the public index")

    return index


async def _board_name(client: httpx.AsyncClient, spec: dict, token: str) -> str:
    name_url = spec.get("name_url")
    if name_url:
        try:
            response = await client.get(
                str(name_url).format(token=token), headers=HEADERS, timeout=10.0
            )
            if response.status_code == 200:
                name = (response.json() or {}).get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
        except (httpx.HTTPError, ValueError, AttributeError):
            pass
    return _pretty_token(token)


async def _validate_board(
    client: httpx.AsyncClient, spec: dict, token: str
) -> Optional[Dict[str, object]]:
    """Return a board record when the token is live and has at least one job."""
    try:
        response = await client.get(
            str(spec["validate_url"]).format(token=token), headers=HEADERS, timeout=15.0
        )
    except httpx.HTTPError:
        return None

    if response.status_code != 200:
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    if spec["jobs_key"] is None:
        jobs = data
    elif isinstance(data, dict):
        jobs = data.get(spec["jobs_key"])
    else:
        jobs = None

    if not isinstance(jobs, list) or not jobs:
        return None

    return {
        "name": await _board_name(client, spec, token),
        "token": token,
        "jobs": len(jobs),
    }


async def _validate_many(
    client: httpx.AsyncClient,
    spec: dict,
    tokens: List[str],
    semaphore: asyncio.Semaphore,
    ats: str,
    callback: Optional[ProgressCallback],
) -> List[Tuple[str, Optional[Dict[str, object]]]]:
    async def validate(token: str) -> Tuple[str, Optional[Dict[str, object]]]:
        async with semaphore:
            await asyncio.sleep(0.05)
            return token, await _validate_board(client, spec, token)

    tasks = [asyncio.create_task(validate(token)) for token in tokens]
    results: List[Tuple[str, Optional[Dict[str, object]]]] = []
    for completed, future in enumerate(asyncio.as_completed(tasks), start=1):
        results.append(await future)
        _report(callback, f"{ats}: validating boards {completed}/{len(tokens)}", completed, len(tokens))
    return results


def _pick_candidates(
    tokens: List[str],
    start: int,
    excluded: set,
    skip_tokens: set,
    limit: int,
) -> Tuple[List[str], int]:
    """Walk the token list from ``start`` and return up to ``limit`` new tokens."""
    if not tokens:
        return [], 0

    cursor = start % len(tokens)
    picked: List[str] = []
    seen = set(excluded) | set(skip_tokens)
    # Avoid scanning the entire index when it is exhausted; wrap once at most.
    max_scan = len(tokens)

    for _ in range(max_scan):
        token = tokens[cursor]
        cursor = (cursor + 1) % len(tokens)
        key = token.lower()
        if key in seen or not TOKEN_PATTERN.fullmatch(token):
            continue
        seen.add(key)
        picked.append(token)
        if len(picked) >= limit:
            break

    return picked, cursor


async def _discover_one(
    client: httpx.AsyncClient,
    ats: str,
    tokens: List[str],
    semaphore: asyncio.Semaphore,
    *,
    offset: int,
    max_candidates: int,
    callback: Optional[ProgressCallback],
) -> Dict[str, object]:
    spec = ATS_SPECS[ats]
    skip_tokens = spec["skip_tokens"]  # type: ignore[assignment]

    excluded = {
        str(board.get("token", "")).lower()
        for board in get_companies(ats)
        if board.get("token")
    }
    candidates, next_offset = _pick_candidates(
        tokens, offset, excluded, skip_tokens, max_candidates
    )

    _report(callback, f"{ats}: checking {len(candidates)} new board candidates")
    results = await _validate_many(
        client, spec, candidates, semaphore, ats, callback
    )

    boards = [board for _, board in results if board is not None]
    return {
        "candidates": boards,
        "checked": len(candidates),
        "available_tokens": len(tokens),
        "next_offset": next_offset,
    }


async def discover_boards(
    ats_sources: Iterable[str] = ("greenhouse", "lever", "ashby"),
    *,
    max_candidates_per_ats: int = 120,
    concurrency: int = 12,
    offsets: Optional[Dict[str, int]] = None,
    progress_callback: Optional[ProgressCallback] = None,
) -> Dict[str, object]:
    """Return validated board candidates without changing configuration.

    ``offsets`` lets the dashboard continue from the last batch it checked.
    Every candidate is validated against its live ATS endpoint, so dead or
    malformed tokens are never offered to the user.
    """
    sources = [source for source in ats_sources if source in ATS_SPECS]
    if not sources:
        raise ValueError("No supported ATS sources were selected")
    offsets = offsets or {}
    errors: List[str] = []

    limits = httpx.Limits(max_keepalive_connections=20, max_connections=40)
    async with httpx.AsyncClient(limits=limits, timeout=20.0, follow_redirects=True) as client:
        _report(progress_callback, "Loading public board index")
        index = await _fetch_token_index(client, sources, errors)
        if not any(index.values()):
            raise RuntimeError(
                "Could not load any public board index; existing boards were not changed"
            )

        semaphore = asyncio.Semaphore(max(1, concurrency))
        outcomes = await asyncio.gather(
            *(
                _discover_one(
                    client,
                    ats,
                    index.get(ats) or [],
                    semaphore,
                    offset=max(0, int(offsets.get(ats, 0))),
                    max_candidates=max(1, max_candidates_per_ats),
                    callback=progress_callback,
                )
                for ats in sources
            ),
            return_exceptions=True,
        )

    by_ats: Dict[str, Dict[str, object]] = {}
    for ats, outcome in zip(sources, outcomes):
        if isinstance(outcome, Exception):
            logger.warning("Discovery failed for %s: %s", ats, outcome)
            errors.append(f"{ats}: discovery failed ({outcome})")
            by_ats[ats] = {
                "candidates": [],
                "checked": 0,
                "available_tokens": len(index.get(ats) or []),
                "next_offset": max(0, int(offsets.get(ats, 0))),
            }
        else:
            by_ats[ats] = outcome

    candidates_total = sum(
        len(info.get("candidates") or []) for info in by_ats.values()
    )
    next_offsets = {
        ats: int(info.get("next_offset", 0)) for ats, info in by_ats.items()
    }
    _report(
        progress_callback,
        f"Discovery finished: {candidates_total} new live boards",
        candidates_total,
        candidates_total,
    )

    return {
        "source": "public ATS token index",
        "candidates_total": candidates_total,
        "by_ats": by_ats,
        "next_offsets": next_offsets,
        "errors": errors,
    }

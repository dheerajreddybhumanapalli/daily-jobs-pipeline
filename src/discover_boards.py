"""CLI entry point for opt-in ATS board discovery.

Usage:
    python -m src.discover_boards
    python -m src.discover_boards --ats greenhouse,lever --candidates 50
    python -m src.discover_boards --add greenhouse=stripe --add lever=palantir

Running without ``--add`` only lists validated candidates; it never changes the
configuration. ``--add`` accepts only tokens discovered in that same run.
"""

import argparse
import asyncio
import logging
from collections import defaultdict

from src.config.companies import add_discovered_companies, get_companies
from src.scrapers.discovery import ATS_SPECS, discover_boards


def _parse_add(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected ATS=TOKEN, for example greenhouse=stripe")
    ats, token = value.split("=", 1)
    ats = ats.strip().lower()
    token = token.strip()
    if not ats or not token:
        raise argparse.ArgumentTypeError("expected ATS=TOKEN, for example greenhouse=stripe")
    return ats, token


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover and validate new ATS boards")
    parser.add_argument(
        "--ats",
        default="greenhouse,lever,ashby",
        help=f"Comma-separated ATS sources (available: {', '.join(ATS_SPECS)})",
    )
    parser.add_argument(
        "--candidates",
        type=int,
        default=120,
        help="Maximum board tokens to validate per ATS (default: 120)",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Position in each token index to start checking from (default: 0)",
    )
    parser.add_argument(
        "--add",
        action="append",
        default=[],
        type=_parse_add,
        metavar="ATS=TOKEN",
        help="Add one discovered token; repeat for multiple companies",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    sources = [source.strip().lower() for source in args.ats.split(",") if source.strip()]
    offsets = {source: max(0, args.offset) for source in sources}
    result = asyncio.run(
        discover_boards(
            sources,
            max_candidates_per_ats=max(1, args.candidates),
            offsets=offsets,
        )
    )

    print(f"Board index: {result['source']}")
    for ats, info in result["by_ats"].items():
        print(
            f"\n{ats} - {len(info['candidates'])} new live boards "
            f"(checked {info['checked']}/{info['available_tokens']} tokens)"
        )
        for board in info["candidates"]:
            print(
                f"  {board['name']}  [{board['token']}]  "
                f"{board['jobs']} job{'s' if board['jobs'] != 1 else ''}"
            )
        if not info["candidates"]:
            print("  (none in this batch)")

    for error in result["errors"]:
        print(f"\nWarning: {error}")

    if not args.add:
        print(
            "\nNothing was added. Re-run with --add ATS=TOKEN "
            "(one per company) to save the companies you selected."
        )
        return

    discovered = {
        (ats, board["token"].lower()): board
        for ats, info in result["by_ats"].items()
        for board in info["candidates"]
    }
    configured = {
        ats: {board["token"].lower() for board in get_companies(ats) if board.get("token")}
        for ats in ATS_SPECS
    }

    selections: dict[str, list[dict]] = defaultdict(list)
    for ats, token in args.add:
        key = (ats, token.lower())
        if key in discovered:
            selections[ats].append(discovered[key])
        elif token.lower() in configured.get(ats, set()):
            print(f"{ats}:{token} is already configured; no change.")
        else:
            print(f"{ats}:{token} was not discovered in this run; skipping it.")

    if not selections:
        print("No selected companies were added.")
        return

    summary = add_discovered_companies(selections)
    print(
        f"\nSaved selections: {summary['added_count']} added, "
        f"{summary['updated_count']} updated, "
        f"{summary['unchanged_count']} already configured, "
        f"{summary['invalid_count']} invalid."
    )
    print(
        "Boards now in use: "
        + ", ".join(f"{ats}={count}" for ats, count in summary["totals"].items())
    )


if __name__ == "__main__":
    main()

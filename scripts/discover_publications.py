#!/usr/bin/env python3
"""Check PubMed and bioRxiv for publications missing from the master BibTeX.

Examples
--------
Preview without changing files::

    python scripts/discover_publications.py --dry-run

Apply high-confidence additions using a 45-day bioRxiv window::

    python scripts/discover_publications.py --lookback-days 45

Run a manual bioRxiv backfill from a specific date::

    python scripts/discover_publications.py --sources biorxiv --biorxiv-start-date 2025-01-01
"""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import sys

from biorxiv_api_compat import install_biorxiv_api_fix

# Install the API compatibility layer before the discovery function constructs
# its HttpClient and BioRxivClient instances.
install_biorxiv_api_fix()

from publication_discovery import (  # noqa: E402
    DiscoveryError,
    discover_publications,
    load_discovery_config,
    render_report,
)


def parse_iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the parent of scripts/)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Configuration file (defaults to <root>/publication_discovery.yml)",
    )
    parser.add_argument(
        "--sources",
        choices=("all", "pubmed", "biorxiv"),
        default="all",
        help="External sources to query",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=None,
        help="Override the configured bioRxiv lookback interval",
    )
    parser.add_argument(
        "--biorxiv-start-date",
        type=parse_iso_date,
        default=None,
        help="Explicit bioRxiv start date; overrides --lookback-days",
    )
    parser.add_argument(
        "--today",
        type=parse_iso_date,
        default=None,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report proposed changes without editing the repository",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write a Markdown report (default: .publication-discovery/report.md)",
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="Write a machine-readable result summary",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    config_path = args.config or (root / "publication_discovery.yml")
    report_path = args.report or (root / ".publication-discovery" / "report.md")
    summary_path = args.summary_json or (root / ".publication-discovery" / "result.json")
    run_date = args.today or date.today()

    try:
        config = load_discovery_config(config_path)
        result = discover_publications(
            root,
            config,
            sources=args.sources,
            lookback_days=args.lookback_days,
            biorxiv_start_date=args.biorxiv_start_date,
            today=run_date,
            dry_run=args.dry_run,
        )

        biorxiv_config = config.get("biorxiv") or {}
        if args.biorxiv_start_date:
            start = args.biorxiv_start_date
        else:
            from datetime import timedelta

            days = int(args.lookback_days or biorxiv_config.get("lookback_days", 21))
            start = run_date - timedelta(days=max(1, days))
        interval = f"{start.isoformat()} to {run_date.isoformat()}"

        report = render_report(
            result,
            run_date=run_date,
            sources=args.sources,
            biorxiv_window=interval,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(result.as_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        print(report)
        print(
            f"Discovery complete: {len(result.additions)} addition(s), "
            f"{len(result.upgrades)} upgrade(s), "
            f"{len(result.skipped)} skipped candidate(s)."
        )
        if args.dry_run and result.changed:
            print("Dry run: no repository files were changed.")
        return 0
    except DiscoveryError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

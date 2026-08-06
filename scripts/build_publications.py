#!/usr/bin/env python3
"""Build and validate publication records for the Boyle Lab website.

Inputs
------
* bibliography/*.bib             authoritative citation data
* publication_metadata/*.yml     website-only metadata and member umids
* _people/*.md                   authoritative person records

Generated outputs
-----------------
* _papers/*.yml                  Jekyll collection consumed by the site
* assets/data/publications.json  machine-readable publication index
* pub.bib                        combined BibTeX file for the CV/downloads

Run ``python scripts/build_publications.py`` after changing any input.  Use
``--check`` in continuous integration to verify that committed outputs are
current without modifying files.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any

from publication_tools import (
    BuildMessage,
    PublicationError,
    build_publication_record,
    combined_bibtex,
    dump_front_matter,
    json_text,
    load_bibliography,
    load_metadata,
    load_people,
    records_to_public_json,
    slugify,
)


GENERATED_NOTICE = "# This directory is generated from bibliography/ and publication_metadata/.\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the parent of scripts/)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate and compare generated files without changing them",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings, including unmatched member aliases, as errors",
    )
    return parser.parse_args()


def expected_outputs(root: Path) -> tuple[dict[Path, str], list[BuildMessage], list[dict[str, Any]]]:
    people, people_messages = load_people(root / "_people")
    metadata, metadata_messages = load_metadata(root / "publication_metadata")
    entries, _source_paths = load_bibliography(root / "bibliography")

    entry_keys = {entry.key for entry in entries}
    metadata_keys = set(metadata)
    missing_metadata = sorted(entry_keys - metadata_keys)
    orphan_metadata = sorted(metadata_keys - entry_keys)
    if missing_metadata:
        preview = ", ".join(missing_metadata[:8])
        remainder = "" if len(missing_metadata) <= 8 else f" (+{len(missing_metadata) - 8} more)"
        raise PublicationError(
            "Every publication must have a website metadata sidecar. Missing metadata for: "
            f"{preview}{remainder}. Run scripts/scaffold_publication_metadata.py "
            "or add the YAML files manually."
        )
    if orphan_metadata:
        preview = ", ".join(orphan_metadata[:8])
        remainder = "" if len(orphan_metadata) <= 8 else f" (+{len(orphan_metadata) - 8} more)"
        raise PublicationError(
            f"Metadata references BibTeX key(s) that do not exist: {preview}{remainder}"
        )

    messages = [*people_messages, *metadata_messages]
    records: list[dict[str, Any]] = []
    slugs: dict[str, str] = {}
    dois: dict[str, str] = {}

    for entry in entries:
        record, record_messages = build_publication_record(entry, metadata[entry.key], people)
        messages.extend(record_messages)

        slug = str(record["slug"])
        if slug in slugs:
            raise PublicationError(
                f"Generated publication slug '{slug}' is shared by '{slugs[slug]}' and '{entry.key}'. "
                "Set a unique slug in one metadata file."
            )
        slugs[slug] = entry.key

        doi = str(record.get("doi") or "").casefold()
        if doi:
            if doi in dois:
                raise PublicationError(
                    f"Duplicate DOI '{doi}' in BibTeX entries '{dois[doi]}' and '{entry.key}'"
                )
            dois[doi] = entry.key

        records.append(record)

    # Use a deterministic newest-first order in JSON and the combined data set.
    records.sort(key=lambda item: (str(item.get("sort_date", "")), str(item.get("bibkey", ""))), reverse=True)

    outputs: dict[Path, str] = {}
    papers_dir = root / "_papers"
    for record in records:
        outputs[papers_dir / f"{record['slug']}.yml"] = dump_front_matter(record)

    outputs[root / "assets" / "data" / "publications.json"] = json_text(
        records_to_public_json(records)
    )
    outputs[root / "pub.bib"] = combined_bibtex(entries)
    return outputs, messages, records


def existing_generated_papers(root: Path) -> set[Path]:
    papers_dir = root / "_papers"
    if not papers_dir.exists():
        return set()
    generated: set[Path] = set()
    for path in papers_dir.glob("*.yml"):
        try:
            prefix = path.read_text(encoding="utf-8", errors="replace")[:300]
        except OSError:
            continue
        if "generated: true" in prefix:
            generated.add(path)
    return generated


def check_outputs(root: Path, outputs: dict[Path, str]) -> list[str]:
    problems: list[str] = []
    expected_paths = set(outputs)

    for path, expected in outputs.items():
        if not path.exists():
            problems.append(f"missing generated file: {path.relative_to(root)}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            problems.append(f"stale generated file: {path.relative_to(root)}")

    stale_papers = existing_generated_papers(root) - expected_paths
    for path in sorted(stale_papers):
        problems.append(f"obsolete generated file: {path.relative_to(root)}")
    return problems


def write_outputs(root: Path, outputs: dict[Path, str]) -> None:
    expected_paths = set(outputs)
    for stale in sorted(existing_generated_papers(root) - expected_paths):
        stale.unlink()

    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def print_messages(messages: list[BuildMessage]) -> int:
    warning_count = 0
    for item in messages:
        stream = sys.stderr if item.level in {"warning", "error"} else sys.stdout
        print(f"{item.level.upper()}: {item.message}", file=stream)
        if item.level == "warning":
            warning_count += 1
    return warning_count


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        outputs, messages, records = expected_outputs(root)
        warning_count = print_messages(messages)

        if args.check:
            problems = check_outputs(root, outputs)
            for problem in problems:
                print(f"ERROR: {problem}", file=sys.stderr)
            if problems:
                print(
                    "Generated publication files are not current. Run: "
                    "python scripts/build_publications.py",
                    file=sys.stderr,
                )
                return 1
        else:
            write_outputs(root, outputs)

        if args.strict and warning_count:
            print(f"ERROR: strict mode rejected {warning_count} warning(s)", file=sys.stderr)
            return 1

        action = "Validated" if args.check else "Generated"
        print(
            f"{action} {len(records)} publications from BibTeX, metadata, and _people records."
        )
        return 0
    except PublicationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

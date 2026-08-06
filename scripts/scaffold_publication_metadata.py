#!/usr/bin/env python3
"""Create reviewable metadata sidecars for new BibTeX publications.

The command conservatively matches full/aliased author names to Michigan
``umid`` records in ``_people``.  It never overwrites an existing sidecar.
Review every generated ``members`` list before running the full build,
especially for consortium bylines and common names.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any, Mapping

from publication_tools import (
    PublicationError,
    author_matches_person,
    dump_plain_yaml,
    infer_member_ids,
    load_bibliography,
    load_metadata,
    load_people,
    parse_authors,
    slugify,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root",
    )
    parser.add_argument(
        "--bibkey",
        action="append",
        default=[],
        help="Create only the specified BibTeX key; may be supplied more than once",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the sidecars that would be created without writing them",
    )
    return parser.parse_args()


def author_ordered_members(
    authors: list[dict[str, Any]],
    inferred: list[str],
    people: Mapping[str, Any],
) -> list[str]:
    remaining = set(inferred)
    ordered: list[str] = []
    for author in authors:
        for umid in list(remaining):
            if author_matches_person(author, people[umid]):
                ordered.append(umid)
                remaining.remove(umid)
                break
    ordered.extend(sorted(remaining))
    return ordered


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        people, messages = load_people(root / "_people")
        for message in messages:
            print(f"{message.level.upper()}: {message.message}", file=sys.stderr)
        metadata, _ = load_metadata(root / "publication_metadata")
        entries, _ = load_bibliography(root / "bibliography")

        requested = set(args.bibkey)
        known_keys = {entry.key for entry in entries}
        unknown_requested = requested - known_keys
        if unknown_requested:
            raise PublicationError(
                "Requested BibTeX key(s) do not exist: " + ", ".join(sorted(unknown_requested))
            )

        created = 0
        for entry in entries:
            if requested and entry.key not in requested:
                continue
            if entry.key in metadata:
                continue

            authors = parse_authors(entry.fields.get("author", ""))
            inferred = infer_member_ids(authors, people)
            members = author_ordered_members(authors, inferred, people)
            sidecar = {"bibkey": entry.key, "members": members}
            destination = root / "publication_metadata" / f"{slugify(entry.key)}.yml"
            content = dump_plain_yaml(sidecar)

            if args.dry_run:
                print(f"--- {destination.relative_to(root)}\n{content}")
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8")
                print(f"Created {destination.relative_to(root)}")
            if not members:
                print(
                    f"WARNING: {entry.key} has no inferred lab members; add members and "
                    "member_roles manually if this is a consortium/group byline.",
                    file=sys.stderr,
                )
            created += 1

        if created == 0:
            print("No missing publication metadata sidecars.")
        else:
            verb = "Would create" if args.dry_run else "Created"
            print(f"{verb} {created} metadata sidecar(s). Review them before building.")
        return 0
    except PublicationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

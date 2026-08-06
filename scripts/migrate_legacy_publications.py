#!/usr/bin/env python3
"""One-time migration from the site's legacy BibTeX2HTML/YAML publication data.

This script is included for reproducibility.  It can:

1. reconstruct ``bibliography/publications.bib`` from
   ``_includes/pub/pub_bib.html``;
2. create one ``publication_metadata/*.yml`` sidecar per BibTeX entry;
3. carry forward member IDs and website links from the former hand-maintained
   ``_papers/*.yml`` files; and
4. optionally remove those legacy ``_papers`` files after migration.

Normal updates should use ``scripts/build_publications.py`` instead.
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
import re
import sys
from typing import Any, Mapping

from publication_tools import (
    PublicationError,
    dump_plain_yaml,
    infer_member_ids,
    latex_to_text,
    load_bibliography,
    load_people,
    load_yaml_file,
    normalize_doi,
    normalize_for_match,
    parse_authors,
    slugify,
)


LEGACY_AUTHOR_LABEL_TO_UMID = {
    "pavlovic k": "katrinp",
    "mcdonald tl": "torrin",
    "diehl ag": "adadiehl",
    "switzenberg ja": "jswitzen",
    "sherpa r": "rintsen",
    "mcbean b": "bmcbean",
    "dong s": "shengchd",
    "castro cp": "castrocp",
    "losh sj": "slosh",
    "mumm c": "crmumm",
    "crone b": "crone",
    "parana p": "prparana",
    "van deynze k": "kvandeyn",
    "zhao n": "samzhao",
    "holmes mj": "mhholmes",
    "farnum ga": "gregfar",
    "drexel ml": "melyssae",
    "ouyang n": "nouyang",
    "nishizaki ss": "ssnishi",
    "sethuraman s": "shriyas",
    "morterud c": "cmorteru",
    "williams c": "coltenw",
    "asman c": "casman",
    "amemiya hm": "hamemiya",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the reconstructed BibTeX file and existing metadata sidecars",
    )
    parser.add_argument(
        "--create-missing",
        action="store_true",
        help="Only create metadata sidecars that are currently missing",
    )
    parser.add_argument(
        "--replace-legacy-papers",
        action="store_true",
        help="Delete old hand-maintained _papers/*.yml files after sidecars are written",
    )
    return parser.parse_args()


def strip_html_tags(value: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", value))


def reconstruct_bibtex(root: Path, force: bool) -> Path:
    output = root / "bibliography" / "publications.bib"
    if output.exists() and not force:
        return output

    legacy = root / "_includes" / "pub" / "pub_bib.html"
    if not legacy.exists():
        raise PublicationError(
            f"Cannot reconstruct BibTeX because the legacy file is missing: {legacy}"
        )
    text = legacy.read_text(encoding="utf-8-sig")
    blocks = re.findall(r"<pre>\s*(.*?)\s*</pre>", text, flags=re.I | re.S)
    if not blocks:
        raise PublicationError(f"No BibTeX <pre> blocks found in {legacy}")

    entries = [strip_html_tags(block).strip() for block in blocks]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "% Boyle Lab publication bibliography.\n"
        "% This is the authoritative citation source for the website and CV.\n\n"
        + "\n\n".join(entries)
        + "\n",
        encoding="utf-8",
    )
    print(f"Reconstructed {len(entries)} BibTeX entries in {output.relative_to(root)}")
    return output


def legacy_html_members(root: Path) -> dict[str, list[str]]:
    path = root / "_includes" / "pub" / "pub.html"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    result: dict[str, list[str]] = {}
    for row in re.findall(r"<tr\b.*?</tr>", text, flags=re.I | re.S):
        key_match = re.search(r"<a\s+name=[\"']([^\"']+)", row, flags=re.I)
        if not key_match:
            continue
        key = html.unescape(key_match.group(1))
        member_ids: list[str] = []
        for raw_label in re.findall(r"<u>(.*?)</u>", row, flags=re.I | re.S):
            label = normalize_for_match(strip_html_tags(raw_label).replace("*", ""))
            umid = LEGACY_AUTHOR_LABEL_TO_UMID.get(label)
            if umid and umid not in member_ids:
                member_ids.append(umid)
        # The legacy formatter used bold, rather than underline, for Alan.
        if re.search(r"<b>\s*Boyle\s+AP\s*</b>", row, flags=re.I) and "apboyle" not in member_ids:
            member_ids.append("apboyle")
        result[key] = member_ids
    return result


def load_legacy_papers(root: Path) -> tuple[list[tuple[Path, dict[str, Any]]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    records: list[tuple[Path, dict[str, Any]]] = []
    by_doi: dict[str, dict[str, Any]] = {}
    by_title: dict[str, dict[str, Any]] = {}
    for path in sorted((root / "_papers").glob("*.yml")):
        data = load_yaml_file(path)
        # Skip records that have already been generated by the new pipeline.
        if data.get("generated") is True:
            continue
        records.append((path, data))
        doi = normalize_doi(data.get("doi") or "").casefold()
        title = normalize_for_match(str(data.get("title") or ""))
        if doi:
            by_doi[doi] = data
        if title:
            by_title[title] = data
    return records, by_doi, by_title


def match_legacy_record(entry_fields: Mapping[str, str], by_doi: Mapping[str, dict[str, Any]], by_title: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    doi = normalize_doi(entry_fields.get("doi") or "").casefold()
    if doi and doi in by_doi:
        return dict(by_doi[doi])
    title = normalize_for_match(latex_to_text(entry_fields.get("title") or ""))
    if title and title in by_title:
        return dict(by_title[title])
    return {}


def author_ordered_members(authors: list[dict[str, Any]], inferred: list[str], people: Mapping[str, Any]) -> list[str]:
    remaining = set(inferred)
    ordered: list[str] = []
    # infer_member_ids is conservative, but sort its result in publication order.
    from publication_tools import author_matches_person

    for author in authors:
        for umid in list(remaining):
            if author_matches_person(author, people[umid]):
                ordered.append(umid)
                remaining.remove(umid)
                break
    ordered.extend(sorted(remaining))
    return ordered


def build_metadata(
    entry: Any,
    people: Mapping[str, Any],
    legacy_markup_members: Mapping[str, list[str]],
    legacy_record: Mapping[str, Any],
) -> dict[str, Any]:
    authors = parse_authors(entry.fields.get("author", ""))
    inferred = infer_member_ids(authors, people)
    members = author_ordered_members(authors, inferred, people)

    for umid in legacy_markup_members.get(entry.key, []):
        if umid in people and umid not in members:
            members.append(umid)
    for umid in legacy_record.get("members") or []:
        umid = str(umid)
        if umid in people and umid not in members:
            members.append(umid)

    metadata: dict[str, Any] = {
        "bibkey": entry.key,
        "members": members,
    }

    links: dict[str, Any] = {}
    if legacy_record.get("github"):
        links["code"] = legacy_record["github"]
    if legacy_record.get("data"):
        links["data"] = legacy_record["data"]
    if legacy_record.get("news"):
        links["news"] = legacy_record["news"]
    if legacy_record.get("google_scholar"):
        links["scholar"] = legacy_record["google_scholar"]
    if links:
        metadata["links"] = links

    # Carry forward fields only when the reconstructed BibTeX does not already
    # contain them.
    for key in ("abstract", "url", "pdf", "biorxiv", "doi", "PMID"):
        source_key = key.casefold()
        bib_has_value = bool(entry.fields.get(source_key))
        if legacy_record.get(key) not in (None, "", []) and not bib_has_value:
            metadata[key] = legacy_record[key]

    return metadata


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        reconstruct_bibtex(root, args.force)
        people, messages = load_people(root / "_people")
        for message in messages:
            print(f"{message.level.upper()}: {message.message}", file=sys.stderr)

        entries, _paths = load_bibliography(root / "bibliography")
        markup_members = legacy_html_members(root)
        legacy_files, legacy_by_doi, legacy_by_title = load_legacy_papers(root)
        metadata_dir = root / "publication_metadata"
        metadata_dir.mkdir(parents=True, exist_ok=True)

        created = 0
        skipped = 0
        for entry in entries:
            path = metadata_dir / f"{slugify(entry.key)}.yml"
            if path.exists() and not args.force:
                skipped += 1
                continue
            legacy_record = match_legacy_record(entry.fields, legacy_by_doi, legacy_by_title)
            metadata = build_metadata(entry, people, markup_members, legacy_record)
            path.write_text(dump_plain_yaml(metadata), encoding="utf-8")
            created += 1

        if args.replace_legacy_papers:
            for path, _data in legacy_files:
                path.unlink()
            print(f"Removed {len(legacy_files)} legacy _papers YAML files")

        print(
            f"Created {created} publication metadata sidecars; skipped {skipped} existing sidecars."
        )
        return 0
    except PublicationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

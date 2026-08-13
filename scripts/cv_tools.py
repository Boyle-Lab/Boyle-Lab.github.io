#!/usr/bin/env python3
"""Utilities for generating the Boyle CV from the website publication data.

The CV deliberately uses the same three sources as the website:

* ``bibliography/publications.bib`` for citation data;
* ``publication_metadata/*.yml`` for publication-to-member relationships; and
* ``_people/*.md`` for canonical member identities.

The resulting LaTeX publication list highlights Alan Boyle in bold and other
Boyle Lab byline authors with an underline.  No author names are hard-coded in
this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from publication_tools import (
    BibEntry,
    BuildMessage,
    Person,
    PublicationError,
    attach_members_to_authors,
    author_matches_person,
    build_publication_record,
    latex_to_text,
    load_bibliography,
    load_metadata,
    load_people,
    parse_authors,
    parse_bibtex,
)


PRINCIPAL_INVESTIGATOR_UMID = "apboyle"


@dataclass(slots=True)
class CVPublication:
    """One validated publication with CV-specific author annotations."""

    entry: BibEntry
    record: dict[str, Any]
    authors: list[dict[str, Any]]


_LATEX_ESCAPES = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_LATEX_PATTERN = re.compile("|".join(re.escape(value) for value in _LATEX_ESCAPES))


def tex_escape(value: Any) -> str:
    """Escape plain Unicode text for XeLaTeX while retaining readable glyphs."""
    text = latex_to_text(value)
    return _LATEX_PATTERN.sub(lambda match: _LATEX_ESCAPES[match.group(0)], text)


def tex_href(url: str, label: str) -> str:
    """Return a robust hyperlink without interpreting URL punctuation as TeX."""
    clean_url = str(url or "").strip()
    if not clean_url:
        return tex_escape(label)
    # The repository URLs do not contain braces.  Reject them rather than
    # producing malformed TeX if a future record introduces one.
    if "{" in clean_url or "}" in clean_url:
        raise PublicationError(f"CV hyperlink contains an unsupported brace: {clean_url}")
    return rf"\href{{\detokenize{{{clean_url}}}}}{{{tex_escape(label)}}}"


def _metadata_author_records(
    entry: BibEntry,
    metadata: Mapping[str, Any],
    people: Mapping[str, Person],
) -> tuple[list[dict[str, Any]], list[str]]:
    raw_member_ids = metadata.get("members") or []
    if not isinstance(raw_member_ids, (list, tuple)):
        raw_member_ids = [raw_member_ids]
    member_ids = [str(value).strip() for value in raw_member_ids if str(value).strip()]
    raw_authors = str(metadata.get("author") or entry.fields.get("author") or "")
    authors = parse_authors(raw_authors)
    overrides = metadata.get("author_member_map") or {}
    if not isinstance(overrides, dict):
        raise PublicationError(f"{metadata.get('_source')}: author_member_map must be a mapping")
    authors, _matched, unmatched = attach_members_to_authors(
        authors,
        member_ids,
        people,
        overrides,
    )
    member_roles = metadata.get("member_roles") or {}
    if not isinstance(member_roles, dict):
        raise PublicationError(f"{metadata.get('_source')}: member_roles must be a mapping")
    unaccounted = [
        umid
        for umid in unmatched
        if str(member_roles.get(umid) or "").strip().lower().replace("-", "_")
        not in {"consortium", "contributor", "group_author", "non_byline"}
    ]
    return authors, unaccounted


def load_cv_publications(
    root: Path,
) -> tuple[list[CVPublication], list[BuildMessage], dict[str, Person]]:
    """Load and validate every website publication for CV rendering."""
    people, people_messages = load_people(root / "_people")
    metadata, metadata_messages = load_metadata(root / "publication_metadata")
    entries, _ = load_bibliography(root / "bibliography")

    entry_keys = {entry.key for entry in entries}
    metadata_keys = set(metadata)
    missing = sorted(entry_keys - metadata_keys)
    orphaned = sorted(metadata_keys - entry_keys)
    if missing:
        raise PublicationError(
            "CV generation requires one publication sidecar per BibTeX entry. Missing: "
            + ", ".join(missing)
        )
    if orphaned:
        raise PublicationError(
            "CV generation found sidecars without BibTeX entries: " + ", ".join(orphaned)
        )

    messages = [*people_messages, *metadata_messages]
    publications: list[CVPublication] = []
    for entry in entries:
        sidecar = metadata[entry.key]
        record, record_messages = build_publication_record(entry, sidecar, people)
        messages.extend(record_messages)
        authors, unmatched = _metadata_author_records(entry, sidecar, people)
        for umid in unmatched:
            messages.append(
                BuildMessage(
                    "warning",
                    f"{sidecar.get('_source')}: member '{umid}' could not be attached to "
                    f"a byline author for CV entry '{entry.key}'",
                )
            )
        publications.append(CVPublication(entry=entry, record=record, authors=authors))

    publications.sort(
        key=lambda item: (
            str(item.record.get("sort_date") or ""),
            str(item.record.get("bibkey") or ""),
        ),
        reverse=True,
    )
    return publications, messages, people


def _author_marker(author: Mapping[str, Any]) -> str:
    marker = ""
    if author.get("equal_contrib"):
        marker += "*"
    if author.get("co_senior"):
        marker += r"\textsuperscript{\(\dagger\)}"
    return marker


def format_cv_author(author: Mapping[str, Any]) -> str:
    """Format one author using website-derived member identity information."""
    name = tex_escape(author.get("citation_name") or author.get("full_name") or "")
    member_id = str(author.get("member_id") or "")
    if member_id == PRINCIPAL_INVESTIGATOR_UMID:
        name = rf"\textbf{{{name}}}"
    elif member_id:
        name = rf"\underline{{{name}}}"
    return _author_marker(author) + name


def format_cv_authors(authors: Sequence[Mapping[str, Any]]) -> str:
    return ", ".join(format_cv_author(author) for author in authors)


def _venue_text(publication: CVPublication) -> str:
    record = publication.record
    entry = publication.entry
    journal = str(record.get("journal") or "").strip()
    year = int(record.get("year") or 0)
    volume = str(record.get("volume") or "").strip()
    number = str(record.get("number") or "").strip()
    pages = str(record.get("pages") or "").strip()
    status = str(record.get("status") or "published")

    chunks: list[str] = []
    if journal:
        chunks.append(rf"\textit{{{tex_escape(journal)}}}")
    elif entry.entry_type in {"inproceedings", "conference", "proceedings"}:
        booktitle = tex_escape(entry.fields.get("booktitle") or "Conference proceedings")
        chunks.append(rf"\textit{{{booktitle}}}")

    if year:
        if chunks:
            chunks[-1] += f" {year}"
        else:
            chunks.append(str(year))

    citation_tail = ""
    if volume:
        citation_tail = tex_escape(volume)
        if number:
            citation_tail += f"({tex_escape(number)})"
        if pages:
            citation_tail += f":{tex_escape(pages)}"
    elif pages:
        if entry.entry_type in {"inproceedings", "conference", "proceedings"}:
            citation_tail = f"pp. {tex_escape(pages)}"
        else:
            citation_tail = tex_escape(pages)
    if citation_tail:
        chunks.append(citation_tail)

    if status == "in_press":
        chunks.append("in press")
    return ", ".join(chunks)


def format_cv_publication(publication: CVPublication) -> str:
    record = publication.record
    authors = format_cv_authors(publication.authors)
    title = tex_escape(record.get("title") or "").strip()
    venue = _venue_text(publication)

    if title.endswith((".", "?", "!")):
        quoted_title = f"``{title}''"
    else:
        quoted_title = f"``{title}.''"
    citation = f"{authors}. {quoted_title}"
    if venue:
        citation += f" {venue}."

    pmid = str(record.get("PMID") or "").strip()
    doi = str(record.get("doi") or "").strip()
    primary_url = str(record.get("primary_url") or "").strip()
    if pmid:
        citation += " " + tex_href(
            f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            f"PMID: {pmid}",
        ) + "."
    elif doi:
        citation += " " + tex_href(f"https://doi.org/{doi}", f"doi: {doi}") + "."
    elif primary_url:
        citation += " " + tex_href(primary_url, "Publication link") + "."
    return citation


def render_publications_tex(publications: Sequence[CVPublication]) -> str:
    lines = [
        "% Generated by scripts/build_cv.py. Do not edit directly.",
        "% Source: bibliography/publications.bib + publication_metadata + _people.",
        r"\section*{Publications}",
        r"\begin{flushright}",
        r"\scriptsize * co-first authorship; \(\dagger\) co-senior authorship; "
        r"\underline{underline} indicates Boyle Lab members",
        r"\end{flushright}",
        r"\begin{enumerate}[label={[\arabic*]},leftmargin=2.7em,labelsep=0.55em,itemsep=0.65em,parsep=0pt,topsep=0.25em]",
    ]
    for publication in publications:
        lines.append(r"\item " + format_cv_publication(publication))
    lines.extend([r"\end{enumerate}", ""])
    return "\n".join(lines)


def load_patent_entries(path: Path) -> list[BibEntry]:
    if not path.exists():
        return []
    entries = parse_bibtex(path.read_text(encoding="utf-8-sig"), source=path)
    entries.sort(
        key=lambda entry: (
            int(re.search(r"\d{4}", latex_to_text(entry.fields.get("year") or "0")).group())
            if re.search(r"\d{4}", latex_to_text(entry.fields.get("year") or ""))
            else 0,
            entry.key,
        ),
        reverse=True,
    )
    return entries


def _format_patent_authors(entry: BibEntry, principal: Person) -> str:
    formatted: list[str] = []
    for author in parse_authors(entry.fields.get("author") or ""):
        name = tex_escape(author.get("citation_name") or "")
        if author_matches_person(author, principal):
            name = rf"\textbf{{{name}}}"
        formatted.append(name)
    return ", ".join(formatted)


def format_patent(entry: BibEntry, principal: Person) -> str:
    authors = _format_patent_authors(entry, principal)
    title = tex_escape(entry.fields.get("title") or "")
    number = tex_escape(entry.fields.get("number") or "")
    year = tex_escape(entry.fields.get("year") or "")
    url = latex_to_text(entry.fields.get("url") or "")
    text = f"{authors}. ``{title}.''"
    if number:
        text += f" {number}"
    if year:
        text += f", {year}"
    text += "."
    if url:
        text += " " + tex_href(url, "Patent record") + "."
    return text


def render_patents_tex(entries: Sequence[BibEntry], people: Mapping[str, Person]) -> str:
    lines = [
        "% Generated by scripts/build_cv.py. Do not edit directly.",
        "% Source: cv/patents.bib.",
    ]
    if not entries:
        return "\n".join(lines + [""])
    principal = people.get(PRINCIPAL_INVESTIGATOR_UMID)
    if principal is None:
        raise PublicationError(
            f"CV generation requires _people record '{PRINCIPAL_INVESTIGATOR_UMID}'"
        )
    lines.extend(
        [
            r"\section*{Patents}",
            r"\begin{enumerate}[label={[\arabic*]},leftmargin=2.7em,labelsep=0.55em,itemsep=0.65em,parsep=0pt,topsep=0.25em]",
        ]
    )
    for entry in entries:
        lines.append(r"\item " + format_patent(entry, principal))
    lines.extend([r"\end{enumerate}", ""])
    return "\n".join(lines)


def expected_cv_outputs(root: Path) -> tuple[dict[Path, str], list[BuildMessage], int]:
    publications, messages, people = load_cv_publications(root)
    patents = load_patent_entries(root / "cv" / "patents.bib")
    outputs = {
        root / "cv" / "generated" / "publications.tex": render_publications_tex(publications),
        root / "cv" / "generated" / "patents.tex": render_patents_tex(patents, people),
    }
    return outputs, messages, len(publications)

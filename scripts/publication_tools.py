#!/usr/bin/env python3
"""Shared utilities for the Boyle Lab publication data pipeline.

The website keeps bibliographic data in BibTeX, website-only metadata in
``publication_metadata/*.yml``, and person identities in ``_people/*.md``.
This module parses and joins those sources without requiring a heavy BibTeX
library.  It intentionally supports the subset of BibTeX used by the lab's
bibliography, including nested braces, quoted values, and ``#`` concatenation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import hashlib
import html
import re
import unicodedata
from typing import Any, Mapping, Sequence

import yaml


class PublicationError(RuntimeError):
    """Raised when publication source data are invalid."""


@dataclass(slots=True)
class BibEntry:
    entry_type: str
    key: str
    fields: dict[str, str]
    raw: str
    source: Path | None = None


@dataclass(slots=True)
class Person:
    umid: str
    name: str
    source: Path
    url: str
    publish: bool = True


@dataclass(slots=True)
class BuildMessage:
    level: str
    message: str


MONTHS: dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

CORPORATE_AUTHOR_WORDS = {
    "consortium",
    "group",
    "network",
    "project",
    "initiative",
    "investigators",
    "collaboration",
    "committee",
    "working group",
}

NON_BYLINE_MEMBER_ROLES = {"consortium", "contributor", "group_author", "non_byline"}
VALID_STATUSES = {"published", "preprint", "in_press"}
VALID_PUBLICATION_TYPES = {"article", "chapter", "conference"}
SAFE_BIBKEY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
DEPRECATED_METADATA_FIELDS = {"slug", "legacy_bibkeys"}
DEPRECATED_PERSON_FIELDS = {"publication_names", "author_aliases"}


# ---------------------------------------------------------------------------
# YAML/front-matter utilities
# ---------------------------------------------------------------------------


def load_yaml_file(path: Path) -> dict[str, Any]:
    """Load either plain YAML or a Jekyll front-matter document."""
    text = path.read_text(encoding="utf-8-sig")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) < 3:
            raise PublicationError(f"Malformed front matter in {path}")
        text = parts[1]
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise PublicationError(f"Could not parse YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise PublicationError(f"Expected a YAML mapping in {path}")
    return data


def load_people(people_dir: Path) -> tuple[dict[str, Person], list[BuildMessage]]:
    people: dict[str, Person] = {}
    messages: list[BuildMessage] = []

    for path in sorted(people_dir.glob("*.md")):
        data = load_yaml_file(path)
        deprecated = sorted(DEPRECATED_PERSON_FIELDS.intersection(data))
        if deprecated:
            raise PublicationError(
                f"{path}: deprecated person field(s): {', '.join(deprecated)}. "
                "Map historical or publication-specific bylines in the relevant "
                "publication_metadata sidecar using author_member_map."
            )
        umid = str(data.get("umid") or "").strip()
        if not umid:
            messages.append(BuildMessage("warning", f"{path}: missing umid; ignored for publication matching"))
            continue

        name = str(data.get("name") or path.stem.replace("_", " ")).strip()
        publish = bool(data.get("publish", True))
        configured_url = str(data.get("permalink") or "").strip()
        url = configured_url or f"/people/{path.stem}/"
        if umid in people:
            other = people[umid]
            raise PublicationError(
                f"Duplicate umid '{umid}' in {other.source} and {path}. "
                "Each Michigan umid must identify one canonical _people record."
            )

        people[umid] = Person(
            umid=umid,
            name=name,
            source=path,
            url=url,
            publish=publish,
        )

    return people, messages


def load_metadata(metadata_dir: Path) -> tuple[dict[str, dict[str, Any]], list[BuildMessage]]:
    metadata: dict[str, dict[str, Any]] = {}
    messages: list[BuildMessage] = []
    if not metadata_dir.exists():
        return metadata, messages

    for path in sorted(metadata_dir.glob("*.yml")) + sorted(metadata_dir.glob("*.yaml")):
        data = load_yaml_file(path)
        deprecated = sorted(DEPRECATED_METADATA_FIELDS.intersection(data))
        if deprecated:
            raise PublicationError(
                f"{path}: deprecated metadata field(s): {', '.join(deprecated)}. "
                "The stable BibTeX key is now the only publication identifier."
            )
        key = str(data.get("bibkey") or "").strip()
        if not key:
            raise PublicationError(f"{path}: required field 'bibkey' is missing")
        if key in metadata:
            raise PublicationError(
                f"Duplicate metadata for BibTeX key '{key}' in "
                f"{metadata[key]['_source']} and {path}"
            )
        data["_source"] = path
        metadata[key] = data
    return metadata, messages


# ---------------------------------------------------------------------------
# BibTeX parser
# ---------------------------------------------------------------------------


def _is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    index -= 1
    while index >= 0 and text[index] == "\\":
        backslashes += 1
        index -= 1
    return bool(backslashes % 2)


def _scan_balanced(text: str, start: int, opener: str, closer: str) -> int:
    """Return the index just after the balanced region beginning at start."""
    if text[start] != opener:
        raise PublicationError("Internal parser error: unbalanced scan start")
    depth = 1
    i = start + 1
    in_quote = False
    while i < len(text):
        ch = text[i]
        if ch == '"' and not _is_escaped(text, i):
            in_quote = not in_quote
        if not in_quote or opener == "{":
            if ch == opener and not _is_escaped(text, i):
                depth += 1
            elif ch == closer and not _is_escaped(text, i):
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    raise PublicationError(f"Unclosed BibTeX entry beginning near character {start}")


def _split_first_top_level_comma(content: str) -> tuple[str, str]:
    brace_depth = 0
    in_quote = False
    for i, ch in enumerate(content):
        if ch == '"' and not _is_escaped(content, i):
            in_quote = not in_quote
        elif not in_quote:
            if ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth = max(0, brace_depth - 1)
            elif ch == "," and brace_depth == 0:
                return content[:i], content[i + 1 :]
    raise PublicationError("BibTeX entry is missing the comma after its citation key")


def _parse_braced_value(text: str, start: int) -> tuple[str, int]:
    end = _scan_balanced(text, start, "{", "}")
    return text[start + 1 : end - 1], end


def _parse_quoted_value(text: str, start: int) -> tuple[str, int]:
    i = start + 1
    brace_depth = 0
    value: list[str] = []
    while i < len(text):
        ch = text[i]
        if ch == "{" and not _is_escaped(text, i):
            brace_depth += 1
        elif ch == "}" and not _is_escaped(text, i):
            brace_depth = max(0, brace_depth - 1)
        elif ch == '"' and brace_depth == 0 and not _is_escaped(text, i):
            return "".join(value), i + 1
        value.append(ch)
        i += 1
    raise PublicationError("Unclosed quoted BibTeX value")


def _parse_bare_value(text: str, start: int) -> tuple[str, int]:
    i = start
    while i < len(text) and text[i] not in ",#\r\n":
        i += 1
    return text[start:i].strip(), i


def _parse_fields(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    i = 0
    length = len(body)

    while i < length:
        while i < length and (body[i].isspace() or body[i] == ","):
            i += 1
        if i >= length:
            break

        name_start = i
        while i < length and (body[i].isalnum() or body[i] in "_-:"):
            i += 1
        field_name = body[name_start:i].strip().lower()
        if not field_name:
            snippet = body[i : i + 80].replace("\n", " ")
            raise PublicationError(f"Could not parse BibTeX field near: {snippet}")

        while i < length and body[i].isspace():
            i += 1
        if i >= length or body[i] != "=":
            raise PublicationError(f"BibTeX field '{field_name}' is missing '='")
        i += 1

        chunks: list[str] = []
        while True:
            while i < length and body[i].isspace():
                i += 1
            if i >= length:
                break
            if body[i] == "{":
                chunk, i = _parse_braced_value(body, i)
            elif body[i] == '"':
                chunk, i = _parse_quoted_value(body, i)
            else:
                chunk, i = _parse_bare_value(body, i)
            chunks.append(chunk)

            while i < length and body[i].isspace():
                i += 1
            if i < length and body[i] == "#":
                i += 1
                continue
            break

        fields[field_name] = "".join(chunks).strip()
        while i < length and body[i].isspace():
            i += 1
        if i < length and body[i] == ",":
            i += 1

    return fields


def parse_bibtex(text: str, source: Path | None = None) -> list[BibEntry]:
    entries: list[BibEntry] = []
    i = 0
    while True:
        match = re.search(r"@([A-Za-z]+)\s*([\{\(])", text[i:])
        if not match:
            break
        entry_start = i + match.start()
        entry_type = match.group(1).lower()
        opener = match.group(2)
        closer = "}" if opener == "{" else ")"
        open_index = i + match.end() - 1
        end = _scan_balanced(text, open_index, opener, closer)
        raw = text[entry_start:end].strip()
        content = text[open_index + 1 : end - 1].strip()
        i = end

        if entry_type in {"comment", "preamble", "string"}:
            continue
        key_text, body = _split_first_top_level_comma(content)
        key = key_text.strip()
        if not key:
            raise PublicationError(f"Empty BibTeX key in {source or '<text>'}")
        entries.append(
            BibEntry(
                entry_type=entry_type,
                key=key,
                fields=_parse_fields(body),
                raw=raw,
                source=source,
            )
        )
    return entries


def load_bibliography(bibliography_dir: Path) -> tuple[list[BibEntry], list[Path]]:
    paths = sorted(bibliography_dir.glob("*.bib"))
    if not paths:
        raise PublicationError(f"No .bib files found in {bibliography_dir}")

    entries: list[BibEntry] = []
    seen: dict[str, Path | None] = {}
    for path in paths:
        parsed = parse_bibtex(path.read_text(encoding="utf-8-sig"), source=path)
        for entry in parsed:
            if not SAFE_BIBKEY_PATTERN.fullmatch(entry.key):
                raise PublicationError(
                    f"Unsafe BibTeX key '{entry.key}' in {path}. Citation keys must begin "
                    "with a letter and contain only ASCII letters and digits; use the "
                    "FirstAuthorYearMnemonic convention (for example, "
                    "Pavlovic2026FiberTEnCATS)."
                )
            if entry.key in seen:
                raise PublicationError(
                    f"Duplicate BibTeX key '{entry.key}' in {seen[entry.key]} and {path}"
                )
            seen[entry.key] = path
            entries.append(entry)
    return entries, paths


# ---------------------------------------------------------------------------
# Text and author normalization
# ---------------------------------------------------------------------------


_LATEX_SIMPLE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"{\textquoteright}", "’"),
    (r"{\textquoteleft}", "‘"),
    (r"{\textquotedblleft}", "“"),
    (r"{\textquotedblright}", "”"),
    (r"{\textendash}", "–"),
    (r"{\textemdash}", "—"),
    (r"{\textgreater}", ">"),
    (r"{\textless}", "<"),
    (r"{\texttimes}", "×"),
    (r"{\aa}", "å"),
    (r"{\AA}", "Å"),
    (r"{\o}", "ø"),
    (r"{\O}", "Ø"),
    (r"\&", "&"),
    (r"\%", "%"),
    (r"\_", "_"),
    (r"\#", "#"),
    (r"\$", "$"),
    (r"\textgreater", ">"),
    (r"\textless", "<"),
    (r"\textendash", "–"),
    (r"\textemdash", "—"),
    (r"\texttimes", "×"),
    (r"\ ", " "),
)

_ACCENTS: dict[str, str] = {
    "'": "\u0301",
    "`": "\u0300",
    '"': "\u0308",
    "^": "\u0302",
    "~": "\u0303",
    "=": "\u0304",
    ".": "\u0307",
    "u": "\u0306",
    "v": "\u030C",
    "H": "\u030B",
    "c": "\u0327",
    "k": "\u0328",
    "r": "\u030A",
}


def latex_to_text(value: Any) -> str:
    """Convert common BibTeX/LaTeX text markup to readable Unicode."""
    if value is None:
        return ""
    text = html.unescape(str(value)).replace("\u00a0", " ")
    for source, replacement in _LATEX_SIMPLE_REPLACEMENTS:
        text = text.replace(source, replacement)

    # Commands whose braces are only presentational.
    wrapper_pattern = re.compile(
        r"\\(?:textit|textbf|emph|mathrm|mathbf|operatorname|textrm|texttt|textsuperscript|textsubscript)\s*\{([^{}]*)\}"
    )
    previous = None
    while previous != text:
        previous = text
        text = wrapper_pattern.sub(r"\1", text)

    # TeX accents, with or without braces: \'{e}, \'e, \c{c}, etc.
    accent_pattern = re.compile(r"\\([\'`\"\^~=\.uvHckr])\s*\{?([A-Za-z])\}?")

    def replace_accent(match: re.Match[str]) -> str:
        mark = _ACCENTS.get(match.group(1))
        if not mark:
            return match.group(2)
        return unicodedata.normalize("NFC", match.group(2) + mark)

    text = accent_pattern.sub(replace_accent, text)
    text = re.sub(r"\\(?:url|href)\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[A-Za-z]+\*?", "", text)
    text = text.replace("{", "").replace("}", "")
    text = text.replace("~", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_for_match(value: str) -> str:
    text = latex_to_text(value)
    text = re.sub(r",?\s*(?:Ph\.?D\.?|M\.?D\.?|M\.?S\.?|B\.?S\.?)\s*$", "", text, flags=re.I)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def slugify(value: str) -> str:
    value = normalize_for_match(value).replace(" ", "-")
    value = re.sub(r"-+", "-", value).strip("-")
    return value or hashlib.sha1(str(value).encode("utf-8")).hexdigest()[:12]


def split_authors(raw: str) -> list[str]:
    authors: list[str] = []
    start = 0
    brace_depth = 0
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth = max(0, brace_depth - 1)
        elif brace_depth == 0 and raw[i : i + 5].casefold() == " and ":
            authors.append(raw[start:i].strip())
            i += 5
            start = i
            continue
        i += 1
    authors.append(raw[start:].strip())
    return [author for author in authors if author]


def _strip_contribution_markers(raw_name: str) -> tuple[str, bool, bool]:
    equal = bool(re.search(r"(^|\s)\*", raw_name))
    senior = bool(re.search(r"\{?\\dag\}?", raw_name))
    cleaned = re.sub(r"\{?\\dag\}?", "", raw_name)
    cleaned = cleaned.replace("*", "")
    return cleaned.strip(), equal, senior


def _is_corporate_author(cleaned: str) -> bool:
    normalized = normalize_for_match(cleaned)
    if cleaned.strip().startswith("{") and cleaned.strip().endswith("}") and "," not in cleaned:
        return True
    return any(word in normalized for word in CORPORATE_AUTHOR_WORDS)


def parse_author(raw_name: str) -> dict[str, Any]:
    cleaned, equal, senior = _strip_contribution_markers(raw_name)
    cleaned_text = latex_to_text(cleaned)
    corporate = _is_corporate_author(cleaned)

    family = ""
    given = ""
    if corporate:
        family = cleaned_text
    elif "," in cleaned_text:
        family, given = [part.strip() for part in cleaned_text.split(",", 1)]
    else:
        parts = cleaned_text.split()
        if len(parts) == 1:
            family = parts[0]
        elif len(parts) > 1:
            family = parts[-1]
            given = " ".join(parts[:-1])

    initials = "".join(
        part[0].upper()
        for part in re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", given)
        if part
    )
    citation_name = family if corporate else f"{family} {initials}".strip()
    full_name = family if corporate else f"{given} {family}".strip()

    return {
        "raw": raw_name,
        "family": family,
        "given": given,
        "initials": initials,
        "citation_name": citation_name,
        "full_name": full_name,
        "corporate": corporate,
        "equal_contrib": equal,
        "co_senior": senior,
    }


def parse_authors(raw: str) -> list[dict[str, Any]]:
    return [parse_author(name) for name in split_authors(raw)]


def _name_signature(name: str) -> tuple[str, str, str]:
    parsed = parse_author(name)
    family = normalize_for_match(parsed["family"]).replace(" ", "")
    given = normalize_for_match(parsed["given"])
    given_tokens = given.split()
    first = given_tokens[0] if given_tokens else ""
    initials = "".join(token[0] for token in given_tokens if token)
    return family, first, initials


def person_name_signatures(person: Person) -> list[tuple[str, str, str]]:
    names = [person.name]
    signatures: list[tuple[str, str, str]] = []
    for name in names:
        # Person display names are generally given-name first.  Add both a normal
        # parse and an explicit given-first parse to avoid treating "Boyle" as a
        # given name when credentials or parenthetical names are present.
        clean = re.sub(r",?\s*(?:Ph\.?D\.?|M\.?D\.?|M\.?S\.?|B\.?S\.?).*$", "", name, flags=re.I)
        clean = re.sub(r"\([^)]*\)", " ", clean)
        tokens = latex_to_text(clean).split()
        if len(tokens) >= 2 and "," not in clean:
            signatures.append(_name_signature(f"{tokens[-1]}, {' '.join(tokens[:-1])}"))
        signatures.append(_name_signature(clean))
    # Preserve order while deduplicating.
    return list(dict.fromkeys(signatures))


def author_matches_person(author: Mapping[str, Any], person: Person) -> bool:
    author_family = normalize_for_match(str(author.get("family", ""))).replace(" ", "")
    author_given = normalize_for_match(str(author.get("given", "")))
    author_given_tokens = author_given.split()
    author_first = author_given_tokens[0] if author_given_tokens else ""
    author_initials = "".join(token[0] for token in author_given_tokens if token)

    for family, first, initials in person_name_signatures(person):
        if not family or family != author_family:
            continue
        if first and author_first and first == author_first:
            return True
        if initials and author_initials and len(initials) >= 2 and initials == author_initials:
            return True
        # A profile display name may intentionally contain only an initial.
        if len(first) == 1 and author_first.startswith(first):
            return True
    return False


def attach_members_to_authors(
    authors: list[dict[str, Any]],
    member_ids: Sequence[str],
    people: Mapping[str, Person],
    overrides: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Attach member IDs and profile URLs to author records.

    Returns ``(authors, matched_member_ids, unmatched_member_ids)``.
    ``overrides`` may map a umid to either a zero-based author index or an
    author-name string.
    """
    overrides = overrides or {}
    matched: set[str] = set()
    assigned_indices: set[int] = set()

    for umid in member_ids:
        person = people[umid]
        override = overrides.get(umid)
        candidate_indices: list[int] = []

        if isinstance(override, int):
            if 0 <= override < len(authors):
                candidate_indices = [override]
        elif isinstance(override, str) and override.strip():
            target = normalize_for_match(override)
            candidate_indices = [
                index
                for index, author in enumerate(authors)
                if target
                in {
                    normalize_for_match(str(author.get("raw", ""))),
                    normalize_for_match(str(author.get("full_name", ""))),
                    normalize_for_match(str(author.get("citation_name", ""))),
                }
            ]
        else:
            candidate_indices = [
                index
                for index, author in enumerate(authors)
                if author_matches_person(author, person)
            ]

        candidate_indices = [index for index in candidate_indices if index not in assigned_indices]
        if len(candidate_indices) == 1:
            index = candidate_indices[0]
            authors[index]["member_id"] = umid
            authors[index]["member_url"] = person.url
            authors[index]["member_name"] = person.name
            assigned_indices.add(index)
            matched.add(umid)

    return authors, sorted(matched), [umid for umid in member_ids if umid not in matched]


def infer_member_ids(authors: Sequence[Mapping[str, Any]], people: Mapping[str, Person]) -> list[str]:
    """Conservatively infer lab-member authors from current profile names.

    This helper is used by the one-time migration and metadata scaffolding.
    The normal build still treats the sidecar ``members`` list as authoritative.
    """
    inferred: list[str] = []
    for umid, person in people.items():
        matches = [author for author in authors if author_matches_person(author, person)]
        if len(matches) == 1:
            inferred.append(umid)
    return inferred


# ---------------------------------------------------------------------------
# Publication record construction
# ---------------------------------------------------------------------------


def normalize_doi(value: Any) -> str:
    doi = latex_to_text(value).strip()
    doi = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", doi, flags=re.I)
    return doi.strip().rstrip(".")


def extract_pmid(fields: Mapping[str, str], metadata: Mapping[str, Any]) -> str:
    for key in ("pmid", "PMID"):
        if metadata.get(key):
            return re.sub(r"\D", "", str(metadata[key]))
    if fields.get("pmid"):
        return re.sub(r"\D", "", latex_to_text(fields["pmid"]))
    note = latex_to_text(fields.get("note", ""))
    match = re.search(r"PMID\s*:?\s*(\d+)", note, flags=re.I)
    return match.group(1) if match else ""


def parse_month(value: Any) -> int:
    text = latex_to_text(value).strip().casefold()
    if not text:
        return 1
    if text.isdigit():
        month = int(text)
        return month if 1 <= month <= 12 else 1
    return MONTHS.get(text, MONTHS.get(text[:3], 1))


def publication_sort_date(fields: Mapping[str, str], metadata: Mapping[str, Any]) -> str:
    explicit = metadata.get("date") or fields.get("date")
    if explicit:
        text = str(explicit).strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return text

    year_text = latex_to_text(metadata.get("year") or fields.get("year") or "0")
    match = re.search(r"\d{4}", year_text)
    year = int(match.group()) if match else 0

    # Preprint URLs usually expose the posting/version date even when the
    # BibTeX record has no month. Prefer that over a DOI whose embedded date
    # may refer to an earlier manuscript version.
    for candidate in (metadata.get("url"), fields.get("url"), metadata.get("pdf"), fields.get("pdf")):
        url_text = latex_to_text(candidate or "")
        url_match = re.search(r"/(20\d{2})/(0?[1-9]|1[0-2])/(0?[1-9]|[12]\d|3[01])(?:/|$)", url_text)
        if url_match:
            return date(int(url_match.group(1)), int(url_match.group(2)), int(url_match.group(3))).isoformat()

    # bioRxiv-style DOIs and keys often contain YYYY.MM.DD. Use the date only
    # when it agrees with the bibliographic year.
    for candidate in (metadata.get("doi"), fields.get("doi")):
        candidate_text = latex_to_text(candidate or "")
        doi_match = re.search(r"(20\d{2})[.-](0?[1-9]|1[0-2])[.-](0?[1-9]|[12]\d|3[01])", candidate_text)
        if doi_match and (year <= 0 or int(doi_match.group(1)) == year):
            return date(int(doi_match.group(1)), int(doi_match.group(2)), int(doi_match.group(3))).isoformat()

    month = parse_month(metadata.get("month") or fields.get("month"))
    if year <= 0:
        return "0000-01-01"
    return date(year, month, 1).isoformat()


def infer_status(entry: BibEntry, metadata: Mapping[str, Any]) -> str:
    if metadata.get("status"):
        return re.sub(r"[\s-]+", "_", str(metadata["status"]).strip().lower())
    journal = latex_to_text(entry.fields.get("journal", "")).casefold()
    howpublished = latex_to_text(entry.fields.get("howpublished", "")).casefold()
    if any(repository in journal or repository in howpublished for repository in ("biorxiv", "medrxiv", "arxiv")):
        return "preprint"
    if entry.entry_type in {"unpublished", "preprint"}:
        return "preprint"
    return "published"


def infer_publication_type(entry: BibEntry, metadata: Mapping[str, Any]) -> str:
    if metadata.get("publication_type"):
        return re.sub(r"[\s-]+", "_", str(metadata["publication_type"]).strip().lower())
    if entry.entry_type in {"inbook", "incollection", "book", "booklet"}:
        return "chapter"
    if entry.entry_type in {"inproceedings", "conference", "proceedings"}:
        return "conference"
    return "article"


def _metadata_links(metadata: Mapping[str, Any]) -> dict[str, Any]:
    links = metadata.get("links") or {}
    if not isinstance(links, dict):
        raise PublicationError(f"{metadata.get('_source')}: 'links' must be a mapping")
    return dict(links)


def _safe_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _publication_author_record(author: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the author fields consumed by the Liquid templates."""
    record: dict[str, Any] = {"citation_name": str(author["citation_name"])}
    for key in ("member_url", "member_name"):
        value = author.get(key)
        if value:
            record[key] = str(value)
    if author.get("equal_contrib"):
        record["equal_contrib"] = True
    if author.get("co_senior"):
        record["co_senior"] = True
    return record


def build_publication_record(
    entry: BibEntry,
    metadata: Mapping[str, Any],
    people: Mapping[str, Person],
) -> tuple[dict[str, Any], list[BuildMessage]]:
    """Join one BibTeX record, one sidecar, and the lab-member directory.

    The returned mapping is intentionally narrow: it contains only fields used
    by the current Jekyll templates, plus the complete BibTeX entry requested
    for the browsable/downloadable bibliography. Matching fields used during
    validation are never serialized into ``_papers``.
    """
    messages: list[BuildMessage] = []
    fields = entry.fields

    required = ("author", "title", "year")
    missing = [field for field in required if not fields.get(field) and not metadata.get(field)]
    if missing:
        raise PublicationError(
            f"BibTeX entry '{entry.key}' is missing required field(s): {', '.join(missing)}"
        )

    member_ids = [
        str(value).strip()
        for value in _safe_list(metadata.get("members"))
        if str(value).strip()
    ]
    unknown = [umid for umid in member_ids if umid not in people]
    if unknown:
        raise PublicationError(
            f"{metadata.get('_source')}: unknown member umid(s) for '{entry.key}': "
            f"{', '.join(unknown)}"
        )
    if len(member_ids) != len(set(member_ids)):
        raise PublicationError(
            f"{metadata.get('_source')}: duplicate umid in members for '{entry.key}'"
        )

    raw_authors = str(metadata.get("author") or fields.get("author") or "")
    authors = parse_authors(raw_authors)
    overrides = metadata.get("author_member_map") or {}
    if not isinstance(overrides, dict):
        raise PublicationError(f"{metadata.get('_source')}: author_member_map must be a mapping")
    invalid_override_members = [str(umid) for umid in overrides if str(umid) not in member_ids]
    if invalid_override_members:
        raise PublicationError(
            f"{metadata.get('_source')}: author_member_map contains umid(s) not listed in "
            f"members: {', '.join(invalid_override_members)}"
        )
    invalid_override_values = [
        str(umid) for umid, target in overrides.items() if not isinstance(target, (int, str))
    ]
    if invalid_override_values:
        raise PublicationError(
            f"{metadata.get('_source')}: author_member_map values must be an author name or "
            f"zero-based index (invalid for: {', '.join(invalid_override_values)})"
        )

    member_roles_raw = metadata.get("member_roles") or {}
    if not isinstance(member_roles_raw, dict):
        raise PublicationError(f"{metadata.get('_source')}: member_roles must be a mapping")
    member_roles = {
        str(umid): re.sub(r"[\s-]+", "_", str(role).strip().lower())
        for umid, role in member_roles_raw.items()
    }
    invalid_role_members = [umid for umid in member_roles if umid not in member_ids]
    if invalid_role_members:
        raise PublicationError(
            f"{metadata.get('_source')}: member_roles contains umid(s) not listed in members: "
            f"{', '.join(invalid_role_members)}"
        )
    invalid_member_roles = [
        f"{umid}={role}"
        for umid, role in member_roles.items()
        if role not in NON_BYLINE_MEMBER_ROLES
    ]
    if invalid_member_roles:
        raise PublicationError(
            f"{metadata.get('_source')}: invalid non-byline member role(s): "
            f"{', '.join(invalid_member_roles)}. Allowed values: "
            f"{', '.join(sorted(NON_BYLINE_MEMBER_ROLES))}"
        )

    authors, _matched_members, unmatched_members = attach_members_to_authors(
        authors, member_ids, people, overrides
    )
    for umid in unmatched_members:
        if member_roles.get(umid) in NON_BYLINE_MEMBER_ROLES:
            continue
        messages.append(
            BuildMessage(
                "warning",
                f"{metadata.get('_source')}: member '{umid}' is listed for '{entry.key}' "
                "but did not match an author. Add author_member_map to this publication "
                "metadata file or a non-byline member_roles value.",
            )
        )

    title = latex_to_text(metadata.get("title") or fields.get("title"))
    journal = latex_to_text(
        metadata.get("journal") or fields.get("journal") or fields.get("booktitle")
    )
    year_text = latex_to_text(metadata.get("year") or fields.get("year"))
    year_match = re.search(r"\d{4}", year_text)
    year = int(year_match.group()) if year_match else 0
    sort_date = publication_sort_date(fields, metadata)

    status = infer_status(entry, metadata)
    if status not in VALID_STATUSES:
        raise PublicationError(
            f"{metadata.get('_source')}: invalid status '{status}' for '{entry.key}'. "
            f"Allowed values: {', '.join(sorted(VALID_STATUSES))}"
        )
    publication_type = infer_publication_type(entry, metadata)
    if publication_type not in VALID_PUBLICATION_TYPES:
        raise PublicationError(
            f"{metadata.get('_source')}: invalid publication_type '{publication_type}' for "
            f"'{entry.key}'. Allowed values: {', '.join(sorted(VALID_PUBLICATION_TYPES))}"
        )

    doi = normalize_doi(metadata.get("doi") or fields.get("doi"))
    pmid = extract_pmid(fields, metadata)
    metadata_links = _metadata_links(metadata)
    url = latex_to_text(
        metadata.get("url") or fields.get("url") or metadata_links.get("article") or ""
    )
    pdf = latex_to_text(
        metadata.get("pdf") or fields.get("pdf") or metadata_links.get("pdf") or ""
    )
    preprint = latex_to_text(
        metadata.get("biorxiv")
        or fields.get("biorxiv")
        or metadata_links.get("preprint")
        or (url if status == "preprint" else "")
    )
    primary_url = url or (f"https://doi.org/{doi}" if doi else pdf or preprint)

    # Only site-specific supplemental links belong in the sidecar-derived
    # mapping. Article/PDF/preprint links already have dedicated fields.
    normalized_links: dict[str, Any] = {}
    for key, value in metadata_links.items():
        normalized_key = str(key).strip()
        if normalized_key in {"article", "pdf", "preprint"} or value in (None, "", []):
            continue
        if isinstance(value, list):
            normalized_value = [latex_to_text(item) for item in value if item]
        elif normalized_key == "news":
            normalized_value = [latex_to_text(value)]
        else:
            normalized_value = latex_to_text(value)
        if normalized_value not in (None, "", []):
            normalized_links[normalized_key] = normalized_value

    abstract = latex_to_text(metadata.get("abstract") or fields.get("abstract") or "")
    summary = str(metadata.get("summary") or "").strip()
    topics = [
        str(topic).strip()
        for topic in _safe_list(metadata.get("topics"))
        if str(topic).strip()
    ]
    teaser = str(metadata.get("teaser") or "").strip()

    record: dict[str, Any] = {
        "generated": True,
        "bibkey": entry.key,
        "title": title,
        "author_list": [_publication_author_record(author) for author in authors],
        "year": year,
        "sort_date": sort_date,
        "members": member_ids,
        "bibtex": entry.raw,
    }

    # Defaults are omitted because Liquid already treats absent values as
    # published journal articles. This keeps every generated file readable.
    if status != "published":
        record["status"] = status
    if publication_type != "article":
        record["publication_type"] = publication_type

    optional_values: tuple[tuple[str, Any], ...] = (
        ("journal", journal),
        ("volume", latex_to_text(metadata.get("volume") or fields.get("volume") or "")),
        ("number", latex_to_text(metadata.get("number") or fields.get("number") or "")),
        ("pages", latex_to_text(metadata.get("pages") or fields.get("pages") or "")),
        ("doi", doi),
        ("PMID", pmid),
        ("primary_url", primary_url),
        ("pdf", pdf),
        ("biorxiv", preprint),
        ("links", normalized_links),
        ("member_roles", member_roles),
        ("abstract", abstract),
        ("featured", True if metadata.get("featured") else None),
        ("topics", topics),
        ("summary", summary),
        ("teaser", teaser),
    )
    for key, value in optional_values:
        if value not in (None, "", [], {}):
            record[key] = value

    return record, messages


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class LiteralString(str):
    pass


class FrontMatterDumper(yaml.SafeDumper):
    pass


def _literal_presenter(dumper: yaml.Dumper, data: LiteralString) -> yaml.ScalarNode:
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")


FrontMatterDumper.add_representer(LiteralString, _literal_presenter)


def prepare_for_yaml(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: prepare_for_yaml(item) for key, item in value.items()}
    if isinstance(value, list):
        return [prepare_for_yaml(item) for item in value]
    if isinstance(value, str) and ("\n" in value or len(value) > 260):
        return LiteralString(value)
    return value


def dump_front_matter(record: Mapping[str, Any]) -> str:
    yaml_text = yaml.dump(
        prepare_for_yaml(dict(record)),
        Dumper=FrontMatterDumper,
        allow_unicode=True,
        sort_keys=False,
        width=100,
        default_flow_style=False,
    ).rstrip()
    return f"---\n{yaml_text}\n---\n"


def dump_plain_yaml(data: Mapping[str, Any]) -> str:
    return yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        width=100,
        default_flow_style=False,
    )


def combined_bibtex(entries: Sequence[BibEntry]) -> str:
    header = (
        "% Boyle Lab publications\n"
        "% Generated by scripts/build_publications.py from bibliography/*.bib.\n"
        "% Edit the source file(s) in bibliography/, not this combined file.\n"
        "% Citation keys are permanent ASCII FirstAuthorYearMnemonic identifiers.\n\n"
    )
    return header + "\n\n".join(entry.raw.rstrip() for entry in entries) + "\n"

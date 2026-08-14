#!/usr/bin/env python3
"""Discover and format Boyle Lab publications from PubMed and bioRxiv.

The discovery layer is intentionally separate from the normal publication
builder.  It queries external services, proposes changes to the authoritative
BibTeX file and creates minimal website metadata sidecars.  The existing
``build_publications.py`` script remains responsible for validating and
producing ``_papers/*.yml`` and ``pub.bib``.

Only high-confidence author matches are applied automatically.  Candidate
records that resemble an existing publication but cannot be linked by a stable
identifier are reported for review and are not added.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
import calendar
import html
import json
import os
import re
import time
import unicodedata
from typing import Any, Iterable, Mapping, MutableMapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

import yaml

from publication_tools import (
    BibEntry,
    Person,
    author_matches_person,
    extract_pmid,
    infer_status,
    latex_to_text,
    load_bibliography,
    load_metadata,
    load_people,
    load_yaml_file,
    normalize_doi,
    normalize_for_match,
    parse_author,
    parse_authors,
    parse_bibtex,
    publication_sort_date,
)


class DiscoveryError(RuntimeError):
    """Raised when publication discovery cannot complete safely."""


@dataclass(slots=True, frozen=True)
class DiscoveryAuthor:
    """One author from an external publication record."""

    raw_name: str
    family: str = ""
    given: str = ""
    collective: str = ""
    orcid: str = ""
    affiliations: tuple[str, ...] = ()

    @property
    def bibtex_name(self) -> str:
        if self.collective:
            # One inner brace pair, plus the field's outer pair, preserves a
            # corporate author as one BibTeX name.
            return "{" + self.collective.strip("{} ") + "}"
        if self.family and self.given:
            return f"{self.family}, {self.given}"
        return self.raw_name.strip()

    @property
    def display_name(self) -> str:
        if self.collective:
            return self.collective
        if self.given and self.family:
            return f"{self.given} {self.family}".strip()
        return self.raw_name.strip()


@dataclass(slots=True)
class CandidatePublication:
    """A normalized publication returned by PubMed or bioRxiv."""

    source: str
    source_id: str
    title: str
    authors: list[DiscoveryAuthor]
    year: int
    publication_date: str
    journal: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    month: str = ""
    day: str = ""
    abstract: str = ""
    doi: str = ""
    pmid: str = ""
    url: str = ""
    pdf: str = ""
    status: str = "published"
    publication_types: tuple[str, ...] = ()
    category: str = ""
    version: int = 1
    published_doi: str = ""
    extra_fields: dict[str, str] = field(default_factory=dict)

    @property
    def normalized_title(self) -> str:
        return normalize_title(self.title)

    @property
    def first_author_family(self) -> str:
        return self.authors[0].family if self.authors else ""

    @property
    def author_field(self) -> str:
        return " and ".join(author.bibtex_name for author in self.authors)


@dataclass(slots=True, frozen=True)
class ExistingPublication:
    key: str
    entry: BibEntry
    doi: str
    pmid: str
    normalized_title: str
    first_author_family: str
    status: str
    sort_date: str


@dataclass(slots=True)
class ProposedChange:
    kind: str
    candidate: CandidatePublication
    bibkey: str
    existing_key: str = ""
    reason: str = ""
    members: list[str] = field(default_factory=list)
    author_member_map: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class SkippedCandidate:
    candidate: CandidatePublication
    reason: str
    matching_key: str = ""


@dataclass(slots=True)
class DiscoveryResult:
    additions: list[ProposedChange] = field(default_factory=list)
    upgrades: list[ProposedChange] = field(default_factory=list)
    skipped: list[SkippedCandidate] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.additions or self.upgrades)

    def as_dict(self) -> dict[str, Any]:
        def candidate_dict(candidate: CandidatePublication) -> dict[str, Any]:
            return {
                "source": candidate.source,
                "source_id": candidate.source_id,
                "title": candidate.title,
                "doi": candidate.doi,
                "pmid": candidate.pmid,
                "date": candidate.publication_date,
            }

        return {
            "changed": self.changed,
            "addition_count": len(self.additions),
            "upgrade_count": len(self.upgrades),
            "skipped_count": len(self.skipped),
            "additions": [
                {
                    "bibkey": item.bibkey,
                    "members": item.members,
                    **candidate_dict(item.candidate),
                }
                for item in self.additions
            ],
            "upgrades": [
                {
                    "bibkey": item.bibkey,
                    "existing_key": item.existing_key,
                    **candidate_dict(item.candidate),
                }
                for item in self.upgrades
            ],
            "skipped": [
                {
                    "reason": item.reason,
                    "matching_key": item.matching_key,
                    **candidate_dict(item.candidate),
                }
                for item in self.skipped
            ],
            "warnings": self.warnings,
            "changed_files": self.changed_files,
        }


# ---------------------------------------------------------------------------
# Configuration and HTTP
# ---------------------------------------------------------------------------


DEFAULT_CONFIG: dict[str, Any] = {
    "version": 1,
    "target_umid": "apboyle",
    "pubmed": {
        "enabled": True,
        "max_results": 1000,
        "excluded_publication_types": [
            "Published Erratum",
            "Retracted Publication",
            "Retraction of Publication",
            "Editorial",
            "Comment",
            "News",
        ],
    },
    "biorxiv": {
        "enabled": True,
        "lookback_days": 21,
        "server": "biorxiv",
    },
    "matching": {
        "duplicate_title_threshold": 0.97,
        "ambiguous_title_threshold": 0.90,
        "affiliation_terms": [
            "University of Michigan",
            "Michigan Medicine",
            "Ann Arbor",
        ],
    },
}


def deep_merge(base: MutableMapping[str, Any], override: Mapping[str, Any]) -> MutableMapping[str, Any]:
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(base.get(key), MutableMapping):
            deep_merge(base[key], value)  # type: ignore[index]
        else:
            base[key] = value
    return base


def load_discovery_config(path: Path) -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
        if not isinstance(loaded, dict):
            raise DiscoveryError(f"{path}: expected a YAML mapping")
        deep_merge(config, loaded)
    if int(config.get("version", 0)) != 1:
        raise DiscoveryError(f"{path}: unsupported publication-discovery configuration version")
    return config


class HttpClient:
    """Small retrying HTTP client using only the Python standard library."""

    def __init__(
        self,
        *,
        user_agent: str,
        timeout: int = 45,
        retries: int = 4,
        minimum_interval: float = 0.34,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.retries = retries
        self.minimum_interval = minimum_interval
        self._last_request = 0.0

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.minimum_interval:
            time.sleep(self.minimum_interval - elapsed)

    def get_bytes(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        *,
        allow_not_found: bool = False,
    ) -> bytes | None:
        if params:
            query = urlencode({key: value for key, value in params.items() if value not in (None, "")})
            url = f"{url}?{query}"

        for attempt in range(self.retries):
            self._wait()
            request = Request(
                url,
                headers={
                    "Accept": "application/json, application/xml, text/xml;q=0.9, */*;q=0.8",
                    "User-Agent": self.user_agent,
                },
            )
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    payload = response.read()
                self._last_request = time.monotonic()
                return payload
            except HTTPError as exc:
                self._last_request = time.monotonic()
                if exc.code == 404 and allow_not_found:
                    return None
                if exc.code not in {429, 500, 502, 503, 504} or attempt + 1 >= self.retries:
                    raise DiscoveryError(f"HTTP {exc.code} while requesting {url}") from exc
                retry_after = exc.headers.get("Retry-After")
                delay = float(retry_after) if retry_after and retry_after.isdigit() else 2**attempt
                time.sleep(delay)
            except (URLError, TimeoutError) as exc:
                self._last_request = time.monotonic()
                if attempt + 1 >= self.retries:
                    raise DiscoveryError(f"Network error while requesting {url}: {exc}") from exc
                time.sleep(2**attempt)
        raise DiscoveryError(f"Request failed after retries: {url}")

    def get_json(
        self,
        url: str,
        params: Mapping[str, Any] | None = None,
        *,
        allow_not_found: bool = False,
    ) -> dict[str, Any] | None:
        payload = self.get_bytes(url, params, allow_not_found=allow_not_found)
        if payload is None:
            return None
        try:
            value = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DiscoveryError(f"Invalid JSON returned by {url}") from exc
        if not isinstance(value, dict):
            raise DiscoveryError(f"Expected a JSON object from {url}")
        return value


# ---------------------------------------------------------------------------
# Normalization and identity matching
# ---------------------------------------------------------------------------


_CREDENTIAL_RE = re.compile(
    r",?\s*(?:Ph\.?D\.?|M\.?D\.?|M\.?S\.?|B\.?S\.?|D\.?Phil\.?).*$",
    flags=re.I,
)
_TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "the",
    "to",
    "using",
    "with",
}
_NAME_PARTICLES = {
    "abou",
    "al",
    "bin",
    "da",
    "de",
    "del",
    "della",
    "der",
    "di",
    "du",
    "la",
    "le",
    "van",
    "von",
}


def clean_person_display_name(name: str) -> str:
    return _CREDENTIAL_RE.sub("", name).strip()


def normalize_orcid(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"^https?://orcid\.org/", "", text, flags=re.I)
    match = re.search(r"\d{4}-\d{4}-\d{4}-[\dXx]{4}", text)
    return match.group(0).upper() if match else ""


def normalize_title(value: str) -> str:
    text = latex_to_text(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.casefold()
    text = re.sub(r"\b(?:preprint|ahead of print)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def title_similarity(left: str, right: str) -> float:
    left_normalized = normalize_title(left)
    right_normalized = normalize_title(right)
    if not left_normalized or not right_normalized:
        return 0.0
    if left_normalized == right_normalized:
        return 1.0
    return SequenceMatcher(None, left_normalized, right_normalized).ratio()


def ascii_alphanumeric(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^A-Za-z0-9]+", "", text)


def pascal_token(value: str) -> str:
    clean = ascii_alphanumeric(value)
    if not clean:
        return ""
    if any(ch.isupper() for ch in value[1:]) or any(ch.isdigit() for ch in value):
        return clean[0].upper() + clean[1:]
    return clean[0].upper() + clean[1:].lower()


def loose_name_parts(name: str) -> tuple[str, str]:
    """Return ``(family, given)`` for a loose, usually given-first name."""
    text = re.sub(r"\s+", " ", str(name or "").strip())
    if not text:
        return "", ""
    if "," in text:
        family, given = text.split(",", 1)
        return family.strip(), given.strip()

    tokens = text.split()
    if len(tokens) == 1:
        return tokens[0], ""
    family_start = len(tokens) - 1
    while family_start - 1 >= 1 and tokens[family_start - 1].casefold().rstrip(".") in _NAME_PARTICLES:
        family_start -= 1
    family = " ".join(tokens[family_start:])
    given = " ".join(tokens[:family_start])
    return family, given


def target_author_match(
    candidate: CandidatePublication,
    target: Person,
    target_orcid: str,
    affiliation_terms: Sequence[str],
) -> bool:
    """Require an ORCID or a high-confidence full-name match for the target."""
    target_first = normalize_for_match(clean_person_display_name(target.name)).split()
    target_first_name = target_first[0] if target_first else ""
    normalized_affiliations = [normalize_for_match(term) for term in affiliation_terms if term]

    for author in candidate.authors:
        if target_orcid and normalize_orcid(author.orcid) == target_orcid:
            return True

        parsed = parse_author(author.bibtex_name)
        if not author_matches_person(parsed, target):
            continue

        given_tokens = normalize_for_match(author.given or parsed.get("given", "")).split()
        if given_tokens and len(given_tokens[0]) > 1 and given_tokens[0] == target_first_name:
            return True

        affiliations = " ".join(normalize_for_match(value) for value in author.affiliations)
        if affiliations and any(term and term in affiliations for term in normalized_affiliations):
            return True

    return False


def make_citation_key(
    candidate: CandidatePublication,
    existing_keys: Iterable[str],
) -> str:
    family = pascal_token(candidate.first_author_family) or "Publication"
    year = candidate.year or int(candidate.publication_date[:4] or 0)

    title_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", latex_to_text(candidate.title))
    significant = [token for token in title_tokens if token.casefold() not in _TITLE_STOPWORDS]
    if not significant:
        significant = title_tokens or ["Article"]

    mnemonic_tokens: list[str] = []
    for token in significant:
        mnemonic = pascal_token(token)
        if not mnemonic:
            continue
        mnemonic_tokens.append(mnemonic)
        joined = "".join(mnemonic_tokens)
        if len(joined) >= 16 or len(mnemonic_tokens) >= 3:
            break
    mnemonic = "".join(mnemonic_tokens)[:32] or "Article"
    base = f"{family}{year}{mnemonic}"
    base = re.sub(r"[^A-Za-z0-9]", "", base)
    if not base or not base[0].isalpha():
        base = "Publication" + base

    occupied = {key.casefold() for key in existing_keys}
    if base.casefold() not in occupied:
        return base
    suffix_index = 0
    while True:
        suffix = chr(ord("A") + suffix_index) if suffix_index < 26 else str(suffix_index + 1)
        proposed = base + suffix
        if proposed.casefold() not in occupied:
            return proposed
        suffix_index += 1


# ---------------------------------------------------------------------------
# PubMed
# ---------------------------------------------------------------------------


MONTH_LOOKUP = {
    name.casefold(): index
    for index, name in enumerate(calendar.month_abbr)
    if name
}
MONTH_LOOKUP.update(
    {
        name.casefold(): index
        for index, name in enumerate(calendar.month_name)
        if name
    }
)


def xml_text(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return re.sub(r"\s+", " ", "".join(element.itertext())).strip()


def pubmed_date(article: ET.Element) -> tuple[str, str, str, int]:
    article_date = article.find("ArticleDate")
    pub_date = article.find("Journal/JournalIssue/PubDate")
    source = article_date if article_date is not None else pub_date

    year = xml_text(source.find("Year")) if source is not None else ""
    month = xml_text(source.find("Month")) if source is not None else ""
    day = xml_text(source.find("Day")) if source is not None else ""
    medline = xml_text(source.find("MedlineDate")) if source is not None else ""

    if not year:
        match = re.search(r"(?:19|20)\d{2}", medline)
        year = match.group(0) if match else ""
    year_int = int(year) if year.isdigit() else 0

    month_number = 1
    if month.isdigit():
        month_number = max(1, min(12, int(month)))
    elif month:
        month_number = MONTH_LOOKUP.get(month.casefold(), MONTH_LOOKUP.get(month[:3].casefold(), 1))
    elif medline:
        for token, number in MONTH_LOOKUP.items():
            if token and re.search(rf"\b{re.escape(token)}\b", medline.casefold()):
                month_number = number
                month = str(number)
                break

    day_number = int(day) if day.isdigit() and 1 <= int(day) <= 31 else 1
    if year_int:
        try:
            iso_date = date(year_int, month_number, day_number).isoformat()
        except ValueError:
            iso_date = date(year_int, month_number, 1).isoformat()
    else:
        iso_date = "0000-01-01"
    return iso_date, str(month_number), str(day_number), year_int


def parse_pubmed_article(node: ET.Element) -> CandidatePublication:
    citation = node.find("MedlineCitation")
    if citation is None:
        raise DiscoveryError("PubMed record is missing MedlineCitation")
    article = citation.find("Article")
    if article is None:
        raise DiscoveryError("PubMed record is missing Article")

    pmid = xml_text(citation.find("PMID"))
    title = xml_text(article.find("ArticleTitle"))
    journal = xml_text(article.find("Journal/Title"))
    volume = xml_text(article.find("Journal/JournalIssue/Volume"))
    issue = xml_text(article.find("Journal/JournalIssue/Issue"))
    pages = xml_text(article.find("Pagination/MedlinePgn"))
    if not pages:
        for location in article.findall("ELocationID"):
            if location.attrib.get("EIdType", "").casefold() not in {"doi", "pii"}:
                pages = xml_text(location)
                if pages:
                    break

    publication_date, month, day, year = pubmed_date(article)

    abstract_parts: list[str] = []
    for abstract_node in article.findall("Abstract/AbstractText"):
        value = xml_text(abstract_node)
        if not value:
            continue
        label = str(abstract_node.attrib.get("Label") or "").strip()
        abstract_parts.append(f"{label}: {value}" if label else value)
    abstract = " ".join(abstract_parts)

    authors: list[DiscoveryAuthor] = []
    for author_node in article.findall("AuthorList/Author"):
        collective = xml_text(author_node.find("CollectiveName"))
        if collective:
            authors.append(
                DiscoveryAuthor(raw_name=collective, collective=collective, family=collective)
            )
            continue
        family = xml_text(author_node.find("LastName"))
        given = xml_text(author_node.find("ForeName")) or xml_text(author_node.find("Initials"))
        if not family:
            continue
        orcid = ""
        for identifier in author_node.findall("Identifier"):
            if identifier.attrib.get("Source", "").casefold() == "orcid":
                orcid = normalize_orcid(xml_text(identifier))
        affiliations = tuple(
            xml_text(affiliation)
            for affiliation in author_node.findall("AffiliationInfo/Affiliation")
            if xml_text(affiliation)
        )
        authors.append(
            DiscoveryAuthor(
                raw_name=f"{given} {family}".strip(),
                family=family,
                given=given,
                orcid=orcid,
                affiliations=affiliations,
            )
        )

    doi = ""
    for identifier in node.findall("PubmedData/ArticleIdList/ArticleId"):
        if identifier.attrib.get("IdType", "").casefold() == "doi":
            doi = normalize_doi(xml_text(identifier))
            break
    if not doi:
        for location in article.findall("ELocationID"):
            if location.attrib.get("EIdType", "").casefold() == "doi":
                doi = normalize_doi(xml_text(location))
                break

    publication_types = tuple(
        xml_text(value)
        for value in article.findall("PublicationTypeList/PublicationType")
        if xml_text(value)
    )
    url = f"https://doi.org/{doi}" if doi else f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    return CandidatePublication(
        source="PubMed",
        source_id=pmid,
        title=title,
        authors=authors,
        year=year,
        publication_date=publication_date,
        journal=journal,
        volume=volume,
        issue=issue,
        pages=pages,
        month=month,
        day=day,
        abstract=abstract,
        doi=doi,
        pmid=pmid,
        url=url,
        status="published",
        publication_types=publication_types,
    )


def parse_pubmed_xml(payload: bytes) -> list[CandidatePublication]:
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise DiscoveryError(f"Invalid XML returned by PubMed: {exc}") from exc
    return [parse_pubmed_article(node) for node in root.findall("PubmedArticle")]


class PubMedClient:
    BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    def __init__(
        self,
        http: HttpClient,
        *,
        email: str,
        tool: str = "BoyleLabPublicationDiscovery",
        api_key: str = "",
    ) -> None:
        if not email:
            raise DiscoveryError("PubMed discovery requires a contact email")
        self.http = http
        self.email = email
        self.tool = tool
        self.api_key = api_key

    def _common_params(self) -> dict[str, str]:
        params = {"tool": self.tool, "email": self.email}
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def search_ids(self, query: str, max_results: int) -> list[str]:
        params: dict[str, Any] = {
            **self._common_params(),
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": max_results,
            "sort": "pub date",
        }
        data = self.http.get_json(f"{self.BASE}/esearch.fcgi", params)
        if data is None:
            return []
        result = data.get("esearchresult") or {}
        identifiers = result.get("idlist") or []
        if not isinstance(identifiers, list):
            raise DiscoveryError("Unexpected PubMed ESearch response")
        return [str(identifier) for identifier in identifiers]

    def fetch(self, identifiers: Sequence[str]) -> list[CandidatePublication]:
        records: list[CandidatePublication] = []
        for start in range(0, len(identifiers), 200):
            batch = identifiers[start : start + 200]
            params: dict[str, Any] = {
                **self._common_params(),
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
            }
            payload = self.http.get_bytes(f"{self.BASE}/efetch.fcgi", params)
            if payload:
                records.extend(parse_pubmed_xml(payload))
        return records

    def discover(self, query: str, max_results: int) -> list[CandidatePublication]:
        return self.fetch(self.search_ids(query, max_results))


def build_pubmed_query(target: Person, target_orcid: str) -> str:
    clean_name = clean_person_display_name(target.name)
    family, given = loose_name_parts(clean_name)
    initials = "".join(token[0] for token in re.findall(r"[A-Za-z]+", given) if token)
    terms: list[str] = []
    if target_orcid:
        terms.append(f'"orcid {target_orcid}"[auid]')
    if family and initials:
        terms.append(f'"{family} {initials}"[au]')
    if clean_name:
        terms.append(f'"{clean_name}"[fau]')
    return "(" + " OR ".join(dict.fromkeys(terms)) + ")"


# ---------------------------------------------------------------------------
# bioRxiv
# ---------------------------------------------------------------------------


def split_biorxiv_authors(value: str) -> list[str]:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text:
        return []
    if ";" in text:
        return [part.strip() for part in text.split(";") if part.strip()]
    # The API normally uses semicolons. Retain an unsplit string rather than
    # incorrectly splitting surnames when an older response does not.
    return [text]


def biorxiv_content_urls(record: Mapping[str, Any], doi: str, version: int) -> tuple[str, str]:
    jats = str(record.get("jatsxml") or record.get("jats xml path") or "").strip()
    if jats:
        if jats.startswith("http"):
            base = jats
        else:
            base = "https://www.biorxiv.org" + (jats if jats.startswith("/") else "/" + jats)
        base = re.sub(r"(?:\.source)?\.xml$", "", base)
        return base, base + ".full.pdf"
    base = f"https://www.biorxiv.org/content/{doi}v{version}"
    return base, base + ".full.pdf"


def parse_biorxiv_record(record: Mapping[str, Any]) -> CandidatePublication:
    doi = normalize_doi(record.get("doi") or record.get("biorxiv_doi") or "")
    title = html.unescape(str(record.get("title") or record.get("preprint_title") or "")).strip()
    author_text = str(record.get("authors") or record.get("preprint_authors") or "")
    authors: list[DiscoveryAuthor] = []
    for raw_name in split_biorxiv_authors(author_text):
        family, given = loose_name_parts(raw_name)
        authors.append(
            DiscoveryAuthor(raw_name=raw_name, family=family, given=given)
        )

    date_text = str(record.get("date") or record.get("preprint_date") or "").strip()
    date_match = re.search(r"(20\d{2})-(\d{2})-(\d{2})", date_text)
    if date_match:
        publication_date = date_match.group(0)
        year = int(date_match.group(1))
        month = str(int(date_match.group(2)))
        day = str(int(date_match.group(3)))
    else:
        year_match = re.search(r"20\d{2}", date_text)
        year = int(year_match.group(0)) if year_match else 0
        publication_date = f"{year:04d}-01-01" if year else "0000-01-01"
        month = "1"
        day = "1"

    try:
        version = int(record.get("version") or 1)
    except (TypeError, ValueError):
        version = 1
    url, pdf = biorxiv_content_urls(record, doi, version)
    published_doi = normalize_doi(record.get("published") or record.get("published_doi") or "")
    if published_doi.casefold() in {"na", "n/a", "none", "null", "not available"}:
        published_doi = ""

    return CandidatePublication(
        source="bioRxiv",
        source_id=doi,
        title=title,
        authors=authors,
        year=year,
        publication_date=publication_date,
        journal="bioRxiv",
        month=month,
        day=day,
        abstract=html.unescape(str(record.get("abstract") or record.get("preprint_abstract") or "")).strip(),
        doi=doi,
        url=url,
        pdf=pdf,
        status="preprint",
        category=str(record.get("category") or record.get("preprint_category") or "").strip(),
        version=version,
        published_doi=published_doi,
    )


def parse_biorxiv_collection(data: Mapping[str, Any]) -> list[CandidatePublication]:
    collection = data.get("collection") or []
    if not isinstance(collection, list):
        raise DiscoveryError("Unexpected bioRxiv API response: collection is not a list")
    return [parse_biorxiv_record(record) for record in collection if isinstance(record, Mapping)]


class BioRxivClient:
    BASE = "https://api.biorxiv.org"

    def __init__(self, http: HttpClient, *, server: str = "biorxiv") -> None:
        if server not in {"biorxiv", "medrxiv"}:
            raise DiscoveryError(f"Unsupported preprint server: {server}")
        self.http = http
        self.server = server

    def discover(self, start: date, end: date) -> list[CandidatePublication]:
        cursor = 0
        latest_by_doi: dict[str, CandidatePublication] = {}
        while True:
            url = (
                f"{self.BASE}/details/{self.server}/"
                f"{start.isoformat()}/{end.isoformat()}/{cursor}/json"
            )
            data = self.http.get_json(url)
            if data is None:
                break
            page = parse_biorxiv_collection(data)
            for candidate in page:
                key = candidate.doi.casefold() or candidate.normalized_title
                previous = latest_by_doi.get(key)
                if previous is None or candidate.version >= previous.version:
                    latest_by_doi[key] = candidate

            messages = data.get("messages") or []
            message = messages[0] if messages and isinstance(messages[0], Mapping) else {}
            try:
                total = int(message.get("total") or 0)
            except (TypeError, ValueError):
                total = 0
            if not page:
                break
            cursor += len(page)
            if total and cursor >= total:
                break
            if len(page) < 100 and not total:
                break
        return sorted(latest_by_doi.values(), key=lambda item: item.publication_date, reverse=True)

    def publication_link_for_doi(self, published_doi: str) -> str:
        """Return a linked bioRxiv DOI for a published DOI, when known."""
        doi_path = quote(normalize_doi(published_doi), safe="/")
        url = f"{self.BASE}/pubs/{self.server}/{doi_path}"
        try:
            data = self.http.get_json(url, allow_not_found=True)
        except DiscoveryError:
            return ""
        if not data:
            return ""
        collection = data.get("collection") or []
        if not isinstance(collection, list):
            return ""
        for record in collection:
            if not isinstance(record, Mapping):
                continue
            biorxiv_doi = normalize_doi(record.get("biorxiv_doi") or record.get("doi") or "")
            if biorxiv_doi:
                return biorxiv_doi
        return ""


# ---------------------------------------------------------------------------
# Existing bibliography and duplicate resolution
# ---------------------------------------------------------------------------


def existing_publications(entries: Sequence[BibEntry]) -> list[ExistingPublication]:
    result: list[ExistingPublication] = []
    for entry in entries:
        authors = parse_authors(entry.fields.get("author", ""))
        first_family = str(authors[0].get("family") or "") if authors else ""
        result.append(
            ExistingPublication(
                key=entry.key,
                entry=entry,
                doi=normalize_doi(entry.fields.get("doi", "")),
                pmid=extract_pmid(entry.fields, {}),
                normalized_title=normalize_title(entry.fields.get("title", "")),
                first_author_family=first_family,
                status=infer_status(entry, {}),
                sort_date=publication_sort_date(entry.fields, {}),
            )
        )
    return result


class BibliographyIndex:
    def __init__(self, entries: Sequence[BibEntry]) -> None:
        self.records = existing_publications(entries)
        self.by_key = {record.key: record for record in self.records}
        self.by_doi = {record.doi.casefold(): record for record in self.records if record.doi}
        self.by_pmid = {record.pmid: record for record in self.records if record.pmid}
        self.by_title = {
            record.normalized_title: record
            for record in self.records
            if record.normalized_title
        }

    def identifier_match(self, candidate: CandidatePublication) -> ExistingPublication | None:
        """Return an existing record matched by a persistent identifier only.

        Title matching is intentionally separate so a PubMed record can first be
        checked for an explicit bioRxiv-to-journal relationship. This preserves
        the original stable citation key when a preprint is published under the
        same title.
        """
        doi = normalize_doi(candidate.doi).casefold()
        if doi and doi in self.by_doi:
            return self.by_doi[doi]
        if candidate.pmid and candidate.pmid in self.by_pmid:
            return self.by_pmid[candidate.pmid]
        if candidate.published_doi:
            published = normalize_doi(candidate.published_doi).casefold()
            if published in self.by_doi:
                return self.by_doi[published]
        return None

    def exact_title_match(self, candidate: CandidatePublication) -> ExistingPublication | None:
        if candidate.normalized_title and candidate.normalized_title in self.by_title:
            return self.by_title[candidate.normalized_title]
        return None

    def exact_match(self, candidate: CandidatePublication) -> ExistingPublication | None:
        """Backward-compatible combined identifier/title lookup."""
        return self.identifier_match(candidate) or self.exact_title_match(candidate)

    def closest_title(self, candidate: CandidatePublication) -> tuple[ExistingPublication | None, float]:
        best: ExistingPublication | None = None
        best_score = 0.0
        candidate_family = normalize_for_match(candidate.first_author_family)
        for record in self.records:
            record_family = normalize_for_match(record.first_author_family)
            if candidate_family and record_family and candidate_family != record_family:
                continue
            score = SequenceMatcher(
                None,
                candidate.normalized_title,
                record.normalized_title,
            ).ratio()
            if score > best_score:
                best = record
                best_score = score
        return best, best_score


# ---------------------------------------------------------------------------
# Lab-member inference and BibTeX formatting
# ---------------------------------------------------------------------------


def load_sidecar_aliases(metadata: Mapping[str, Mapping[str, Any]]) -> dict[str, set[str]]:
    """Reuse historical names already recorded in publication sidecars."""
    aliases: dict[str, set[str]] = {}
    for sidecar in metadata.values():
        mapping = sidecar.get("author_member_map") or {}
        if not isinstance(mapping, Mapping):
            continue
        for umid, target in mapping.items():
            if not isinstance(target, str) or not target.strip():
                continue
            aliases.setdefault(str(umid), set()).add(normalize_for_match(target))
    return aliases


def infer_candidate_members(
    candidate: CandidatePublication,
    people: Mapping[str, Person],
    aliases: Mapping[str, set[str]],
    *,
    target_umid: str = "",
    target_orcid: str = "",
) -> tuple[list[str], dict[str, str]]:
    member_by_author_index: dict[int, str] = {}
    explicit_map: dict[str, str] = {}

    for index, author in enumerate(candidate.authors):
        if (
            target_umid
            and target_umid in people
            and target_orcid
            and normalize_orcid(author.orcid) == normalize_orcid(target_orcid)
        ):
            member_by_author_index[index] = target_umid
            # ORCID establishes identity even when the indexed display name
            # differs from the current profile name. Preserve the exact byline
            # in the publication-specific sidecar for the normal builder.
            parsed_target = parse_author(author.bibtex_name)
            if not author_matches_person(parsed_target, people[target_umid]):
                explicit_map[target_umid] = author.bibtex_name
            continue

        parsed = parse_author(author.bibtex_name)
        matched = [
            umid
            for umid, person in people.items()
            if author_matches_person(parsed, person)
        ]
        if len(matched) == 1:
            member_by_author_index[index] = matched[0]
            continue

        author_names = {
            normalize_for_match(author.raw_name),
            normalize_for_match(author.display_name),
            normalize_for_match(author.bibtex_name),
        }
        alias_matches = [
            umid
            for umid, known_aliases in aliases.items()
            if author_names.intersection(known_aliases)
        ]
        if len(alias_matches) == 1:
            umid = alias_matches[0]
            member_by_author_index[index] = umid
            explicit_map[umid] = author.bibtex_name

    members = [member_by_author_index[index] for index in sorted(member_by_author_index)]
    return list(dict.fromkeys(members)), explicit_map


def bibtex_escape(value: str) -> str:
    text = html.unescape(str(value or ""))
    replacements = (
        ("\\", "\\textbackslash{}"),
        ("&", r"\&"),
        ("%", r"\%"),
        ("#", r"\#"),
        ("$", r"\$"),
        ("_", r"\_"),
    )
    for source, replacement in replacements:
        text = text.replace(source, replacement)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def bibtex_field(name: str, value: str, *, double_braces: bool = False) -> str:
    escaped = bibtex_escape(value)
    wrapped = "{{" + escaped + "}}" if double_braces else "{" + escaped + "}"
    return f"  {name} = {wrapped}"


def format_candidate_bibtex(
    candidate: CandidatePublication,
    bibkey: str,
    *,
    preserved_preprint: ExistingPublication | None = None,
) -> str:
    fields: list[tuple[str, str, bool]] = [
        ("author", candidate.author_field, False),
        ("title", candidate.title, True),
    ]
    if candidate.journal:
        fields.append(("journal", candidate.journal, False))
    if candidate.volume:
        fields.append(("volume", candidate.volume, False))
    if candidate.issue:
        fields.append(("number", candidate.issue, False))
    if candidate.pages:
        fields.append(("pages", candidate.pages, False))
    fields.append(("year", str(candidate.year), False))
    if candidate.month:
        fields.append(("month", candidate.month, False))
    if candidate.day and candidate.day != "1":
        fields.append(("day", candidate.day, False))
    if candidate.abstract:
        fields.append(("abstract", candidate.abstract, False))
    if candidate.doi:
        fields.append(("doi", candidate.doi, False))
    if candidate.url:
        fields.append(("url", candidate.url, False))
    if candidate.pdf:
        fields.append(("pdf", candidate.pdf, False))

    if preserved_preprint is not None:
        old_url = latex_to_text(preserved_preprint.entry.fields.get("url", ""))
        old_doi = normalize_doi(preserved_preprint.entry.fields.get("doi", ""))
        old_pdf = latex_to_text(preserved_preprint.entry.fields.get("pdf", ""))
        preprint_link = old_url or (f"https://doi.org/{old_doi}" if old_doi else "")
        if preprint_link:
            fields.append(("biorxiv", preprint_link, False))
        if old_pdf and not candidate.pdf:
            fields.append(("pdf", old_pdf, False))

    for key, value in candidate.extra_fields.items():
        if value and key not in {field_name for field_name, _value, _double in fields}:
            fields.append((key, value, False))
    if candidate.pmid:
        fields.append(("note", f"{{PMID:}} {candidate.pmid}", False))

    lines = [f"@article{{{bibkey},"]
    for index, (name, value, double_braces) in enumerate(fields):
        suffix = "," if index + 1 < len(fields) else ""
        lines.append(bibtex_field(name, value, double_braces=double_braces) + suffix)
    lines.append("}")
    return "\n".join(lines)


class BibFileEditor:
    """Perform narrow insertions/replacements without reformatting old entries."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.text = path.read_text(encoding="utf-8-sig")

    def entries(self) -> list[BibEntry]:
        return parse_bibtex(self.text, source=self.path)

    def replace(self, key: str, raw_entry: str) -> None:
        entry = next((item for item in self.entries() if item.key == key), None)
        if entry is None:
            raise DiscoveryError(f"Cannot replace missing BibTeX key: {key}")
        start = self.text.find(entry.raw)
        if start < 0:
            raise DiscoveryError(f"Could not locate raw BibTeX entry for {key}")
        end = start + len(entry.raw)
        self.text = self.text[:start] + raw_entry + self.text[end:]

    def insert(self, raw_entry: str, sort_date: str) -> None:
        entries = self.entries()
        insertion = len(self.text.rstrip())
        for entry in entries:
            existing_date = publication_sort_date(entry.fields, {})
            if existing_date <= sort_date:
                location = self.text.find(entry.raw)
                if location >= 0:
                    insertion = location
                    break
        prefix = self.text[:insertion].rstrip()
        suffix = self.text[insertion:].lstrip()
        before = "\n\n" if prefix else ""
        after = ("\n\n" + suffix) if suffix else "\n"
        self.text = prefix + before + raw_entry + after

    def write(self) -> None:
        self.path.write_text(self.text, encoding="utf-8")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def filter_pubmed_candidates(
    candidates: Sequence[CandidatePublication],
    target: Person,
    target_orcid: str,
    affiliation_terms: Sequence[str],
    excluded_types: Sequence[str],
) -> tuple[list[CandidatePublication], list[SkippedCandidate]]:
    excluded_normalized = {normalize_for_match(value) for value in excluded_types}
    accepted: list[CandidatePublication] = []
    skipped: list[SkippedCandidate] = []
    for candidate in candidates:
        types = {normalize_for_match(value) for value in candidate.publication_types}
        excluded = sorted(types.intersection(excluded_normalized))
        if excluded:
            skipped.append(candidate_skip(candidate, f"excluded PubMed publication type: {excluded[0]}"))
            continue
        if not target_author_match(candidate, target, target_orcid, affiliation_terms):
            skipped.append(candidate_skip(candidate, "target author could not be verified with high confidence"))
            continue
        accepted.append(candidate)
    return accepted, skipped


def filter_biorxiv_candidates(
    candidates: Sequence[CandidatePublication],
    target: Person,
    target_orcid: str,
    affiliation_terms: Sequence[str],
) -> tuple[list[CandidatePublication], list[SkippedCandidate]]:
    accepted: list[CandidatePublication] = []
    skipped: list[SkippedCandidate] = []
    for candidate in candidates:
        if not target_author_match(candidate, target, target_orcid, affiliation_terms):
            continue  # Most interval records are unrelated; omit them from the report.
        accepted.append(candidate)
    return accepted, skipped


def candidate_skip(candidate: CandidatePublication, reason: str, key: str = "") -> SkippedCandidate:
    return SkippedCandidate(candidate=candidate, reason=reason, matching_key=key)


def deduplicate_external_candidates(
    candidates: Sequence[CandidatePublication],
) -> list[CandidatePublication]:
    """Prefer PubMed over a linked or title-identical bioRxiv record."""
    ordered = sorted(
        candidates,
        key=lambda item: (
            item.source == "PubMed",
            item.publication_date,
            item.version,
        ),
        reverse=True,
    )
    accepted: list[CandidatePublication] = []
    seen_dois: set[str] = set()
    seen_pmids: set[str] = set()
    seen_titles: set[str] = set()
    for candidate in ordered:
        identifiers = {
            normalize_doi(candidate.doi).casefold(),
            normalize_doi(candidate.published_doi).casefold(),
        } - {""}
        if identifiers.intersection(seen_dois):
            continue
        if candidate.pmid and candidate.pmid in seen_pmids:
            continue
        if candidate.normalized_title in seen_titles:
            continue
        accepted.append(candidate)
        seen_dois.update(identifiers)
        if candidate.pmid:
            seen_pmids.add(candidate.pmid)
        if candidate.normalized_title:
            seen_titles.add(candidate.normalized_title)
    return accepted


def plan_changes(
    candidates: Sequence[CandidatePublication],
    index: BibliographyIndex,
    people: Mapping[str, Person],
    aliases: Mapping[str, set[str]],
    *,
    duplicate_title_threshold: float,
    ambiguous_title_threshold: float,
    biorxiv_client: BioRxivClient | None = None,
    target_umid: str = "",
    target_orcid: str = "",
) -> DiscoveryResult:
    result = DiscoveryResult()
    occupied_keys = set(index.by_key)

    for candidate in deduplicate_external_candidates(candidates):
        identifier_match = index.identifier_match(candidate)
        if identifier_match is not None:
            result.skipped.append(
                candidate_skip(candidate, "already present by DOI or PMID", identifier_match.key)
            )
            continue

        # Resolve an explicit bioRxiv-to-journal relationship before checking
        # titles. Published articles commonly retain the preprint title, and a
        # title-first check would otherwise suppress the intended upgrade.
        linked_preprint: ExistingPublication | None = None
        if candidate.source == "PubMed" and candidate.doi and biorxiv_client is not None:
            preprint_doi = biorxiv_client.publication_link_for_doi(candidate.doi)
            if preprint_doi:
                linked_preprint = index.by_doi.get(preprint_doi.casefold())
        if linked_preprint is not None and linked_preprint.status == "preprint":
            members, author_map = infer_candidate_members(
                candidate,
                people,
                aliases,
                target_umid=target_umid,
                target_orcid=target_orcid,
            )
            result.upgrades.append(
                ProposedChange(
                    kind="upgrade",
                    candidate=candidate,
                    bibkey=linked_preprint.key,
                    existing_key=linked_preprint.key,
                    reason=f"PubMed article is explicitly linked to bioRxiv DOI {linked_preprint.doi}",
                    members=members,
                    author_member_map=author_map,
                )
            )
            continue

        title_match = index.exact_title_match(candidate)
        if title_match is not None:
            if candidate.source == "PubMed" and title_match.status == "preprint":
                result.skipped.append(
                    candidate_skip(
                        candidate,
                        "probable published version of an existing preprint "
                        "(exact normalized title); no stable bioRxiv publication link was returned",
                        title_match.key,
                    )
                )
            else:
                result.skipped.append(
                    candidate_skip(candidate, "already present by normalized title", title_match.key)
                )
            continue

        closest, score = index.closest_title(candidate)
        if closest is not None and score >= duplicate_title_threshold:
            if candidate.source == "PubMed" and closest.status == "preprint":
                result.skipped.append(
                    candidate_skip(
                        candidate,
                        f"probable published version of an existing preprint (title similarity {score:.3f}); no stable bioRxiv publication link was returned",
                        closest.key,
                    )
                )
            else:
                result.skipped.append(
                    candidate_skip(candidate, f"probable duplicate by title similarity ({score:.3f})", closest.key)
                )
            continue
        if closest is not None and score >= ambiguous_title_threshold:
            result.skipped.append(
                candidate_skip(candidate, f"ambiguous title match ({score:.3f}); manual review required", closest.key)
            )
            continue

        bibkey = make_citation_key(candidate, occupied_keys)
        occupied_keys.add(bibkey)
        members, author_map = infer_candidate_members(
            candidate,
            people,
            aliases,
            target_umid=target_umid,
            target_orcid=target_orcid,
        )
        result.additions.append(
            ProposedChange(
                kind="add",
                candidate=candidate,
                bibkey=bibkey,
                reason="not present by DOI, PMID, or normalized title",
                members=members,
                author_member_map=author_map,
            )
        )

    result.additions.sort(key=lambda item: item.candidate.publication_date, reverse=True)
    result.upgrades.sort(key=lambda item: item.candidate.publication_date, reverse=True)
    return result


def metadata_filename(metadata_dir: Path, bibkey: str) -> Path:
    return metadata_dir / f"{bibkey.casefold()}.yml"


def write_sidecar(change: ProposedChange, metadata_dir: Path) -> Path:
    path = metadata_filename(metadata_dir, change.bibkey)
    if path.exists():
        raise DiscoveryError(f"Refusing to overwrite existing publication sidecar: {path}")
    data: dict[str, Any] = {
        "bibkey": change.bibkey,
        "members": change.members,
    }
    if change.author_member_map:
        data["author_member_map"] = change.author_member_map
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000),
        encoding="utf-8",
    )
    return path


def apply_changes(
    result: DiscoveryResult,
    bibliography_path: Path,
    metadata_dir: Path,
    index: BibliographyIndex,
) -> None:
    editor = BibFileEditor(bibliography_path)

    for change in result.upgrades:
        existing = index.by_key[change.existing_key]
        replacement = format_candidate_bibtex(
            change.candidate,
            change.bibkey,
            preserved_preprint=existing,
        )
        editor.replace(change.existing_key, replacement)

    # Insert oldest first so multiple new records with the same date retain the
    # final newest-first ordering supplied by ``result.additions``.
    for change in reversed(result.additions):
        editor.insert(
            format_candidate_bibtex(change.candidate, change.bibkey),
            change.candidate.publication_date,
        )
        sidecar = write_sidecar(change, metadata_dir)
        result.changed_files.append(str(sidecar))

    if result.changed:
        editor.write()
        result.changed_files.insert(0, str(bibliography_path))


def discover_publications(
    root: Path,
    config: Mapping[str, Any],
    *,
    sources: str = "all",
    lookback_days: int | None = None,
    biorxiv_start_date: date | None = None,
    today: date | None = None,
    http: HttpClient | None = None,
    dry_run: bool = False,
) -> DiscoveryResult:
    root = root.resolve()
    today = today or date.today()
    people, _ = load_people(root / "_people")
    metadata, _ = load_metadata(root / "publication_metadata")
    entries, source_paths = load_bibliography(root / "bibliography")
    if len(source_paths) != 1 or source_paths[0].name != "publications.bib":
        raise DiscoveryError(
            "Publication discovery expects one authoritative bibliography at "
            "bibliography/publications.bib"
        )
    bibliography_path = source_paths[0]

    target_umid = str(config.get("target_umid") or "").strip()
    if target_umid not in people:
        raise DiscoveryError(f"Configured target_umid '{target_umid}' was not found in _people")
    target = people[target_umid]
    target_profile = load_yaml_file(target.source)
    social = target_profile.get("social") or {}
    target_orcid = normalize_orcid(social.get("orcid", "") if isinstance(social, Mapping) else "")
    contact_email = str(social.get("email") or "").strip() if isinstance(social, Mapping) else ""

    matching_config = config.get("matching") or {}
    affiliation_terms = list(matching_config.get("affiliation_terms") or [])
    duplicate_threshold = float(matching_config.get("duplicate_title_threshold", 0.97))
    ambiguous_threshold = float(matching_config.get("ambiguous_title_threshold", 0.90))
    if not 0 <= ambiguous_threshold <= duplicate_threshold <= 1:
        raise DiscoveryError("Title matching thresholds must satisfy 0 <= ambiguous <= duplicate <= 1")

    http = http or HttpClient(
        user_agent=f"BoyleLabPublicationDiscovery/1.0 ({contact_email or 'apboyle@umich.edu'})"
    )
    candidates: list[CandidatePublication] = []
    initial_skips: list[SkippedCandidate] = []

    pubmed_config = config.get("pubmed") or {}
    pubmed_enabled = bool(pubmed_config.get("enabled", True)) and sources in {"all", "pubmed"}
    if pubmed_enabled:
        api_key = os.environ.get("NCBI_API_KEY", "").strip()
        pubmed = PubMedClient(http, email=contact_email, api_key=api_key)
        query = str(pubmed_config.get("query") or build_pubmed_query(target, target_orcid))
        raw_pubmed = pubmed.discover(query, int(pubmed_config.get("max_results", 1000)))
        accepted, skipped = filter_pubmed_candidates(
            raw_pubmed,
            target,
            target_orcid,
            affiliation_terms,
            list(pubmed_config.get("excluded_publication_types") or []),
        )
        candidates.extend(accepted)
        initial_skips.extend(skipped)

    biorxiv_config = config.get("biorxiv") or {}
    biorxiv_enabled = bool(biorxiv_config.get("enabled", True)) and sources in {"all", "biorxiv"}
    biorxiv_client: BioRxivClient | None = None
    if biorxiv_enabled:
        biorxiv_client = BioRxivClient(http, server=str(biorxiv_config.get("server") or "biorxiv"))
        window = int(lookback_days or biorxiv_config.get("lookback_days", 21))
        start = biorxiv_start_date or (today - timedelta(days=max(1, window)))
        raw_biorxiv = biorxiv_client.discover(start, today)
        accepted, skipped = filter_biorxiv_candidates(
            raw_biorxiv,
            target,
            target_orcid,
            affiliation_terms,
        )
        candidates.extend(accepted)
        initial_skips.extend(skipped)

    index = BibliographyIndex(entries)
    aliases = load_sidecar_aliases(metadata)
    result = plan_changes(
        candidates,
        index,
        people,
        aliases,
        duplicate_title_threshold=duplicate_threshold,
        ambiguous_title_threshold=ambiguous_threshold,
        biorxiv_client=biorxiv_client,
        target_umid=target_umid,
        target_orcid=target_orcid,
    )
    result.skipped = initial_skips + result.skipped

    if not dry_run:
        apply_changes(result, bibliography_path, root / "publication_metadata", index)
    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def identifier_text(candidate: CandidatePublication) -> str:
    values: list[str] = []
    if candidate.doi:
        values.append(f"DOI `{candidate.doi}`")
    if candidate.pmid:
        values.append(f"PMID `{candidate.pmid}`")
    return "; ".join(values) or candidate.source_id


def markdown_escape_table(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).replace("|", r"\|").strip()


def render_report(
    result: DiscoveryResult,
    *,
    run_date: date,
    sources: str,
    biorxiv_window: str,
) -> str:
    lines = [
        "# Automated publication discovery",
        "",
        f"Run date: **{run_date.isoformat()}**  ",
        f"Sources checked: **{sources}**  ",
        f"bioRxiv interval: **{biorxiv_window}**",
        "",
        "This pull request was prepared from external metadata and requires human review before merging.",
        "",
    ]

    if result.additions:
        lines.extend(
            [
                "## Proposed additions",
                "",
                "| Citation key | Source | Publication | Identifiers | Inferred lab members |",
                "|---|---|---|---|---|",
            ]
        )
        for change in result.additions:
            candidate = change.candidate
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{change.bibkey}`",
                        candidate.source,
                        markdown_escape_table(candidate.title),
                        markdown_escape_table(identifier_text(candidate)),
                        ", ".join(f"`{member}`" for member in change.members) or "none inferred",
                    ]
                )
                + " |"
            )
        lines.append("")

    if result.upgrades:
        lines.extend(
            [
                "## Proposed preprint-to-journal updates",
                "",
                "| Existing citation key | Publication | New identifiers | Basis |",
                "|---|---|---|---|",
            ]
        )
        for change in result.upgrades:
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{change.existing_key}`",
                        markdown_escape_table(change.candidate.title),
                        markdown_escape_table(identifier_text(change.candidate)),
                        markdown_escape_table(change.reason),
                    ]
                )
                + " |"
            )
        lines.append("")

    review_skips = [
        item
        for item in result.skipped
        if "manual review" in item.reason or "probable published version" in item.reason
    ]
    if review_skips:
        lines.extend(
            [
                "## Candidates requiring manual review",
                "",
                "These records were not added automatically.",
                "",
                "| Source | Publication | Reason | Possible match |",
                "|---|---|---|---|",
            ]
        )
        for item in review_skips:
            lines.append(
                "| "
                + " | ".join(
                    [
                        item.candidate.source,
                        markdown_escape_table(item.candidate.title),
                        markdown_escape_table(item.reason),
                        f"`{item.matching_key}`" if item.matching_key else "—",
                    ]
                )
                + " |"
            )
        lines.append("")

    if not result.changed:
        lines.extend(["## Result", "", "No new high-confidence publications were found.", ""])

    if result.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in result.warnings)
        lines.append("")

    lines.extend(
        [
            "## Review checklist",
            "",
            "- [ ] Confirm that every proposed record is an Alan P. Boyle publication.",
            "- [ ] Confirm author order, names, equal-contribution markers, and co-senior-author markers.",
            "- [ ] Confirm the permanent citation key before merge; it must not change later.",
            "- [ ] Confirm inferred `members` and any `author_member_map` entries in the sidecar.",
            "- [ ] Confirm journal, publication date, volume, issue, pages, DOI, PMID, and abstract.",
            "- [ ] For an updated preprint, confirm that the journal article is the same work.",
            "- [ ] Add website-only fields such as `summary`, `topics`, `links`, or `featured` when appropriate.",
            "",
            "The workflow regenerates `_papers/*.yml`, `pub.bib`, the CV publication source, and `assets/ABoyle_CV.pdf`, then runs the repository test suite before opening the draft pull request.",
            "",
        ]
    )
    return "\n".join(lines)

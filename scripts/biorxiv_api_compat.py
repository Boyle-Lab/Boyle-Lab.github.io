#!/usr/bin/env python3
"""Reliability fixes for the bioRxiv API used by publication discovery.

This module is imported by ``scripts/discover_publications.py`` before the
normal discovery run starts.  It updates the existing publication-discovery
classes in memory, leaving the rest of the publication matching and BibTeX
formatting implementation unchanged.

The compatibility layer addresses three observed API behaviors:

* the explicit ``/json`` content-detail route can return a non-JSON response;
* a proxy or upstream service can occasionally return HTML with HTTP 200; and
* bioRxiv pagination reports the page size in ``messages[0].count`` and should
  not be assumed to contain 100 records.
"""

from __future__ import annotations

from datetime import date
import json
import re
import time
from typing import Any, Mapping

import publication_discovery as discovery


def _reliable_get_json(
    self: discovery.HttpClient,
    url: str,
    params: Mapping[str, Any] | None = None,
    *,
    allow_not_found: bool = False,
) -> dict[str, Any] | None:
    """Decode a JSON object, retrying malformed HTTP-200 responses.

    ``HttpClient.get_bytes`` already retries network errors and transient HTTP
    status codes.  This additional loop handles the separate case in which an
    upstream proxy returns an HTML or otherwise malformed body with status 200.
    """

    for attempt in range(self.retries):
        payload = self.get_bytes(url, params, allow_not_found=allow_not_found)
        if payload is None:
            return None

        problem: Exception | None = None
        try:
            value = json.loads(payload.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            problem = exc
        else:
            if isinstance(value, dict):
                return value
            problem = TypeError(
                f"expected a JSON object, received {type(value).__name__}"
            )

        preview = payload[:240].decode("utf-8", errors="replace")
        preview = re.sub(r"\s+", " ", preview).strip()
        detail = f"; response begins with {preview!r}" if preview else ""
        if attempt + 1 >= self.retries:
            raise discovery.DiscoveryError(
                f"Invalid JSON returned by {url} after "
                f"{self.retries} attempt(s){detail}"
            ) from problem
        time.sleep(2**attempt)

    raise discovery.DiscoveryError(f"Invalid JSON returned by {url}")


def _details_page(
    self: discovery.BioRxivClient,
    start: date,
    end: date,
    cursor: int,
) -> dict[str, Any] | None:
    """Fetch one bioRxiv content-detail page using a safe endpoint order."""

    base_url = (
        f"{self.BASE}/details/{self.server}/"
        f"{start.isoformat()}/{end.isoformat()}/{cursor}"
    )
    errors: list[str] = []

    # bioRxiv defaults to JSON when the format suffix is omitted.  Use that
    # route first; retain /json only as a compatibility fallback.
    for url in (base_url, f"{base_url}/json"):
        try:
            return self.http.get_json(url)
        except discovery.DiscoveryError as exc:
            errors.append(f"{url}: {exc}")

    raise discovery.DiscoveryError(
        "bioRxiv returned unusable responses from both JSON endpoints: "
        + " | ".join(errors)
    )


def _reliable_biorxiv_discover(
    self: discovery.BioRxivClient,
    start: date,
    end: date,
) -> list[discovery.CandidatePublication]:
    """Retrieve all pages and retain the newest version of each preprint."""

    cursor = 0
    latest_by_doi: dict[str, discovery.CandidatePublication] = {}

    while True:
        data = self._details_page(start, end, cursor)
        if data is None:
            break

        page = discovery.parse_biorxiv_collection(data)
        for candidate in page:
            key = candidate.doi.casefold() or candidate.normalized_title
            previous = latest_by_doi.get(key)
            if previous is None or candidate.version >= previous.version:
                latest_by_doi[key] = candidate

        messages = data.get("messages") or []
        message = (
            messages[0]
            if messages and isinstance(messages[0], Mapping)
            else {}
        )
        try:
            total = int(message.get("total") or 0)
        except (TypeError, ValueError):
            total = 0
        try:
            page_count = int(message.get("count") or len(page))
        except (TypeError, ValueError):
            page_count = len(page)

        if not page:
            break

        # Current bioRxiv responses commonly contain 30 records per page.  Use
        # the count returned by the API rather than assuming a fixed page size.
        cursor += max(page_count, len(page))
        if total and cursor >= total:
            break

    return sorted(
        latest_by_doi.values(),
        key=lambda item: item.publication_date,
        reverse=True,
    )


def install_biorxiv_api_fix() -> None:
    """Install the compatibility methods once for the current Python process."""

    if getattr(discovery, "_BIORXIV_API_COMPAT_INSTALLED", False):
        return

    discovery.HttpClient.get_json = _reliable_get_json
    discovery.BioRxivClient._details_page = _details_page
    discovery.BioRxivClient.discover = _reliable_biorxiv_discover
    discovery._BIORXIV_API_COMPAT_INSTALLED = True

from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest
import unittest.mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import publication_discovery  # noqa: E402
from biorxiv_api_compat import install_biorxiv_api_fix  # noqa: E402

install_biorxiv_api_fix()


class FakeByteResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        return self.payload


class PagedBioRxivHttp:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_json(self, url, params=None, *, allow_not_found=False):
        self.calls.append(url)
        cursor = int(url.rstrip("/").split("/")[-1])
        records = {
            0: {
                "doi": "10.1101/2026.08.10.111111",
                "title": "First preprint",
                "authors": "Jane Tester; Alan P Boyle",
                "date": "2026-08-10",
                "version": "1",
            },
            1: {
                "doi": "10.1101/2026.08.11.222222",
                "title": "Second preprint",
                "authors": "John Tester; Alan P Boyle",
                "date": "2026-08-11",
                "version": "1",
            },
        }
        record = records.get(cursor)
        collection = [record] if record else []
        return {
            "messages": [
                {
                    "status": "ok",
                    "cursor": cursor,
                    "count": len(collection),
                    "total": 2,
                }
            ],
            "collection": collection,
        }


class FallbackBioRxivHttp:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_json(self, url, params=None, *, allow_not_found=False):
        self.calls.append(url)
        if not url.endswith("/json"):
            raise publication_discovery.DiscoveryError(
                "Invalid JSON returned by default endpoint"
            )
        return {
            "messages": [{"status": "ok", "count": 0, "total": 0}],
            "collection": [],
        }


class HttpClientReliabilityTests(unittest.TestCase):
    def test_json_parser_retries_a_malformed_http_200_response(self) -> None:
        client = publication_discovery.HttpClient(
            user_agent="BoyleLabPublicationDiscovery/test",
            retries=2,
            minimum_interval=0,
        )
        responses = [
            FakeByteResponse(b"<html>temporary proxy response</html>"),
            FakeByteResponse(b'{"status": "ok"}'),
        ]
        with unittest.mock.patch(
            "publication_discovery.urlopen",
            side_effect=responses,
        ):
            with unittest.mock.patch("publication_discovery.time.sleep"):
                self.assertEqual(
                    client.get_json("https://example.test/data"),
                    {"status": "ok"},
                )


class BioRxivClientTests(unittest.TestCase):
    def test_default_json_route_and_reported_cursor_count_are_used(self) -> None:
        http = PagedBioRxivHttp()
        records = publication_discovery.BioRxivClient(http).discover(
            date(2026, 8, 1),
            date(2026, 8, 17),
        )
        self.assertEqual(
            [record.title for record in records],
            ["Second preprint", "First preprint"],
        )
        self.assertEqual(
            http.calls,
            [
                "https://api.biorxiv.org/details/biorxiv/2026-08-01/2026-08-17/0",
                "https://api.biorxiv.org/details/biorxiv/2026-08-01/2026-08-17/1",
            ],
        )
        self.assertTrue(all(not url.endswith("/json") for url in http.calls))

    def test_explicit_json_route_is_only_a_fallback(self) -> None:
        http = FallbackBioRxivHttp()
        records = publication_discovery.BioRxivClient(http).discover(
            date(2026, 8, 1),
            date(2026, 8, 17),
        )
        self.assertEqual(records, [])
        self.assertEqual(
            http.calls,
            [
                "https://api.biorxiv.org/details/biorxiv/2026-08-01/2026-08-17/0",
                "https://api.biorxiv.org/details/biorxiv/2026-08-01/2026-08-17/0/json",
            ],
        )


if __name__ == "__main__":
    unittest.main()

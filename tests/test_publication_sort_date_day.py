"""Regression tests for the separate publication day field.

Run from the repository root:
    python3 -m unittest discover -s tests -p 'test_publication_sort_date_day.py' -v
"""
from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from publication_tools import PublicationError, publication_sort_date


class PublicationSortDateDayTests(unittest.TestCase):
    def test_bibtex_day(self):
        self.assertEqual(
            publication_sort_date({"year": "2026", "month": "sep", "day": "28"}, {}),
            "2026-09-28",
        )

    def test_numeric_and_named_months(self):
        for month in ("9", "09", "sep", "Sept", "September"):
            with self.subTest(month=month):
                self.assertEqual(
                    publication_sort_date({"year": "2026", "month": month, "day": "7"}, {}),
                    "2026-09-07",
                )

    def test_day_normalization(self):
        for day in ("7", "07", " 7 ", "{07}"):
            with self.subTest(day=day):
                self.assertEqual(
                    publication_sort_date({"year": "2026", "month": "9", "day": day}, {}),
                    "2026-09-07",
                )

    def test_metadata_day_overrides_bibtex(self):
        for day in (18, "18"):
            with self.subTest(day=day):
                self.assertEqual(
                    publication_sort_date(
                        {"year": "2026", "month": "sep", "day": "7"}, {"day": day}
                    ),
                    "2026-09-18",
                )

    def test_empty_metadata_day_uses_bibtex(self):
        for day in (None, "", "  "):
            with self.subTest(day=day):
                self.assertEqual(
                    publication_sort_date(
                        {"year": "2026", "month": "sep", "day": "7"}, {"day": day}
                    ),
                    "2026-09-07",
                )

    def test_missing_day_defaults_to_first(self):
        for day in (None, "", "  "):
            with self.subTest(day=day):
                self.assertEqual(
                    publication_sort_date({"year": "2026", "month": "sep", "day": day}, {}),
                    "2026-09-01",
                )
        self.assertEqual(publication_sort_date({"year": "2026", "month": "sep"}, {}), "2026-09-01")

    def test_year_only_unchanged(self):
        self.assertEqual(publication_sort_date({"year": "2026"}, {}), "2026-01-01")

    def test_unknown_year_unchanged(self):
        self.assertEqual(publication_sort_date({}, {}), "0000-01-01")

    def test_leap_day(self):
        self.assertEqual(
            publication_sort_date({"year": "2024", "month": "feb", "day": "29"}, {}),
            "2024-02-29",
        )

    def test_invalid_days_raise_publication_error(self):
        for day in ("0", "-1", "32", "seven", "7.5"):
            with self.subTest(day=day):
                with self.assertRaisesRegex(PublicationError, "Invalid publication date"):
                    publication_sort_date({"year": "2026", "month": "sep", "day": day}, {})

    def test_invalid_calendar_dates_raise_publication_error(self):
        for fields in (
            {"year": "2026", "month": "feb", "day": "29"},
            {"year": "2026", "month": "apr", "day": "31"},
        ):
            with self.subTest(fields=fields):
                with self.assertRaises(PublicationError):
                    publication_sort_date(fields, {})

    def test_metadata_zero_day_is_not_treated_as_missing(self):
        with self.assertRaises(PublicationError):
            publication_sort_date({"year": "2026", "month": "sep", "day": "7"}, {"day": 0})

    def test_full_date_precedence_unchanged(self):
        self.assertEqual(
            publication_sort_date(
                {"year": "2026", "month": "sep", "day": "28", "date": "2026-06-11"}, {}
            ),
            "2026-06-11",
        )
        self.assertEqual(
            publication_sort_date(
                {"year": "2026", "month": "sep", "day": "28", "date": "2026-06-11"},
                {"date": date(2026, 8, 17)},
            ),
            "2026-08-17",
        )

    def test_url_and_doi_precedence_preserved(self):
        fields = {
            "year": "2026", "month": "sep", "day": "28",
            "doi": "10.1101/2026.06.11.123456",
        }
        self.assertEqual(publication_sort_date(fields, {}), "2026-06-11")
        fields["url"] = "https://example.org/2026/08/17/article"
        self.assertEqual(publication_sort_date(fields, {}), "2026-08-17")

    def test_all_doi_days_preserved(self):
        for day in range(1, 32):
            for token in (str(day), f"{day:02d}"):
                with self.subTest(day=token):
                    self.assertEqual(
                        publication_sort_date(
                            {"year": "2026", "doi": f"10.1101/2026.01.{token}.123456"}, {}
                        ),
                        f"2026-01-{day:02d}",
                    )

    def test_metadata_doi_day_preserved(self):
        self.assertEqual(
            publication_sort_date({"year": "2026"}, {"doi": "10.1101/2026.06.26.123456"}),
            "2026-06-26",
        )

    def test_doi_day_does_not_match_numeric_prefix(self):
        for token in ("115", "32", "99"):
            with self.subTest(day=token):
                self.assertEqual(
                    publication_sort_date(
                        {"year": "2026", "month": "sep", "day": "28",
                         "doi": f"10.1101/2026.01.{token}.123456"}, {}
                    ),
                    "2026-09-28",
                )

    def test_doi_year_mismatch_uses_bibliographic_fields(self):
        self.assertEqual(
            publication_sort_date(
                {"year": "2026", "month": "sep", "day": "28",
                 "doi": "10.1101/2025.06.26.123456"}, {}
            ),
            "2026-09-28",
        )


if __name__ == "__main__":
    unittest.main()

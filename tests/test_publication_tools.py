from __future__ import annotations

from pathlib import Path
import re
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_publications import check_outputs, expected_outputs  # noqa: E402
from publication_tools import (  # noqa: E402
    Person,
    PublicationError,
    build_publication_record,
    latex_to_text,
    load_bibliography,
    load_metadata,
    load_people,
    parse_authors,
    parse_bibtex,
)


ALLOWED_PAPER_FIELDS = {
    "generated",
    "bibkey",
    "title",
    "author_list",
    "year",
    "sort_date",
    "members",
    "bibtex",
    "status",
    "publication_type",
    "journal",
    "volume",
    "number",
    "pages",
    "doi",
    "PMID",
    "primary_url",
    "pdf",
    "biorxiv",
    "links",
    "member_roles",
    "abstract",
    "featured",
    "topics",
    "summary",
    "teaser",
}
ALLOWED_AUTHOR_FIELDS = {
    "citation_name",
    "member_url",
    "member_name",
    "equal_contrib",
    "co_senior",
}


class BibTeXParserTests(unittest.TestCase):
    def test_nested_braces_and_quoted_values(self) -> None:
        source = r'''@article{Example2026,
          author = {*Doe, Jane Q. and {Example Consortium}},
          title = {{A title with {Protected Words} and \& punctuation}},
          year = "2026",
          note = {part one } # "part two"
        }'''
        entries = parse_bibtex(source)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].key, "Example2026")
        self.assertEqual(entries[0].fields["year"], "2026")
        self.assertIn("Protected Words", entries[0].fields["title"])
        self.assertEqual(entries[0].fields["note"], "part one part two")

    def test_unsafe_repository_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            bibliography = Path(directory)
            (bibliography / "publications.bib").write_text(
                "@article{10.1000/unsafe, author={Boyle, Alan P.}, title={Example}, year={2026}}",
                encoding="utf-8",
            )
            with self.assertRaises(PublicationError):
                load_bibliography(bibliography)

    def test_author_contribution_markers(self) -> None:
        authors = parse_authors(r"*Doe, Jane Q. and {\dag}Boyle, Alan P")
        self.assertTrue(authors[0]["equal_contrib"])
        self.assertTrue(authors[1]["co_senior"])
        self.assertEqual(authors[1]["citation_name"], "Boyle AP")

    def test_latex_to_unicode(self) -> None:
        self.assertEqual(latex_to_text(r"Muller{\textquoteright}s A \& B"), "Muller’s A & B")

    def test_scalar_news_link_is_normalized_to_list(self) -> None:
        entry = parse_bibtex(
            "@article{Example2026, author={Boyle, Alan P.}, title={Example}, year={2026}}"
        )[0]
        person = Person(
            umid="apboyle",
            name="Alan P. Boyle",
            source=Path("_people/Alan_Boyle.md"),
            url="/people/Alan_Boyle/",
        )
        record, messages = build_publication_record(
            entry,
            {"bibkey": entry.key, "members": ["apboyle"], "links": {"news": "/news/example/"}},
            {"apboyle": person},
        )
        self.assertFalse(messages)
        self.assertEqual(record["links"]["news"], ["/news/example/"])
        self.assertNotIn("authors_short", record)
        self.assertNotIn("matched_members", record)

    def test_invalid_status_is_rejected(self) -> None:
        entry = parse_bibtex(
            "@article{Example2026, author={Boyle, Alan P.}, title={Example}, year={2026}}"
        )[0]
        person = Person(
            umid="apboyle",
            name="Alan P. Boyle",
            source=Path("_people/Alan_Boyle.md"),
            url="/people/Alan_Boyle/",
        )
        with self.assertRaises(PublicationError):
            build_publication_record(
                entry,
                {"bibkey": entry.key, "members": ["apboyle"], "status": "unknown"},
                {"apboyle": person},
            )


class RepositoryPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs, cls.messages, cls.records = expected_outputs(ROOT)
        cls.by_key = {record["bibkey"]: record for record in cls.records}
        cls.entries, _ = load_bibliography(ROOT / "bibliography")

    def test_repository_builds_without_warnings_and_outputs_are_current(self) -> None:
        self.assertEqual(len(self.records), 87)
        self.assertEqual(len(self.records), len(self.entries))
        self.assertFalse([message for message in self.messages if message.level == "warning"])
        self.assertEqual(check_outputs(ROOT, self.outputs), [])
        self.assertIn(ROOT / "pub.bib", self.outputs)

    def test_repository_keys_and_filenames_are_stable_and_safe(self) -> None:
        pattern = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
        keys = [entry.key for entry in self.entries]
        self.assertTrue(all(pattern.fullmatch(key) for key in keys))
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(
            {path.name for path in (ROOT / "_papers").glob("*.yml")},
            {f"{key}.yml" for key in keys},
        )

    def test_generated_schema_contains_only_fields_used_by_site(self) -> None:
        for path in sorted((ROOT / "_papers").glob("*.yml")):
            text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(text.split("---", 2)[1]) or {}
            self.assertEqual(set(data) - ALLOWED_PAPER_FIELDS, set(), path.name)
            for required in (
                "generated",
                "bibkey",
                "title",
                "author_list",
                "year",
                "sort_date",
                "members",
                "bibtex",
            ):
                self.assertIn(required, data, f"{path.name}: {required}")
            self.assertTrue(data["bibtex"].lstrip().startswith("@"), path.name)
            for author in data["author_list"]:
                self.assertEqual(set(author) - ALLOWED_AUTHOR_FIELDS, set(), path.name)
                self.assertTrue(author.get("citation_name"), path.name)

    def test_every_generated_record_preserves_the_full_bibtex_author_list(self) -> None:
        entries_by_key = {entry.key: entry for entry in self.entries}
        for key, record in self.by_key.items():
            source_authors = parse_authors(entries_by_key[key].fields["author"])
            self.assertEqual(
                len(record["author_list"]),
                len(source_authors),
                f"{key}: generated byline was shortened",
            )
            self.assertEqual(
                [author["citation_name"] for author in record["author_list"]],
                [author["citation_name"] for author in source_authors],
                f"{key}: generated byline differs from BibTeX",
            )

    def test_publication_specific_name_map_handles_prior_name(self) -> None:
        onramp = self.by_key["Mumm2023OnRamp"]
        drexel = next(author for author in onramp["author_list"] if author["citation_name"] == "Drexel ML")
        self.assertEqual(drexel["member_name"], "Melissa Englund, Ph.D.")
        self.assertTrue(drexel["member_url"].startswith("/people/"))

        sidecars, _ = load_metadata(ROOT / "publication_metadata")
        self.assertEqual(
            sidecars["Mumm2023OnRamp"]["author_member_map"]["melyssae"],
            "Drexel, Melissa L",
        )

    def test_consortium_relationship_does_not_fake_byline_authorship(self) -> None:
        smaht = self.by_key["SMaHTNetwork2025SomaticMutationBenchmarking"]
        self.assertEqual(smaht["member_roles"]["apboyle"], "consortium")
        self.assertFalse(
            [author for author in smaht["author_list"] if author.get("member_name") == "Alan P. Boyle, Ph.D."]
        )

    def test_sidecars_and_people_do_not_use_legacy_identity_fields(self) -> None:
        for path in (ROOT / "publication_metadata").glob("*.yml"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("legacy_bibkeys:", text, path.name)
            self.assertNotIn("slug:", text, path.name)
        for path in (ROOT / "_people").glob("*.md"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("publication_names:", text, path.name)
            self.assertNotIn("author_aliases:", text, path.name)

    def test_deprecated_person_alias_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            people_dir = Path(directory)
            (people_dir / "Example.md").write_text(
                "---\nname: Example Person\numid: example\npublication_names:\n  - Prior, Example\n---\n",
                encoding="utf-8",
            )
            with self.assertRaises(PublicationError):
                load_people(people_dir)

    def test_featured_publication_assets_exist(self) -> None:
        featured = [record for record in self.records if record.get("featured")]
        self.assertEqual(len(featured), 4)
        for record in featured:
            self.assertTrue(record.get("summary"), record["bibkey"])
            self.assertTrue(record.get("topics"), record["bibkey"])
            teaser = ROOT / str(record["teaser"]).lstrip("/")
            self.assertTrue(teaser.is_file(), teaser)

    def test_dimensions_metric_is_loaded_once_and_no_search_controls_exist(self) -> None:
        citation = (ROOT / "_includes" / "publication_citation.html").read_text(encoding="utf-8")
        page = (ROOT / "_includes" / "publications_page.html").read_text(encoding="utf-8")
        self.assertIn('data-doi="{{ paper.doi | escape }}"', citation)
        self.assertIn('data-pmid="{{ paper.PMID | escape }}"', citation)
        self.assertIn("show_metrics=true", page)
        self.assertEqual(page.count("integration-dimensions-badge.digital-science.com"), 1)
        self.assertNotIn(">Dimensions<", citation)
        self.assertNotIn("publication-search", page)
        self.assertFalse((ROOT / "assets" / "js" / "publications.js").exists())
        self.assertFalse((ROOT / "assets" / "data" / "publications.json").exists())


if __name__ == "__main__":
    unittest.main()

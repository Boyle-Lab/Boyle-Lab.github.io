from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_publications import expected_outputs  # noqa: E402
from publication_tools import (  # noqa: E402
    Person,
    PublicationError,
    author_matches_person,
    build_publication_record,
    latex_to_text,
    load_bibliography,
    load_people,
    parse_authors,
    parse_bibtex,
)


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
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
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


class RepositoryDataTests(unittest.TestCase):
    def test_repository_builds_without_warnings(self) -> None:
        outputs, messages, records = expected_outputs(ROOT)
        entries, _ = load_bibliography(ROOT / "bibliography")
        self.assertGreater(len(records), 0)
        self.assertEqual(len(records), len(entries))
        self.assertFalse([message for message in messages if message.level == "warning"])
        self.assertIn(ROOT / "pub.bib", outputs)

    def test_repository_keys_are_filename_safe(self) -> None:
        import re

        entries, _ = load_bibliography(ROOT / "bibliography")
        pattern = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")
        self.assertTrue(all(pattern.fullmatch(entry.key) for entry in entries))
        self.assertEqual(len(entries), len({entry.key for entry in entries}))

    def test_publication_alias_matches_prior_name(self) -> None:
        people, _ = load_people(ROOT / "_people")
        author = parse_authors("Drexel, Melissa L.")[0]
        self.assertTrue(author_matches_person(author, people["melyssae"]))

    def test_consortium_relationship_does_not_fake_byline_authorship(self) -> None:
        _outputs, _messages, records = expected_outputs(ROOT)
        by_key = {record["bibkey"]: record for record in records}
        smaht = by_key["SMaHTNetwork2025SomaticMutationBenchmarking"]
        self.assertEqual(smaht["member_roles"]["apboyle"], "consortium")
        self.assertNotIn("apboyle", smaht["matched_members"])

    def test_dimensions_citation_metric_is_configured_once(self) -> None:
        citation_template = (ROOT / "_includes" / "publication_citation.html").read_text()
        publications_page = (ROOT / "_includes" / "publications_page.html").read_text()

        self.assertIn('data-doi="{{ paper.doi | escape }}"', citation_template)
        self.assertIn('data-pmid="{{ paper.PMID | escape }}"', citation_template)
        self.assertIn("show_metrics=true", publications_page)
        self.assertEqual(
            publications_page.count(
                "https://integration-dimensions-badge.digital-science.com/static/com/badge.js"
            ),
            1,
        )


if __name__ == "__main__":
    unittest.main()

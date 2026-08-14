from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from publication_discovery import (  # noqa: E402
    BibliographyIndex,
    BibFileEditor,
    CandidatePublication,
    DiscoveryAuthor,
    ExistingPublication,
    ProposedChange,
    apply_changes,
    discover_publications,
    format_candidate_bibtex,
    infer_candidate_members,
    load_discovery_config,
    make_citation_key,
    parse_biorxiv_record,
    parse_pubmed_xml,
    plan_changes,
    target_author_match,
)
from publication_tools import Person, build_publication_record, load_bibliography, load_metadata, load_people  # noqa: E402


PUBMED_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID Version="1">99900001</PMID>
      <Article PubModel="Electronic">
        <Journal>
          <JournalIssue CitedMedium="Internet">
            <Volume>15</Volume>
            <Issue>4</Issue>
            <PubDate><Year>2026</Year><Month>Aug</Month><Day>12</Day></PubDate>
          </JournalIssue>
          <Title>Genome Biology</Title>
        </Journal>
        <ArticleTitle>Genome architecture reveals <i>repeat-specific</i> regulation</ArticleTitle>
        <Pagination><MedlinePgn>101-115</MedlinePgn></Pagination>
        <Abstract>
          <AbstractText Label="BACKGROUND">Background text.</AbstractText>
          <AbstractText Label="RESULTS">Results text.</AbstractText>
        </Abstract>
        <AuthorList CompleteYN="Y">
          <Author ValidYN="Y">
            <LastName>Tester</LastName><ForeName>Jane Q</ForeName><Initials>JQ</Initials>
            <AffiliationInfo><Affiliation>University of Michigan, Ann Arbor, MI.</Affiliation></AffiliationInfo>
          </Author>
          <Author ValidYN="Y">
            <LastName>Pavlovic</LastName><ForeName>Katarina</ForeName><Initials>K</Initials>
          </Author>
          <Author ValidYN="Y">
            <LastName>Boyle</LastName><ForeName>Alan P</ForeName><Initials>AP</Initials>
            <Identifier Source="ORCID">0000-0002-2081-1105</Identifier>
            <AffiliationInfo><Affiliation>Department of Computational Medicine and Bioinformatics, University of Michigan.</Affiliation></AffiliationInfo>
          </Author>
        </AuthorList>
        <PublicationTypeList><PublicationType>Journal Article</PublicationType></PublicationTypeList>
        <ArticleDate DateType="Electronic"><Year>2026</Year><Month>08</Month><Day>12</Day></ArticleDate>
        <ELocationID EIdType="doi">10.1234/example.2026.1</ELocationID>
      </Article>
    </MedlineCitation>
    <PubmedData>
      <ArticleIdList>
        <ArticleId IdType="pubmed">99900001</ArticleId>
        <ArticleId IdType="doi">10.1234/example.2026.1</ArticleId>
      </ArticleIdList>
    </PubmedData>
  </PubmedArticle>
</PubmedArticleSet>
"""


class FakeHttp:
    def __init__(self, *, pubmed_xml: bytes = PUBMED_XML) -> None:
        self.pubmed_xml = pubmed_xml
        self.calls: list[str] = []

    def get_json(self, url, params=None, *, allow_not_found=False):
        self.calls.append(url)
        if url.endswith("esearch.fcgi"):
            return {"esearchresult": {"idlist": ["99900001"]}}
        if "/details/biorxiv/" in url:
            return {"messages": [{"total": 0}], "collection": []}
        if "/pubs/biorxiv/" in url:
            return {"messages": [], "collection": []}
        raise AssertionError(f"Unexpected JSON request: {url}")

    def get_bytes(self, url, params=None, *, allow_not_found=False):
        self.calls.append(url)
        if url.endswith("efetch.fcgi"):
            return self.pubmed_xml
        raise AssertionError(f"Unexpected byte request: {url}")


class LinkedPreprintClient:
    def __init__(self, preprint_doi: str) -> None:
        self.preprint_doi = preprint_doi

    def publication_link_for_doi(self, published_doi: str) -> str:
        return self.preprint_doi if published_doi else ""


class PublicationParsingTests(unittest.TestCase):
    def test_pubmed_xml_is_converted_to_complete_candidate(self) -> None:
        candidates = parse_pubmed_xml(PUBMED_XML)
        self.assertEqual(len(candidates), 1)
        candidate = candidates[0]
        self.assertEqual(candidate.pmid, "99900001")
        self.assertEqual(candidate.doi, "10.1234/example.2026.1")
        self.assertEqual(candidate.title, "Genome architecture reveals repeat-specific regulation")
        self.assertEqual(candidate.journal, "Genome Biology")
        self.assertEqual(candidate.volume, "15")
        self.assertEqual(candidate.issue, "4")
        self.assertEqual(candidate.pages, "101-115")
        self.assertEqual(candidate.publication_date, "2026-08-12")
        self.assertEqual(candidate.authors[-1].orcid, "0000-0002-2081-1105")
        self.assertIn("BACKGROUND: Background text.", candidate.abstract)

    def test_biorxiv_record_uses_latest_metadata_fields(self) -> None:
        candidate = parse_biorxiv_record(
            {
                "doi": "10.1101/2026.08.10.123456",
                "title": "A targeted long-read method",
                "authors": "Jane Tester; Alan P Boyle",
                "date": "2026-08-11",
                "version": "2",
                "category": "genomics",
                "abstract": "An abstract.",
                "published": "10.1234/final.paper",
            }
        )
        self.assertEqual(candidate.source, "bioRxiv")
        self.assertEqual(candidate.year, 2026)
        self.assertEqual(candidate.version, 2)
        self.assertEqual(candidate.authors[-1].family, "Boyle")
        self.assertEqual(candidate.published_doi, "10.1234/final.paper")
        self.assertTrue(candidate.pdf.endswith(".full.pdf"))

    def test_biorxiv_na_published_value_is_not_treated_as_a_shared_doi(self) -> None:
        first = parse_biorxiv_record(
            {
                "doi": "10.1101/2026.08.10.111111",
                "title": "First unpublished preprint",
                "authors": "Jane Tester; Alan P Boyle",
                "date": "2026-08-10",
                "published": "NA",
            }
        )
        second = parse_biorxiv_record(
            {
                "doi": "10.1101/2026.08.11.222222",
                "title": "Second unpublished preprint",
                "authors": "John Tester; Alan P Boyle",
                "date": "2026-08-11",
                "published": "N/A",
            }
        )
        self.assertEqual(first.published_doi, "")
        self.assertEqual(second.published_doi, "")

        from publication_discovery import deduplicate_external_candidates

        accepted = deduplicate_external_candidates([first, second])
        self.assertEqual({item.doi for item in accepted}, {first.doi, second.doi})

    def test_target_identity_accepts_orcid_or_full_name(self) -> None:
        target = Person("apboyle", "Alan P. Boyle, Ph.D.", Path("Alan.md"), "/people/Alan/")
        candidate = parse_pubmed_xml(PUBMED_XML)[0]
        self.assertTrue(
            target_author_match(
                candidate,
                target,
                "0000-0002-2081-1105",
                ["University of Michigan"],
            )
        )

    def test_citation_key_is_safe_stable_and_collision_aware(self) -> None:
        candidate = parse_pubmed_xml(PUBMED_XML)[0]
        key = make_citation_key(candidate, set())
        self.assertRegex(key, r"^Tester2026[A-Za-z0-9]+$")
        collision = make_citation_key(candidate, {key})
        self.assertNotEqual(collision, key)
        self.assertTrue(collision.startswith(key))


class PublicationPlanningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.people = {
            "apboyle": Person("apboyle", "Alan P. Boyle, Ph.D.", Path("Alan.md"), "/people/Alan/"),
            "katrinp": Person("katrinp", "Katarina Pavlovic", Path("Katarina.md"), "/people/Katarina/"),
        }

    def test_member_inference_follows_author_order(self) -> None:
        candidate = parse_pubmed_xml(PUBMED_XML)[0]
        members, overrides = infer_candidate_members(
            candidate,
            self.people,
            {},
            target_umid="apboyle",
            target_orcid="0000-0002-2081-1105",
        )
        self.assertEqual(members, ["katrinp", "apboyle"])
        self.assertEqual(overrides, {})

    def test_existing_doi_is_not_added(self) -> None:
        entry = load_single_entry(
            "@article{Tester2026Existing,\n"
            "  author = {Tester, Jane Q and Boyle, Alan P},\n"
            "  title = {{Genome architecture reveals repeat-specific regulation}},\n"
            "  journal = {Genome Biology},\n"
            "  year = {2026},\n"
            "  doi = {10.1234/example.2026.1},\n"
            "  note = {{PMID:} 99900001}\n"
            "}"
        )
        result = plan_changes(
            [parse_pubmed_xml(PUBMED_XML)[0]],
            BibliographyIndex([entry]),
            self.people,
            {},
            duplicate_title_threshold=0.97,
            ambiguous_title_threshold=0.90,
            target_umid="apboyle",
            target_orcid="0000-0002-2081-1105",
        )
        self.assertFalse(result.changed)
        self.assertEqual(result.skipped[0].matching_key, "Tester2026Existing")

    def test_explicit_biorxiv_link_upgrades_preprint_without_new_key(self) -> None:
        entry = load_single_entry(
            "@article{Tester2026GenomeArchitecture,\n"
            "  author = {Tester, Jane Q and Boyle, Alan P},\n"
            "  title = {{Genome architecture reveals repeat-specific regulation}},\n"
            "  journal = {bioRxiv},\n"
            "  year = {2026},\n"
            "  doi = {10.1101/2026.08.01.111111},\n"
            "  url = {https://www.biorxiv.org/content/10.1101/2026.08.01.111111v1}\n"
            "}"
        )
        result = plan_changes(
            [parse_pubmed_xml(PUBMED_XML)[0]],
            BibliographyIndex([entry]),
            self.people,
            {},
            duplicate_title_threshold=0.97,
            ambiguous_title_threshold=0.90,
            biorxiv_client=LinkedPreprintClient("10.1101/2026.08.01.111111"),
            target_umid="apboyle",
            target_orcid="0000-0002-2081-1105",
        )
        self.assertEqual(len(result.upgrades), 1)
        self.assertEqual(result.upgrades[0].bibkey, "Tester2026GenomeArchitecture")
        self.assertEqual(result.additions, [])

    def test_formatted_bibtex_matches_repository_conventions(self) -> None:
        candidate = parse_pubmed_xml(PUBMED_XML)[0]
        text = format_candidate_bibtex(candidate, "Tester2026GenomeArchitecture")
        self.assertIn("@article{Tester2026GenomeArchitecture,", text)
        self.assertIn("title = {{Genome architecture reveals repeat-specific regulation}}", text)
        self.assertIn("doi = {10.1234/example.2026.1}", text)
        self.assertIn("note = {{PMID:} 99900001}", text)

    def test_exact_title_preprint_without_link_is_reported_for_review(self) -> None:
        entry = load_single_entry(
            "@article{Tester2026GenomeArchitecture,\n"
            "  author = {Tester, Jane Q and Boyle, Alan P},\n"
            "  title = {{Genome architecture reveals repeat-specific regulation}},\n"
            "  journal = {bioRxiv},\n"
            "  year = {2026},\n"
            "  doi = {10.1101/2026.08.01.111111}\n"
            "}"
        )
        result = plan_changes(
            [parse_pubmed_xml(PUBMED_XML)[0]],
            BibliographyIndex([entry]),
            self.people,
            {},
            duplicate_title_threshold=0.97,
            ambiguous_title_threshold=0.90,
            biorxiv_client=LinkedPreprintClient(""),
            target_umid="apboyle",
            target_orcid="0000-0002-2081-1105",
        )
        self.assertFalse(result.changed)
        self.assertIn("probable published version", result.skipped[0].reason)

    def test_collective_author_receives_exactly_one_protective_brace_pair(self) -> None:
        candidate = CandidatePublication(
            source="PubMed",
            source_id="1",
            title="A consortium paper",
            authors=[DiscoveryAuthor(raw_name="Example Consortium", collective="Example Consortium")],
            year=2026,
            publication_date="2026-01-01",
            journal="Example Journal",
        )
        text = format_candidate_bibtex(candidate, "ExampleConsortium2026Paper")
        self.assertIn("author = {{Example Consortium}}", text)
        self.assertNotIn("author = {{{Example Consortium}}}", text)


class EndToEndDiscoveryTests(unittest.TestCase):
    def test_discovery_adds_bibtex_and_minimal_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bibliography").mkdir()
            (root / "publication_metadata").mkdir()
            (root / "_people").mkdir()
            (root / "_papers").mkdir()
            (root / "bibliography" / "publications.bib").write_text(
                "% Authoritative bibliography.\n\n"
                "@article{Existing2025Paper,\n"
                "  author = {Doe, Jane and Boyle, Alan P},\n"
                "  title = {{An existing paper}},\n"
                "  journal = {Example Journal},\n"
                "  year = {2025},\n"
                "  doi = {10.1000/existing}\n"
                "}\n",
                encoding="utf-8",
            )
            (root / "publication_metadata" / "existing2025paper.yml").write_text(
                "bibkey: Existing2025Paper\nmembers:\n- apboyle\n",
                encoding="utf-8",
            )
            (root / "_people" / "Alan_Boyle.md").write_text(
                "---\n"
                "layout: member\n"
                "publish: true\n"
                "name: Alan P. Boyle, Ph.D.\n"
                "umid: apboyle\n"
                "social:\n"
                "  email: apboyle@umich.edu\n"
                "  orcid: 0000-0002-2081-1105\n"
                "---\n",
                encoding="utf-8",
            )
            (root / "_people" / "Katarina_Pavlovic.md").write_text(
                "---\nlayout: member\npublish: true\nname: Katarina Pavlovic\numid: katrinp\n---\n",
                encoding="utf-8",
            )

            config = load_discovery_config(root / "missing-config.yml")
            result = discover_publications(
                root,
                config,
                sources="pubmed",
                today=date(2026, 8, 14),
                http=FakeHttp(),
            )
            self.assertEqual(len(result.additions), 1)
            key = result.additions[0].bibkey
            self.assertTrue(key.startswith("Tester2026"))

            entries, _ = load_bibliography(root / "bibliography")
            self.assertEqual(entries[0].key, key)
            self.assertEqual(len(entries), 2)

            sidecar = root / "publication_metadata" / f"{key.casefold()}.yml"
            self.assertTrue(sidecar.exists())
            sidecar_data = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(sidecar_data["bibkey"], key)
            self.assertEqual(sidecar_data["members"], ["katrinp", "apboyle"])

            people, _ = load_people(root / "_people")
            metadata, _ = load_metadata(root / "publication_metadata")
            generated, warnings = build_publication_record(entries[0], metadata[key], people)
            self.assertEqual(warnings, [])
            self.assertEqual(generated["members"], ["katrinp", "apboyle"])

    def test_bib_editor_keeps_header_separate_from_first_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "publications.bib"
            path.write_text(
                "% Header comment.\n\n"
                "@article{Old2025,\n  author = {Doe, Jane},\n  title = {Old},\n  year = {2025}\n}\n",
                encoding="utf-8",
            )
            editor = BibFileEditor(path)
            editor.insert(
                "@article{New2026,\n  author = {Doe, Jane},\n  title = {New},\n  year = {2026}\n}",
                "2026-01-01",
            )
            editor.write()
            text = path.read_text(encoding="utf-8")
            self.assertIn("% Header comment.\n\n@article{New2026", text)
            self.assertLess(text.index("New2026"), text.index("Old2025"))


def load_single_entry(text: str):
    from publication_tools import parse_bibtex

    entries = parse_bibtex(text)
    if len(entries) != 1:
        raise AssertionError("fixture must contain one BibTeX entry")
    return entries[0]


class DiscoveryWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = ROOT / ".github" / "workflows" / "discover-publications.yml"
        cls.text = cls.path.read_text(encoding="utf-8")
        cls.workflow = yaml.load(cls.text, Loader=yaml.BaseLoader)

    def test_workflow_is_scheduled_and_manually_runnable(self) -> None:
        triggers = self.workflow["on"]
        self.assertIn("schedule", triggers)
        self.assertIn("workflow_dispatch", triggers)
        self.assertIn("lookback_days", triggers["workflow_dispatch"]["inputs"])
        self.assertIn("biorxiv_start_date", triggers["workflow_dispatch"]["inputs"])

    def test_schedule_uses_ncbi_overnight_window(self) -> None:
        cron = self.workflow["on"]["schedule"][0]["cron"]
        self.assertEqual(cron, "17 7 * * 1")

    def test_discovery_documentation_and_local_make_targets_exist(self) -> None:
        self.assertTrue((ROOT / "PUBLICATION_DISCOVERY.md").is_file())
        self.assertIn("PUBLICATION_DISCOVERY.md", (ROOT / "_config.yml").read_text(encoding="utf-8"))
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("discover-publications-dry-run:", makefile)
        self.assertIn("discover-publications:", makefile)

    def test_workflow_has_minimum_pr_permissions(self) -> None:
        self.assertEqual(self.workflow["permissions"]["contents"], "write")
        self.assertEqual(self.workflow["permissions"]["pull-requests"], "write")

    def test_workflow_discovers_builds_tests_and_opens_draft_pr(self) -> None:
        self.assertIn("python scripts/discover_publications.py", self.text)
        self.assertIn("make publications", self.text)
        self.assertIn("make cv", self.text)
        self.assertIn("make test", self.text)
        self.assertIn("gh pr create", self.text)
        self.assertIn("--draft", self.text)
        self.assertIn("automation/publication-discovery", self.text)
        self.assertIn("assets/ABoyle_CV.pdf", self.text)

    def test_workflow_does_not_overwrite_an_open_review(self) -> None:
        self.assertIn("gh pr list", self.text)
        self.assertIn("manual edits in the open pull request are not overwritten", self.text)

    def test_makefile_exposes_local_discovery_commands(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("discover-publications:", makefile)
        self.assertIn("discover-publications-dry-run:", makefile)
        self.assertIn("scripts/discover_publications.py --dry-run", makefile)

    def test_discovery_documentation_and_configuration_are_present(self) -> None:
        guide = (ROOT / "PUBLICATION_DISCOVERY.md").read_text(encoding="utf-8")
        config = yaml.safe_load((ROOT / "publication_discovery.yml").read_text(encoding="utf-8"))
        self.assertIn("Required repository setting", guide)
        self.assertIn("Pull-request review", guide)
        self.assertEqual(config["target_umid"], "apboyle")
        self.assertEqual(config["biorxiv"]["lookback_days"], 21)


if __name__ == "__main__":
    unittest.main()

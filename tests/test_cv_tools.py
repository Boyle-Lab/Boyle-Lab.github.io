from __future__ import annotations

from pathlib import Path
import os
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from site_test_utils import ROOT

sys.path.insert(0, str(ROOT / "scripts"))

from build_cv import _source_date_epoch, check_outputs  # noqa: E402
from cv_tools import (  # noqa: E402
    PRINCIPAL_INVESTIGATOR_UMID,
    expected_cv_outputs,
    format_cv_publication,
    load_cv_publications,
    tex_escape,
)


class CVGenerationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.outputs, cls.messages, cls.publication_count = expected_cv_outputs(ROOT)
        cls.publications, _messages, cls.people = load_cv_publications(ROOT)
        cls.by_key = {publication.entry.key: publication for publication in cls.publications}
        cls.publications_tex = cls.outputs[ROOT / "cv" / "generated" / "publications.tex"]
        cls.patents_tex = cls.outputs[ROOT / "cv" / "generated" / "patents.tex"]

    def test_generated_cv_sources_are_current_and_complete(self) -> None:
        self.assertEqual(check_outputs(ROOT, self.outputs), [])
        labels = [
            int(value)
            for value in re.findall(
                r"^\\item\[\{\[(\d+)\]\}\] ",
                self.publications_tex,
                flags=re.MULTILINE,
            )
        ]
        self.assertEqual(labels, list(range(self.publication_count, 0, -1)))
        self.assertIn(r"\input{generated/publications.tex}", (ROOT / "cv" / "cv.tex").read_text())
        self.assertIn(r"\input{generated/patents.tex}", (ROOT / "cv" / "cv.tex").read_text())

    def test_author_highlighting_comes_from_website_member_records(self) -> None:
        hmmstr = format_cv_publication(self.by_key["VanDeynze2025HMMSTR"])
        self.assertIn(r"\underline{Van Deynze K}", hmmstr)
        self.assertIn(r"\underline{Mumm C}", hmmstr)
        self.assertIn(r"\textbf{Boyle AP}", hmmstr)
        self.assertEqual(PRINCIPAL_INVESTIGATOR_UMID, "apboyle")

    def test_publication_specific_historical_name_map_is_used(self) -> None:
        onramp = format_cv_publication(self.by_key["Mumm2023OnRamp"])
        self.assertIn(r"\underline{Drexel ML}", onramp)
        self.assertIn(r"\underline{Mumm C}", onramp)

    def test_non_byline_consortium_role_does_not_create_false_author(self) -> None:
        citation = format_cv_publication(
            self.by_key["SMaHTNetwork2025SomaticMutationBenchmarking"]
        )
        self.assertIn("Somatic Mosaicism across Human Tissues Network", citation)
        self.assertNotIn(r"\textbf{Boyle", citation)

    def test_contribution_markers_are_preserved(self) -> None:
        citation = format_cv_publication(self.by_key["VanDeynze2025HMMSTR"])
        self.assertIn(r"*\underline{Van Deynze K}", citation)
        self.assertIn(r"*\underline{Mumm C}", citation)
        senior = format_cv_publication(self.by_key["McDonald2021Cas9MobileElements"])
        self.assertIn(r"\textsuperscript{\(\dagger\)}\textbf{Boyle AP}", senior)

    def test_tex_escaping_handles_cv_sensitive_punctuation(self) -> None:
        self.assertEqual(
            tex_escape("A&B_50% #1"),
            r"A\&B\_50\% \#1",
        )

    def test_patent_section_is_generated_and_pi_is_bold(self) -> None:
        self.assertIn(r"\cvsection{Patents}", self.patents_tex)
        self.assertIn(r"\textbf{Boyle A}", self.patents_tex)
        self.assertIn("US9946835B2", self.patents_tex)

    def test_cv_pdf_is_present_and_valid_enough_for_deployment(self) -> None:
        pdf = ROOT / "assets" / "ABoyle_CV.pdf"
        self.assertTrue(pdf.is_file())
        self.assertGreater(pdf.stat().st_size, 50_000)
        self.assertEqual(pdf.read_bytes()[:5], b"%PDF-")

    def test_legacy_perl_and_bibtex_build_dependencies_are_absent(self) -> None:
        legacy_names = {
            "bold_bib4tex.pl",
            "mod_bib_html.pl",
            "bib_to_yaml.py",
            "apb.bib",
            "apbbold.bib",
        }
        present = {
            path.name
            for path in ROOT.rglob("*")
            if path.is_file() and path.name in legacy_names
        }
        self.assertEqual(present, set())
        self.assertEqual(list(ROOT.rglob("*.pl")), [])
        self.assertEqual(list(ROOT.rglob("*.bst")), [])

        cv_source = (ROOT / "cv" / "cv.tex").read_text(encoding="utf-8")
        for obsolete in ("multibib", r"\newcites", r"\bibliography", r"\bibliographystyle"):
            self.assertNotIn(obsolete, cv_source)

        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertNotIn("perl ", makefile.casefold())
        self.assertNotIn("bibtex ", makefile.casefold())
        self.assertNotIn("bibtex2html", makefile.casefold())

    def test_source_date_tracks_authored_inputs_not_generated_commits(self) -> None:
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"SOURCE_DATE_EPOCH": ""}, clear=False
        ):
            root = Path(directory)
            for relative in (
                "cv/cv.tex",
                "cv/patents.bib",
                "bibliography/publications.bib",
                "publication_metadata/Example.yml",
                "_people/Alan.md",
            ):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative, encoding="utf-8")

            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.invalid"],
                cwd=root,
                check=True,
            )
            env = os.environ.copy()
            env.update(
                {
                    "GIT_AUTHOR_DATE": "2026-01-02T03:04:05Z",
                    "GIT_COMMITTER_DATE": "2026-01-02T03:04:05Z",
                }
            )
            subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=env)
            subprocess.run(["git", "commit", "-qm", "source"], cwd=root, check=True, env=env)
            source_epoch = _source_date_epoch(root)

            generated = root / "assets" / "ABoyle_CV.pdf"
            generated.parent.mkdir(parents=True, exist_ok=True)
            generated.write_bytes(b"%PDF-test")
            later_env = os.environ.copy()
            later_env.update(
                {
                    "GIT_AUTHOR_DATE": "2026-02-03T04:05:06Z",
                    "GIT_COMMITTER_DATE": "2026-02-03T04:05:06Z",
                }
            )
            subprocess.run(["git", "add", "-A"], cwd=root, check=True, env=later_env)
            subprocess.run(
                ["git", "commit", "-qm", "generated artifact"],
                cwd=root,
                check=True,
                env=later_env,
            )
            self.assertEqual(_source_date_epoch(root), source_epoch)

    def test_cv_structure_is_streamlined_and_consistent(self) -> None:
        source = (ROOT / "cv" / "cv.tex").read_text(encoding="utf-8")

        expected_sections = [
            r"\cvsection{Academic Appointments}",
            r"\cvsection{Institutional Affiliations}",
            r"\cvsection{Other Professional Experience}",
            r"\cvsection{Research Support}",
            r"\cvsection{Professional Service}",
            r"\cvsection{Teaching and Mentorship}",
        ]
        positions = [source.index(section) for section in expected_sections]
        self.assertEqual(positions, sorted(positions))

        for heading in (
            r"\subsection*{Active: Principal Investigator and Multi-Principal Investigator}",
            r"\subsection*{Active: Co-Investigator and Consultant}",
            r"\subsection*{Completed: Principal Investigator and Multi-Principal Investigator}",
            r"\subsection*{Completed: Co-Investigator and Consultant}",
            r"\subsection*{Institutional and Consortium Leadership}",
            r"\subsection*{Editorial and Program Committee Service}",
            r"\subsection*{Grant Review}",
            r"\subsection*{Manuscript Review}",
            r"\subsection*{Professional Memberships}",
            r"\subsection*{Training Programs}",
        ):
            self.assertIn(heading, source)

        for obsolete in (
            r"\section*{Grant Support}",
            r"\section*{Industry Experience}",
            r"\section*{Training Programs}",
            "This project seeks",
            "The goal of this project",
            "This proposal seeks",
        ):
            self.assertNotIn(obsolete, source)

        self.assertNotRegex(source, r"\b\d{4}--current\b")
        self.assertNotRegex(source, r"\b(\d{4})--\1\b")
        self.assertNotRegex(source, r"\b(?:co-PI|co-I|co-Chair)\b")
        for typo in (
            "Retreat Planing",
            "Trascription Factor",
            "develop any assay",
            "hexonucleotide",
            "Training Progran",
        ):
            self.assertNotIn(typo, source)

        for term_code in ("W19", "F15", "S17"):
            self.assertIn(term_code, source)

    def test_tagged_pdf_build_uses_lualatex_and_three_passes(self) -> None:
        build_source = (ROOT / "scripts" / "build_cv.py").read_text(encoding="utf-8")
        self.assertIn('shutil.which("lualatex")', build_source)
        self.assertIn("for pass_number in range(1, 4)", build_source)
        self.assertNotIn('shutil.which("xelatex")', build_source)
        self.assertIn("lualatex-pass-{pass_number}.log", build_source)

    def test_command_line_check_succeeds(self) -> None:
        result = subprocess.run(
            [sys.executable, "scripts/build_cv.py", "--check", "--strict"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Validated generated CV source", result.stdout)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from pypdf import PdfReader

from site_test_utils import ROOT


class CVPdfFeatureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = (ROOT / "cv" / "cv.tex").read_text(encoding="utf-8")
        cls.pdf_path = ROOT / "assets" / "ABoyle_CV.pdf"
        cls.reader = PdfReader(cls.pdf_path)

    def test_visual_identity_and_running_furniture_are_defined(self) -> None:
        self.assertIn(r"\definecolor{MichiganBlue}{HTML}{00274C}", self.source)
        self.assertIn(r"\color{MichiganBlue}", self.source)
        self.assertIn(r"allcolors=MichiganBlue", self.source)
        self.assertIn(r"\lhead{\small Updated August 2026}", self.source)
        self.assertIn(
            r"\rhead{\small Alan P. Boyle \textbar{} Curriculum Vitae}",
            self.source,
        )
        self.assertIn(
            r"\cfoot{\small Page \thepage{} of \pageref*{LastPage}}",
            self.source,
        )

    def test_major_sections_are_bookmarked(self) -> None:
        expected = [
            "Alan P. Boyle - Curriculum Vitae",
            "Education",
            "Academic Appointments",
            "Institutional Affiliations",
            "Other Professional Experience",
            "Scholarships, Fellowships, and Honors",
            "Research Support",
            "Professional Service",
            "Teaching and Mentorship",
            "Publications",
            "Patents",
        ]

        def flatten(items: list[object]) -> list[str]:
            titles: list[str] = []
            for item in items:
                if isinstance(item, list):
                    titles.extend(flatten(item))
                else:
                    titles.append(getattr(item, "title", str(item)))
            return titles

        self.assertEqual(flatten(self.reader.outline), expected)
        self.assertIn(r"\newcommand{\cvsection}", self.source)
        self.assertIn(r"\addcontentsline{toc}{section}{#1}", self.source)

    def test_pdf_metadata_is_complete(self) -> None:
        metadata = self.reader.metadata
        self.assertEqual(metadata.title, "Alan P. Boyle - Curriculum Vitae")
        self.assertEqual(metadata.author, "Alan P. Boyle")
        self.assertEqual(metadata.subject, "Academic curriculum vitae")
        self.assertIn("genomics", metadata.get("/Keywords", ""))
        self.assertIn("University of Michigan", metadata.get("/Keywords", ""))

    def test_pdf_is_tagged_and_declares_language(self) -> None:
        root = self.reader.trailer["/Root"]
        self.assertTrue(root["/MarkInfo"]["/Marked"])
        self.assertIn("/StructTreeRoot", root)
        self.assertEqual(root["/Lang"], "en-US")
        self.assertTrue(root["/ViewerPreferences"]["/DisplayDocTitle"])
        self.assertIn("pdfstandard=UA-1", self.source)
        self.assertIn("testphase=phase-III", self.source)

    def test_page_labels_include_current_and_total_page_counts(self) -> None:
        page_count = len(self.reader.pages)
        self.assertGreater(page_count, 10)
        for page_number in (1, 4, page_count):
            text = self.reader.pages[page_number - 1].extract_text()
            self.assertIn(f"Page {page_number} of {page_count}", text)
            self.assertIn("Updated August 2026", text)
            self.assertIn("Alan P. Boyle | Curriculum Vitae", text)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

import yaml

from site_test_utils import ROOT


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = ROOT / ".github" / "workflows" / "site.yml"
        cls.text = cls.path.read_text(encoding="utf-8")
        cls.workflow = yaml.load(cls.text, Loader=yaml.BaseLoader)

    def test_workflow_has_push_pull_request_and_manual_triggers(self) -> None:
        triggers = self.workflow["on"]
        self.assertIn("push", triggers)
        self.assertIn("pull_request", triggers)
        self.assertIn("workflow_dispatch", triggers)

    def test_automatic_runs_are_limited_to_the_bibliography_file(self) -> None:
        triggers = self.workflow["on"]
        expected_paths = ["bibliography/publications.bib"]
        self.assertEqual(triggers["push"]["paths"], expected_paths)
        self.assertEqual(triggers["pull_request"]["paths"], expected_paths)

    def test_workflow_regenerates_publications_and_cv(self) -> None:
        self.assertIn("python scripts/build_publications.py --strict", self.text)
        self.assertIn("python scripts/build_cv.py --strict --compile", self.text)
        self.assertIn("python -m unittest discover -s tests -v", self.text)
        for package in ("fonts-liberation2", "texlive-latex-extra", "texlive-xetex"):
            self.assertIn(package, self.text)

    def test_pull_requests_require_text_outputs_but_compile_the_pdf(self) -> None:
        self.assertIn("git status --porcelain -- _papers pub.bib cv/generated", self.text)
        status_line = next(
            line for line in self.text.splitlines() if "git status --porcelain" in line
        )
        self.assertNotIn("ABoyle_CV.pdf", status_line)
        self.assertIn("python scripts/build_cv.py --strict --compile", self.text)

    def test_direct_push_commits_publication_and_cv_outputs(self) -> None:
        self.assertIn(
            "git add --all -- _papers pub.bib cv/generated assets/ABoyle_CV.pdf",
            self.text,
        )
        self.assertIn("github-actions[bot]", self.text)
        self.assertIn("[skip ci]", self.text)

    def test_workflow_builds_and_deploys_pages_with_current_actions(self) -> None:
        for action in (
            "actions/checkout@v7",
            "actions/setup-python@v7",
            "actions/configure-pages@v6",
            "actions/jekyll-build-pages@v1",
            "actions/upload-pages-artifact@v5",
            "actions/deploy-pages@v5",
        ):
            self.assertIn(action, self.text)
        self.assertIn("pages: write", self.text)
        self.assertIn("id-token: write", self.text)
        self.assertIn("environment:", self.text)
        self.assertIn("name: github-pages", self.text)

    def test_deployment_is_skipped_for_pull_requests(self) -> None:
        deploy = self.workflow["jobs"]["deploy"]
        self.assertEqual(deploy["if"], "github.event_name != 'pull_request'")
        self.assertEqual(deploy["needs"], "build")


if __name__ == "__main__":
    unittest.main()

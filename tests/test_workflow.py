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

    def test_workflow_regenerates_and_checks_publications(self) -> None:
        self.assertIn("python scripts/build_publications.py --strict", self.text)
        self.assertIn("python -m unittest discover -s tests -v", self.text)
        self.assertIn("git status --porcelain -- _papers pub.bib", self.text)
        self.assertIn("git add --all -- _papers pub.bib", self.text)

    def test_workflow_builds_and_deploys_pages(self) -> None:
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

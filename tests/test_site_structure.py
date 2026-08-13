from __future__ import annotations

from pathlib import Path
import re
import unittest

import tinycss2

from site_test_utils import ROOT, load_front_matter


DYNAMIC_CSS_CLASSES = {
    "news-article-hero--contain",
    "news-article-hero--cover",
}
REMOVED_LEGACY_PATHS = {
    "_layouts/simple.html",
    "_includes/reference_paper.html",
    "_includes/pub/pub.html",
    "_includes/pub/pub_bib.html",
    "css/academicons.min.css",
    "scripts/migrate_legacy_publications.py",
    "assets/data/publications.json",
    "assets/js/publications.js",
    "boyle_lab.ico",
    "F-Seq/bffBuilder.tgz",
}
REQUIRED_DOCUMENTATION = {
    "README.md",
    "SITE_STRUCTURE.md",
    "PAGES.md",
    "PEOPLE.md",
    "PUBLICATIONS.md",
    "NEWS_POSTS.md",
    "JOBS.md",
    "DEVELOPMENT.md",
    "STYLES_AND_ASSETS.md",
    "CLEANUP.md",
}


class SiteStructureTests(unittest.TestCase):
    def test_all_referenced_layouts_exist(self) -> None:
        referenced: set[str] = set()
        for path in [
            *ROOT.glob("*.html"),
            *(ROOT / "_people").glob("*.md"),
            *(ROOT / "_posts").glob("**/*.md"),
        ]:
            data, _body = load_front_matter(path)
            if data.get("layout"):
                referenced.add(str(data["layout"]))
        missing = [layout for layout in referenced if not (ROOT / "_layouts" / f"{layout}.html").is_file()]
        self.assertEqual(missing, [])

    def test_liquid_control_blocks_are_balanced(self) -> None:
        pairs = {
            "if": "endif",
            "unless": "endunless",
            "for": "endfor",
            "capture": "endcapture",
            "comment": "endcomment",
        }
        closers = {closer: opener for opener, closer in pairs.items()}
        tag_pattern = re.compile(r"{%-?\s*([A-Za-z_]+)")
        for path in [
            *ROOT.glob("*.html"),
            *(ROOT / "_layouts").glob("*.html"),
            *(ROOT / "_includes").glob("*.html"),
        ]:
            stack: list[str] = []
            for tag in tag_pattern.findall(path.read_text(encoding="utf-8")):
                if tag in pairs:
                    stack.append(tag)
                elif tag in closers:
                    self.assertTrue(stack, f"{path.relative_to(ROOT)}: unexpected {tag}")
                    opener = stack.pop()
                    self.assertEqual(opener, closers[tag], f"{path.relative_to(ROOT)}: {opener}/{tag}")
            self.assertEqual(stack, [], f"{path.relative_to(ROOT)}: unclosed {stack}")

    def test_all_liquid_includes_exist(self) -> None:
        pattern = re.compile(r"{%\s*include\s+([^\s%]+)")
        missing: list[str] = []
        for path in [*ROOT.glob("*.html"), *(ROOT / "_layouts").glob("*.html"), *(ROOT / "_includes").glob("*.html")]:
            for target in pattern.findall(path.read_text(encoding="utf-8")):
                target = target.strip("'\"")
                if "{{" in target:
                    continue
                if not (ROOT / "_includes" / target).is_file():
                    missing.append(f"{path.relative_to(ROOT)} -> {target}")
        self.assertEqual(missing, [])

    def test_known_legacy_files_are_absent(self) -> None:
        self.assertEqual(
            [path for path in sorted(REMOVED_LEGACY_PATHS) if (ROOT / path).exists()],
            [],
        )

    def test_header_uses_only_current_dependencies(self) -> None:
        header = (ROOT / "_includes" / "header.html").read_text(encoding="utf-8")
        self.assertIn('<meta name="viewport"', header)
        self.assertIn('/assets/js/site-navigation.js', header)
        self.assertNotIn("jquery", header.casefold())
        self.assertNotIn("google-analytics.com/ga.js", header)
        for local in (
            "assets/boyle_lab.ico",
            "css/main_style.css",
            "css/mobile_navigation.css",
            "css/academicons.css",
            "assets/js/site-navigation.js",
        ):
            self.assertTrue((ROOT / local).is_file(), local)

    def test_css_parses_and_every_static_class_is_referenced(self) -> None:
        css_text = "\n".join(path.read_text(encoding="utf-8") for path in sorted((ROOT / "css").glob("*.css")))
        parsed_rules = tinycss2.parse_stylesheet(css_text, skip_comments=True, skip_whitespace=True)
        errors = [token for token in parsed_rules if token.type == "error"]
        self.assertEqual(errors, [])

        selectors = [
            tinycss2.serialize(rule.prelude).strip()
            for rule in parsed_rules
            if rule.type == "qualified-rule"
        ]
        self.assertEqual(len(selectors), len(set(selectors)), "duplicate top-level CSS selector blocks")

        classes = set(re.findall(r"(?<![\w-])\.([A-Za-z_][\w-]*)", css_text))
        content = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in ROOT.rglob("*")
            if path.is_file()
            and path.suffix.lower() in {".html", ".md", ".js"}
            and "css" not in path.parts
            and "_site" not in path.parts
        )
        unused = {
            css_class
            for css_class in classes
            if css_class not in DYNAMIC_CSS_CLASSES
            and not re.search(rf"(?<![\w-]){re.escape(css_class)}(?![\w-])", content)
        }
        self.assertEqual(unused, set())

    def test_primary_navigation_targets_exist(self) -> None:
        nav = (ROOT / "_includes" / "nav.html").read_text(encoding="utf-8")
        for target in ("/", "/research/", "/people/", "/publications/", "/software/", "/news/", "/jobs/", "/contact/"):
            self.assertIn(f'href="{target}"', nav)
        for source in ("index.html", "research.html", "people.html", "publications.html", "software.html", "news/index.html", "jobs.html", "contact.html"):
            self.assertTrue((ROOT / source).is_file(), source)

    def test_build_and_documentation_files_exist(self) -> None:
        for path in REQUIRED_DOCUMENTATION | {
            "Gemfile",
            "Makefile",
            "requirements-publications.txt",
            "scripts/build_site.sh",
            ".github/workflows/site.yml",
        }:
            self.assertTrue((ROOT / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()

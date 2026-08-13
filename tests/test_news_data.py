from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import unittest

from site_test_utils import ROOT, load_front_matter, local_asset_path


class NewsDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.people_ids = {
            load_front_matter(path)[0]["umid"]
            for path in (ROOT / "_people").glob("*.md")
        }
        cls.paper_keys = {
            load_front_matter(path)[0]["bibkey"]
            for path in (ROOT / "_papers").glob("*.yml")
        }
        cls.posts = [
            (path, *load_front_matter(path))
            for path in sorted((ROOT / "_posts").glob("**/*.md"))
        ]

    def test_all_news_posts_have_standard_front_matter(self) -> None:
        self.assertEqual(len(self.posts), 170)
        for path, data, _body in self.posts:
            self.assertEqual(data.get("layout"), "post", path.name)
            self.assertIsInstance(data.get("published"), bool, path.name)
            self.assertTrue(data.get("title"), path.name)
            self.assertIsInstance(data.get("date"), (str, date, datetime), path.name)
            self.assertIsInstance(data.get("categories"), list, path.name)
            self.assertTrue(data["categories"], path.name)
            self.assertTrue(data.get("teaser"), path.name)

    def test_teaser_and_optional_image_assets_exist(self) -> None:
        for path, data, _body in self.posts:
            teaser = local_asset_path(data.get("teaser"), default_root="assets/news_graphics")
            if teaser:
                self.assertTrue(teaser.is_file(), f"{path.name}: {teaser.relative_to(ROOT)}")

            hero = data.get("hero_image") or data.get("hero-image")
            hero_path = local_asset_path(hero, default_root="assets/news_graphics")
            if hero_path:
                self.assertTrue(hero_path.is_file(), f"{path.name}: {hero_path.relative_to(ROOT)}")

            for item in data.get("gallery") or []:
                src = item.get("src") if isinstance(item, dict) else item
                gallery_path = local_asset_path(src, default_root="assets/news_graphics")
                if gallery_path:
                    self.assertTrue(gallery_path.is_file(), f"{path.name}: {gallery_path.relative_to(ROOT)}")

    def test_people_and_publication_relationships_resolve(self) -> None:
        for path, data, _body in self.posts:
            people = data.get("people") or []
            self.assertIsInstance(people, list, path.name)
            self.assertEqual(set(people) - self.people_ids, set(), path.name)
            related = data.get("related-publication") or data.get("related_publication")
            if related:
                self.assertIn(related, self.paper_keys, path.name)

    def test_grant_metadata_is_structured(self) -> None:
        for path, data, _body in self.posts:
            award = data.get("award")
            if not award:
                continue
            self.assertIsInstance(award, dict, path.name)
            for key in ("agency", "mechanism", "project"):
                self.assertTrue(award.get(key), f"{path.name}: award.{key}")
            if "collaborators" in award:
                self.assertIsInstance(award["collaborators"], list, path.name)

    def test_post_layout_uses_structured_news_metadata(self) -> None:
        template = (ROOT / "_layouts" / "post.html").read_text(encoding="utf-8")
        for expression in (
            "page.award",
            "page.people",
            "related-publication",
            "page.gallery",
            "page.hero_image",
        ):
            self.assertIn(expression, template)
        self.assertIn("page.previous", template)
        self.assertIn("page.next", template)


if __name__ == "__main__":
    unittest.main()

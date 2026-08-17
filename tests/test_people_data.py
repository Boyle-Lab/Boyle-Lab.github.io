from __future__ import annotations

from datetime import date
from pathlib import Path
import re
import unittest

from site_test_utils import ROOT, load_front_matter


ALLOWED_STATUSES = {"current", "phd_alumni", "alumni", "rotation"}
LEGACY_ROLE_FIELDS = {
    "ms_start",
    "ms_end",
    "phd_start",
    "phd_end",
    "pd_start",
    "pd_end",
    "publication_names",
    "author_aliases",
}


class PeopleDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.people = []
        for path in sorted((ROOT / "_people").glob("*.md")):
            data, body = load_front_matter(path)
            cls.people.append((path, data, body))

    def test_all_people_have_unique_umids_and_list_statuses(self) -> None:
        self.assertEqual(len(self.people), 69)
        seen: dict[str, Path] = {}
        for path, data, _body in self.people:
            umid = str(data.get("umid") or "").strip()
            self.assertTrue(umid, path.name)
            self.assertNotIn(umid, seen, f"{path.name} and {seen.get(umid)}")
            seen[umid] = path

            statuses = data.get("status")
            self.assertIsInstance(statuses, list, path.name)
            self.assertTrue(statuses, path.name)
            self.assertEqual(len(statuses), len(set(statuses)), path.name)
            self.assertEqual(set(statuses) - ALLOWED_STATUSES, set(), path.name)

    def test_people_use_one_role_history_model(self) -> None:
        for path, data, _body in self.people:
            self.assertEqual(set(data).intersection(LEGACY_ROLE_FIELDS), set(), path.name)
            roles = data.get("prior_lab_roles") or []
            self.assertIsInstance(roles, list, path.name)
            for role in roles:
                self.assertIsInstance(role, dict, path.name)
                self.assertTrue(role.get("position"), path.name)
                self.assertTrue(
                    role.get("period") or role.get("start") or role.get("end"),
                    f"{path.name}: role has no dates or period",
                )
                for key in ("start", "end"):
                    value = role.get(key)
                    if value is not None:
                        self.assertIsInstance(value, date, f"{path.name}: quote {key} as YAML date")

    def test_top_level_dates_are_yaml_dates_and_ordered(self) -> None:
        for path, data, _body in self.people:
            dates = data.get("dates") or {}
            self.assertIsInstance(dates, dict, path.name)
            self.assertIsInstance(dates.get("start"), date, path.name)
            if dates.get("end") is not None:
                self.assertIsInstance(dates["end"], date, path.name)
                self.assertLessEqual(dates["start"], dates["end"], path.name)

    def test_phd_alumni_have_one_completed_phd_role(self) -> None:
        for path, data, _body in self.people:
            if "phd_alumni" not in data["status"] or not data.get("publish", True):
                continue
            roles = [
                role
                for role in data.get("prior_lab_roles") or []
                if "Ph.D. student" in str(role.get("position") or "")
            ]
            self.assertEqual(len(roles), 1, path.name)
            self.assertIsInstance(roles[0].get("end"), date, path.name)

    def test_profile_assets_and_current_positions_are_valid(self) -> None:
        for path, data, _body in self.people:
            picture = data.get("picture")
            if picture:
                self.assertTrue((ROOT / "assets" / "people" / picture).is_file(), path.name)
            cv = data.get("CV")
            if cv:
                self.assertTrue((ROOT / "assets" / cv).is_file(), path.name)

            current_position = data.get("current_position")
            if current_position:
                self.assertIsInstance(current_position, dict, path.name)
                self.assertTrue(current_position.get("title"), path.name)
                if current_position.get("as_of") is not None:
                    self.assertIsInstance(current_position["as_of"], date, path.name)

    def test_people_page_sorts_phd_alumni_by_prior_role_end_date(self) -> None:
        template = (ROOT / "people.html").read_text(encoding="utf-8")
        self.assertIn("person.prior_lab_roles", template)
        self.assertIn("role.position contains 'Ph.D. student'", template)
        self.assertIn("role.end", template)
        self.assertIn('split: "||" | sort | reverse', template)
        self.assertNotIn('sort: "dates.phd_end"', template)

    def test_people_page_counts_published_noncurrent_profiles_as_alumni(self) -> None:
        template = (ROOT / "people.html").read_text(encoding="utf-8")
        count_logic = re.compile(
            r"{% assign current_count = 0 %}.*?"
            r"{% assign alumni_count = 0 %}.*?"
            r"{% for person in site.people %}.*?"
            r"{% if person.publish %}.*?"
            r"{% if person.status contains 'current' %}.*?"
            r"{% assign current_count = current_count \| plus: 1 %}.*?"
            r"{% else %}.*?"
            r"{% assign alumni_count = alumni_count \| plus: 1 %}.*?"
            r"{% endif %}.*?{% endif %}.*?{% endfor %}",
            re.DOTALL,
        )
        self.assertRegex(template, count_logic)
        self.assertIn("{{ current_count }}", template)
        self.assertIn("{{ alumni_count }}", template)
        self.assertIn("current members", template)
        self.assertIn("lab alumni", template)

        css = (ROOT / "css" / "main_style.css").read_text(encoding="utf-8")
        primary_size = re.search(
            r"\.site-page-stat strong\s*{[^}]*font-size:\s*([0-9.]+)px;",
            css,
            re.DOTALL,
        )
        alumni_size = re.search(
            r"\.site-page-stat--secondary strong\s*{[^}]*font-size:\s*([0-9.]+)px;",
            css,
            re.DOTALL,
        )
        self.assertIsNotNone(primary_size)
        self.assertIsNotNone(alumni_size)
        self.assertLess(float(alumni_size.group(1)), float(primary_size.group(1)))

        secondary_card = re.search(
            r"\.site-page-stat--secondary\s*{([^}]*)}",
            css,
            re.DOTALL,
        )
        secondary_value = re.search(
            r"\.site-page-stat--secondary strong\s*{([^}]*)}",
            css,
            re.DOTALL,
        )
        self.assertIsNotNone(secondary_card)
        self.assertIsNotNone(secondary_value)
        self.assertRegex(secondary_card.group(1), r"padding:\s*14px;")
        self.assertRegex(
            secondary_value.group(1),
            r"padding-top:\s*calc\(28px\s*-\s*20px\);",
        )

    def test_member_layout_displays_current_position_and_prior_roles(self) -> None:
        template = (ROOT / "_layouts" / "member.html").read_text(encoding="utf-8")
        self.assertIn("page.prior_lab_roles", template)
        self.assertIn("page.current_position", template)
        self.assertIn("page.status contains", template)
        for field in LEGACY_ROLE_FIELDS:
            self.assertNotIn(f"page.{field}", template)


if __name__ == "__main__":
    unittest.main()

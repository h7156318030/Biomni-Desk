import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import community, github_skills, skill_import
from biomni_ui import skills as skill_files


def isolate(case):
    """No network and no writes to the app's own sources file: a GitHub-link import records its commit in a temporary file."""
    d = tempfile.TemporaryDirectory()
    case.addCleanup(d.cleanup)
    for p in (mock.patch.object(github_skills, "SOURCES", Path(d.name) / "skill_sources.json"),
              mock.patch.object(github_skills, "latest_commit", return_value="abc123")):
        p.start()
        case.addCleanup(p.stop)

AEON = """---
name: aeon
description: Time series machine learning tasks for classification and forecasting.
license: BSD-3-Clause license
metadata:
  version: "1.3"
---

## Use

Run the tasks with scikit-learn compatible APIs.
"""


class Catalog(unittest.TestCase):
    def test_every_entry_says_where_it_comes_from_and_how_it_was_checked(self):
        items = community.entries()
        self.assertGreaterEqual(len(items), 5)
        ids = [e["id"] for e in items]
        self.assertEqual(len(ids), len(set(ids)), "ids must be unique")
        for e in items:
            with self.subTest(entry=e["id"]):
                self.assertIn(e["kind"], community.KINDS)
                self.assertRegex(e["repo"], r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
                self.assertTrue(e["url"].startswith("https://github.com/" + e["repo"]))
                self.assertTrue(e["license"])
                self.assertRegex(e["last_changed"], r"^\d{4}-\d{2}-\d{2}$")
                self.assertTrue(e["note"])
                self.assertIsInstance(e["archived"], bool)

    def test_skill_collections_record_how_many_skill_files_were_found(self):
        for e in community.entries():
            if e["kind"] == "skills":
                with self.subTest(entry=e["id"]):
                    self.assertIsInstance(e["skill_count"], int)
                    self.assertGreater(e["skill_count"], 0)
                    self.assertEqual(e["branch"], "main")

    def test_search_matches_every_word_across_name_description_and_keywords(self):
        self.assertIn("gptomics-bioskills", [e["id"] for e in community.search("single-cell")])
        self.assertEqual([e["id"] for e in community.search("single-cell mcp")], [])
        self.assertTrue(all(e["kind"] == "tools" for e in community.search("", "tools")))
        self.assertEqual(len(community.search("")), len(community.entries()))

    def test_blob_links_point_at_the_file_on_github(self):
        e = community.entry("kdense-scientific-agent-skills")
        self.assertEqual(community.blob_url(e, "skills/aeon/SKILL.md"),
                         "https://github.com/K-Dense-AI/scientific-agent-skills/blob/main/skills/aeon/SKILL.md")


def fake_tree(paths, truncated=False):
    def fetch(url, token):
        return {"truncated": truncated, "tree": [{"path": p, "type": "blob"} for p in paths] + [{"path": "skills/x", "type": "tree"}]}
    return fetch


class Listing(unittest.TestCase):
    def setUp(self):
        community._tree_cache.clear()
        self.entry = {"id": "t", "kind": "skills", "repo": "o/r", "branch": "main", "skill_prefix": "skills/", "exclude_prefixes": ["legacy/"]}

    def test_only_skill_files_under_the_prefix_are_listed(self):
        paths = ["skills/aeon/SKILL.md", "skills/aeon/README.md", "other/x/SKILL.md", "legacy/old/SKILL.md", "skills/bio/SKILL.md"]
        files = community.skill_files(self.entry, None, fake_tree(paths))
        self.assertEqual([f["path"] for f in files], ["skills/aeon/SKILL.md", "skills/bio/SKILL.md"])
        self.assertEqual([f["folder"] for f in files], ["aeon", "bio"])

    def test_a_truncated_tree_is_refused_with_a_clear_message(self):
        with self.assertRaises(ValueError):
            community.skill_files(self.entry, None, fake_tree(["skills/a/SKILL.md"], truncated=True))

    def test_tools_and_lists_have_no_skill_listing(self):
        with self.assertRaises(ValueError):
            community.skill_files({"id": "x", "kind": "tools", "repo": "o/r"}, None, fake_tree([]))


class Install(unittest.TestCase):
    def setUp(self):
        community._tree_cache.clear()
        isolate(self)
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = skill_files.SkillStore(Path(self._tmp.name) / "skills", Path(self._tmp.name) / "state.json")
        self.entry = {"id": "t", "kind": "skills", "repo": "o/r", "branch": "main", "skill_prefix": "", "exclude_prefixes": []}
        self.listed = ["skills/aeon/SKILL.md"]

    def test_an_unlisted_path_is_refused_without_a_download(self):
        called = []
        results = community.install(self.entry, ["https://example.org/evil.md"], self.store, None,
                                    lambda *a, **k: called.append(a), fetch=fake_tree(self.listed))
        self.assertEqual(called, [])
        self.assertFalse(results[0]["ok"])

    def test_a_listed_skill_is_imported_through_the_same_import_as_a_link(self):
        results = community.install(self.entry, self.listed, self.store, None,
                                    lambda store, url, token=None: skill_import.import_skill(store, url, fetcher=lambda raw: AEON),
                                    fetch=fake_tree(self.listed))
        self.assertTrue(results[0]["ok"], results)
        self.assertEqual(results[0]["id"], "aeon")
        self.assertIsNotNone(self.store.get("aeon"))

    def test_a_skill_already_in_the_library_is_reported_not_overwritten(self):
        skill_import.import_skill(self.store, "https://github.com/o/r/blob/main/skills/aeon/SKILL.md", fetcher=lambda raw: AEON)
        results = community.install(self.entry, self.listed, self.store, None,
                                    lambda store, url, token=None: skill_import.import_skill(store, url, fetcher=lambda raw: AEON),
                                    fetch=fake_tree(self.listed))
        self.assertFalse(results[0]["ok"])
        self.assertIn("already exists", results[0]["error"])

    def test_the_number_of_skills_per_request_is_capped(self):
        with self.assertRaises(ValueError):
            community.install(self.entry, [f"p{i}" for i in range(community.MAX_INSTALL + 1)], self.store, None, lambda *a, **k: {}, fetch=fake_tree([]))

    def test_nothing_chosen_is_refused(self):
        with self.assertRaises(ValueError):
            community.install(self.entry, [], self.store, None, lambda *a, **k: {}, fetch=fake_tree([]))


class CommunityName(unittest.TestCase):
    def test_a_community_skill_uses_its_name_as_the_title(self):
        class Case(unittest.TestCase):
            def runTest(self):
                pass

        case = Case()
        isolate(case)
        with tempfile.TemporaryDirectory() as d:
            store = skill_files.SkillStore(Path(d) / "skills", Path(d) / "state.json")
            skill = skill_import.import_skill(store, "https://github.com/o/r/blob/main/skills/aeon/SKILL.md", fetcher=lambda raw: AEON)
        case.doCleanups()
        self.assertEqual(skill["title"], "aeon")
        self.assertIn("Time series", skill["description"])


if __name__ == "__main__":
    unittest.main()

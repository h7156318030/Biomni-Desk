import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import github_skills, skills


class Isolated(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        for name, value in (("CREDENTIALS", root / "credentials.json"), ("SOURCES", root / "skill_sources.json")):
            p = mock.patch.object(github_skills, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.store = skills.SkillStore(root / "skills", root / "state.json")


class Token(Isolated):
    def test_token_is_stored_and_cleared(self):
        self.assertIsNone(github_skills.get_token())
        self.assertTrue(github_skills.set_token("ghp_test"))
        self.assertEqual(github_skills.get_token(), "ghp_test")
        self.assertFalse(github_skills.set_token(""))
        self.assertIsNone(github_skills.get_token())

    def test_the_token_file_is_plain_json_only_in_ui_data(self):
        github_skills.set_token("ghp_x")
        self.assertEqual(json.loads(github_skills.CREDENTIALS.read_text(encoding="utf-8")), {"github_token": "ghp_x"})


class Parsing(unittest.TestCase):
    def test_a_file_page_is_split_into_owner_repo_ref_and_path(self):
        self.assertEqual(github_skills.parse_blob("https://github.com/o/r/blob/main/skills/kinase.md"), ("o", "r", "main", "skills/kinase.md"))
        self.assertIsNone(github_skills.parse_blob("https://example.org/x.md"))
        self.assertEqual(github_skills.raw_url("o", "r", "main", "a.md"), "https://raw.githubusercontent.com/o/r/main/a.md")


class Updates(Isolated):
    def skill_text(self, body):
        return f"---\ntitle: Kinase panel\ndescription: d\n---\n{body}"

    def import_one(self, commit="c1", body="Step one."):
        url = "https://github.com/o/r/blob/main/kinase.md"
        from biomni_ui import skill_import

        skill_import.import_skill(self.store, url, fetcher=lambda raw: self.skill_text(body), commit_lookup=lambda *a: commit)
        return url

    def test_no_newer_commit_means_nothing_to_check(self):
        self.import_one(commit="c1")
        rows = github_skills.check_updates(self.store, latest=lambda *a: "c1", fetch=lambda *a: self.skill_text("Step one."))
        self.assertEqual(rows, [])

    def test_a_newer_commit_with_changed_content_is_listed_as_changed(self):
        self.import_one(commit="c1", body="Step one.")
        rows = github_skills.check_updates(self.store, latest=lambda *a: "c2", fetch=lambda *a: self.skill_text("Step one, revised."))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["skill_id"], "kinase-panel")
        self.assertTrue(rows[0]["changed"])
        self.assertEqual(rows[0]["latest_commit"], "c2")

    def test_a_newer_commit_with_the_same_content_is_not_a_change(self):
        self.import_one(commit="c1", body="Step one.")
        rows = github_skills.check_updates(self.store, latest=lambda *a: "c2", fetch=lambda *a: self.skill_text("Step one."))
        self.assertFalse(rows[0]["changed"])

    def test_apply_replaces_the_skill_and_records_the_new_commit(self):
        self.import_one(commit="c1", body="Step one.")
        done = github_skills.apply_updates(self.store, ["kinase-panel"], latest=lambda *a: "c2", fetch=lambda *a: self.skill_text("Step one, revised."))
        self.assertEqual(done, ["kinase-panel"])
        self.assertIn("Step one, revised.", self.store.get("kinase-panel")["body"])
        self.assertEqual(github_skills.sources()["kinase-panel"]["commit"], "c2")

    def test_an_update_without_title_is_refused_and_nothing_changes(self):
        self.import_one(commit="c1", body="Step one.")
        with self.assertRaises(ValueError):
            github_skills.apply_updates(self.store, ["kinase-panel"], latest=lambda *a: "c2", fetch=lambda *a: "no front matter here")
        self.assertIn("Step one.", self.store.get("kinase-panel")["body"])

    def test_skills_without_a_recorded_source_are_ignored(self):
        self.assertEqual(github_skills.check_updates(self.store, latest=lambda *a: "x", fetch=lambda *a: ""), [])


if __name__ == "__main__":
    unittest.main()

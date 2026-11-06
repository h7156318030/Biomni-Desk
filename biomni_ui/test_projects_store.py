import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import notes
from biomni_ui.store import Store


class Projects(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = Store(Path(self._tmp.name) / "t.db")
        self.addCleanup(self.store.close)
        self.proj = self.store.create_project("Immunology")
        self.other = self.store.create_project("Genomics")
        self.store.create_task("t1", "c1", "TP53 mutation spectrum")
        self.store.set_project("c1", self.proj["id"])
        self.store.add_event("t1", {"seq": 1, "type": "answer", "text": "R248Q is common in cancers"})
        self.store.create_task("t2", "c2", "BRCA1 function")
        self.store.set_project("c2", self.other["id"])
        self.store.add_event("t2", {"seq": 1, "type": "answer", "text": "E3 ligase activity"})
        self.store._run("INSERT INTO published VALUES (?,?,?,?)", ("pub1", "Immuno page", 1.0, "t1"))


class Search(Projects):
    def test_finds_titles_questions_and_answer_text(self):
        self.assertEqual([r["id"] for r in self.store.search("TP53")], ["c1"])  # question text
        self.assertEqual([r["id"] for r in self.store.search("R248Q")], ["c1"])  # answer text
        self.assertEqual([r["id"] for r in self.store.search("E3 ligase")], ["c2"])

    def test_snippets_are_readable_text_not_json(self):
        hit = self.store.search("R248Q")[0]
        self.assertIn("R248Q", hit["snippet"])
        self.assertNotIn('"type"', hit["snippet"])

    def test_project_filter(self):
        self.assertEqual(self.store.search("function", self.other["id"])[0]["id"], "c2")
        self.assertEqual(self.store.search("function", self.proj["id"]), [])

    def test_wildcards_are_literal(self):
        self.assertEqual(self.store.search("%"), [])  # not "match everything"
        self.assertEqual(self.store.search("_"), [])

    def test_empty_query_finds_nothing(self):
        self.assertEqual(self.store.search("   "), [])


class Summary(Projects):
    def test_counts_sessions_tasks_and_published_pages(self):
        s = self.store.project_summary(self.proj["id"])
        self.assertEqual(s, {"sessions": 1, "tasks": 1, "published": 1})
        self.assertEqual(self.store.project_summary(self.other["id"]), {"sessions": 1, "tasks": 1, "published": 0})


class Cascade(Projects):
    def test_deletes_only_that_projects_records(self):
        removed = self.store.delete_project_cascade(self.proj["id"])
        self.assertEqual(removed, ["c1"])
        self.assertIsNone(self.store.get_conversation("c1"))
        self.assertIsNotNone(self.store.get_conversation("c2"))  # the other project is untouched
        self.assertEqual(self.store.search("R248Q"), [])  # its events are gone
        self.assertEqual(self.store._run("SELECT COUNT(*) AS n FROM published WHERE task_id='t1'")[0]["n"], 0)
        self.assertEqual([p["id"] for p in self.store.list_projects() if not p["default"]], [self.other["id"]])

    def test_the_default_project_cannot_be_cascaded(self):
        self.store.create_task("t9", "c9", "in quick task")
        self.assertEqual(self.store.delete_project_cascade("quick"), [])
        self.assertIsNotNone(self.store.get_conversation("c9"))

    def test_notes_of_one_project_are_removed_with_it(self):
        with tempfile.TemporaryDirectory() as d:
            saved = notes.STORE
            notes.STORE = Path(d) / "memory_notes.json"
            self.addCleanup(setattr, notes, "STORE", saved)
            notes.add("for immunology", self.proj["id"])
            notes.add("for everyone")
            self.assertEqual(notes.delete_project(self.proj["id"]), 1)
            self.assertEqual([i["text"] for i in notes.list_items()], ["for everyone"])


class GeneratedAndMemory(Projects):
    def test_generated_files_come_from_the_project_sessions_once_per_path(self):
        self.store.add_event("t1", {"seq": 2, "type": "observation", "text": "saved",
                                    "artifacts": [{"name": "table.csv", "path": "/w/table.csv", "kind": "table", "size": 9}]})
        self.store.add_event("t1", {"seq": 3, "type": "observation", "text": "saved again",
                                    "artifacts": [{"name": "table.csv", "path": "/w/table.csv", "kind": "table", "size": 12}]})
        files = self.store.generated_files(self.proj["id"])
        self.assertEqual([f["name"] for f in files], ["table.csv"])
        self.assertEqual(files[0]["session_title"], self.store.get_conversation("c1")["title"])
        self.assertEqual(self.store.generated_files(self.other["id"]), [])  # other project's files stay out

    def test_project_memory_switch_defaults_on_and_can_be_turned_off(self):
        from biomni_ui import prefs

        self.assertTrue(self.store.get_project_settings(self.proj["id"])["memory_on"])
        self.store.set_project_settings(self.proj["id"], prefs.clean_project_settings({"memory_on": False}))
        self.assertFalse(self.store.get_project_settings(self.proj["id"])["memory_on"])

    def test_notes_keep_their_category_and_source(self):
        with tempfile.TemporaryDirectory() as d:
            saved = notes.STORE
            notes.STORE = Path(d) / "memory_notes.json"
            self.addCleanup(setattr, notes, "STORE", saved)
            notes.add("Use hg38", self.proj["id"], category="Genomics")
            notes.propose("Prefer PMIDs", self.proj["id"], category="Writing")
            items = {i["text"]: i for i in notes.list_items()}
            self.assertEqual(items["Use hg38"]["category"], "Genomics")
            self.assertEqual(items["Use hg38"]["source"], "you")
            self.assertEqual(items["Prefer PMIDs"]["source"], "agent")
            self.assertEqual(notes.block(self.proj["id"], enabled=False), "")  # memory switched off: nothing is used
            notes.approve(items["Prefer PMIDs"]["id"])
            self.assertIn("Prefer PMIDs", notes.block(self.proj["id"]))


if __name__ == "__main__":
    unittest.main()

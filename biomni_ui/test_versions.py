import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import annotations, versions


class Versions(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.conv = Path(self._tmp.name) / "conv"
        self.conv.mkdir()
        self.f = self.conv / "result.csv"

    def write(self, text):
        self.f.write_text(text, encoding="utf-8")

    def test_first_save_is_version_one_and_unchanged_content_adds_nothing(self):
        self.write("a,b\n1,2\n")
        v1 = versions.record(self.conv, self.f, "t1")
        self.assertEqual(v1["version"], 1)
        self.assertIsNone(versions.record(self.conv, self.f, "t2"))  # same bytes: no new version
        self.assertEqual(len(versions.versions_of(self.conv, "result.csv")), 1)

    def test_changed_content_is_a_new_version_newest_first(self):
        self.write("one")
        versions.record(self.conv, self.f, "t1")
        self.write("two")
        v2 = versions.record(self.conv, self.f, "t2")
        self.assertEqual(v2["version"], 2)
        rows = versions.versions_of(self.conv, "result.csv")
        self.assertEqual([r["version"] for r in rows], [2, 1])
        self.assertEqual([r["task_id"] for r in rows], ["t2", "t1"])

    def test_identical_content_is_stored_once(self):
        self.write("same")
        versions.record(self.conv, self.f, "t1")
        self.write("other")
        versions.record(self.conv, self.f, "t2")
        self.write("same")
        versions.record(self.conv, self.f, "t3")  # back to an earlier content: a version, but no second blob
        blobs = list((self.conv / "execution_trace" / "blobs").iterdir())
        self.assertEqual(len(blobs), 2)

    def test_restore_copies_an_old_version_back_as_a_new_one(self):
        self.write("first")
        versions.record(self.conv, self.f, "t1")
        self.write("second")
        versions.record(self.conv, self.f, "t2")
        restored = versions.restore(self.conv, "result.csv", 1)
        self.assertEqual(self.f.read_text(encoding="utf-8"), "first")
        self.assertEqual(restored["version"], 3)
        self.assertIn("restored from version 1", restored["reason"])
        with self.assertRaises(LookupError):
            versions.restore(self.conv, "result.csv", 9)

    def test_files_outside_the_session_folder_are_not_versioned(self):
        outside = Path(self._tmp.name) / "elsewhere.csv"
        outside.write_text("x", encoding="utf-8")
        self.assertIsNone(versions.record(self.conv, outside, "t1"))

    def test_large_files_are_not_kept(self):
        self.write("0123456789")
        with mock.patch.object(versions, "MAX_VERSIONED_BYTES", 5):
            self.assertIsNone(versions.record(self.conv, self.f, "t1"))

    def test_blob_lookup_rejects_anything_but_a_sha256(self):
        self.write("x")
        versions.record(self.conv, self.f, "t1")
        sha = versions.versions_of(self.conv, "result.csv")[0]["sha256"]
        self.assertIsNotNone(versions.blob_path(self.conv, sha))
        self.assertIsNone(versions.blob_path(self.conv, "../../secret"))
        self.assertIsNone(versions.blob_path(self.conv, "z" * 64))

    def test_all_files_lists_latest_and_count(self):
        self.write("a")
        versions.record(self.conv, self.f, "t1")
        self.write("b")
        versions.record(self.conv, self.f, "t2")
        row = versions.all_files(self.conv)["result.csv"]
        self.assertEqual(row["count"], 2)
        self.assertEqual(row["latest"]["version"], 2)


class Provenance(Versions):
    def test_provenance_gathers_the_task_its_code_its_log_and_model(self):
        self.write("data")
        versions.record(self.conv, self.f, "task-x")
        task = {"id": "task-x", "prompt": "make the table"}
        events = [
            {"type": "llm", "model": "gpt-x", "effort": "high", "ts": 1.0},
            {"type": "code", "language": "python", "code": "print('table')", "ts": 2.0},
            {"type": "answer", "text": "Here is the table.", "ts": 3.0},
            {"type": "review", "text": "Looks right.", "ts": 4.0},
        ]
        receipts = [{"tool": "python", "time": "2026-11-06 10:00:00", "summary": "ok", "result_sha256": "ab", "failed": False}]
        p = versions.provenance(self.conv, "result.csv", 1, task, events, receipts)
        self.assertEqual(p["task"]["id"], "task-x")
        self.assertEqual(p["messages"]["question"], "make the table")
        self.assertEqual(p["messages"]["answer"], "Here is the table.")
        self.assertEqual(p["code"][0]["code"], "print('table')")
        self.assertEqual(p["execution_log"][0]["tool"], "python")
        self.assertEqual(p["environment"]["model"], "gpt-x")
        self.assertEqual(p["review"], "Looks right.")

    def test_missing_version_is_an_error(self):
        self.write("data")
        versions.record(self.conv, self.f, "task-x")
        with self.assertRaises(LookupError):
            versions.provenance(self.conv, "result.csv", 7, None, [], [])


class Annotations(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.conv = Path(self._tmp.name)

    def test_add_list_delete(self):
        a = annotations.add(self.conv, "plot.png", "axis label is cut off", quote="Figure 2")
        self.assertEqual(annotations.list_items(self.conv)[0]["id"], a["id"])
        self.assertTrue(annotations.delete(self.conv, a["id"]))
        self.assertFalse(annotations.delete(self.conv, a["id"]))

    def test_pending_comments_are_sent_once_with_their_task(self):
        a = annotations.add(self.conv, "report.md", "cite the 2024 review")
        pending = annotations.take_pending(self.conv)
        self.assertEqual([x["id"] for x in pending], [a["id"]])
        annotations.mark_sent(self.conv, [a["id"]], "task-9")
        self.assertEqual(annotations.take_pending(self.conv), [])
        self.assertEqual(annotations.list_items(self.conv)[0]["sent_in_task"], "task-9")

    def test_prompt_text_names_the_file_and_the_passage(self):
        a = annotations.add(self.conv, "report.md", "cite the 2024 review", quote="the main finding")
        text = annotations.as_prompt_text([a])
        self.assertIn("report.md", text)
        self.assertIn("the main finding", text)
        self.assertIn("cite the 2024 review", text)
        self.assertEqual(annotations.as_prompt_text([]), "")

    def test_a_comment_needs_text_and_a_file(self):
        with self.assertRaises(ValueError):
            annotations.add(self.conv, "x.md", "   ")
        with self.assertRaises(ValueError):
            annotations.add(self.conv, "", "something")


if __name__ == "__main__":
    unittest.main()

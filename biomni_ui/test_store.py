import tempfile
import unittest
from pathlib import Path

from biomni_ui import assist, files
from biomni_ui.runner import CITE_HINT, FORMAT_HINT, Manager
from biomni_ui.store import Store
from biomni_ui.test_runner import collect, native_model, use_native


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.store.close)  # runs before tmp.cleanup (LIFO)

    def make(self, answers):
        use_native(self, answers)
        return Manager(native_model, self.store)

    def test_persist_and_reload(self):
        m = self.make(["hi"])
        t = m.start("question one that is long")
        collect(t)
        conv = self.store.get_conversation(t.conversation_id)
        self.assertEqual(conv["title"], "question one that is long")
        self.assertEqual(conv["tasks"][0]["status"], "done")
        self.assertEqual(conv["tasks"][0]["events"][-1]["type"], "done")

    def test_followup_shares_conversation(self):
        m = self.make(["a", "a"])
        t1 = m.start("q1")
        collect(t1)
        t2 = m.start("q2", t1.conversation_id)
        collect(t2)
        conv = self.store.get_conversation(t1.conversation_id)
        self.assertEqual([t["prompt"] for t in conv["tasks"]], ["q1", "q2"])
        self.assertEqual(len(self.store.list_conversations()), 1)

    def test_extra_event_gets_next_seq(self):
        m = self.make(["a"])
        t = m.start("q")
        collect(t)
        n = len(t.events)
        ev = m.add_event(t.id, {"type": "review", "text": "ok"})
        self.assertEqual(ev["seq"], n)

    def test_delete_and_rename(self):
        t = self.make(["a"]).start("q")
        collect(t)
        self.assertTrue(self.store.rename(t.conversation_id, "新标题"))
        self.assertEqual(self.store.list_conversations()[0]["title"], "新标题")
        self.store.delete_conversation(t.conversation_id)
        self.assertEqual(self.store.list_conversations(), [])
        self.assertIsNone(self.store.get_task(t.id))

    def test_running_tasks_marked_interrupted_on_restart(self):
        self.store.create_task("x1", "c1", "p")
        again = Store(Path(self.tmp.name) / "t.db")
        self.addCleanup(again.close)
        self.assertEqual(again.get_task("x1")["status"], "interrupted")


class FilesTests(unittest.TestCase):
    def test_resolve_inside_and_outside(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            root = Path(a)
            (root / "plot.png").write_bytes(b"x")
            (root / "run.exe").write_bytes(b"x")
            (Path(b) / "secret.csv").write_text("x")
            self.assertEqual(files.resolve("plot.png", [root]), (root / "plot.png").resolve())
            self.assertIsNone(files.resolve("run.exe", [root]))  # type not allowed
            self.assertIsNone(files.resolve(str(Path(b) / "secret.csv"), [root]))  # outside roots
            self.assertIsNone(files.resolve("../" + Path(b).name + "/secret.csv", [root]))


class AssistTests(unittest.TestCase):
    def test_parse_suggestions(self):
        self.assertEqual(assist.parse_suggestions('好的 ["a","b"] 完'), ["a", "b"])
        self.assertEqual(assist.parse_suggestions("无法解析"), [])
        self.assertEqual(assist.parse_suggestions('["a", 3, ""]'), ["a"])

    def test_parse_plan(self):
        d = assist.parse_plan('说明 {"simple": false, "questions": ["物种？", 5], "plan": ["a", "b", ""]} 结束')
        self.assertEqual(d, {"simple": False, "questions": ["物种？"], "plan": ["a", "b"]})
        self.assertEqual(assist.parse_plan("乱码"), {"simple": False, "questions": [], "plan": []})
        self.assertEqual(assist.parse_plan('{"plan": "oops"}')["plan"], [])

    def test_approved_prompt(self):
        txt = assist.approved_prompt("q", ["查询", "总结"], [("物种？", "人"), ("无答案", " ")])
        self.assertIn("物种？ → 人", txt)
        self.assertNotIn("无答案", txt)
        self.assertIn("2. [ ] 总结", txt)
        self.assertEqual(assist.approved_prompt("q", [], []), "")

    def test_agent_prompt_includes_extra_but_stored_prompt_is_plain(self):
        use_native(self, ["x"])
        t = Manager(native_model, Store(Path(tempfile.mkdtemp()) / "x.db")).start("问题", None, "附加")
        collect(t)
        self.assertEqual(t.prompt, "问题")
        self.assertTrue(t.agent_prompt.startswith("问题\n\n附加\n\n"))
        self.assertIn(FORMAT_HINT, t.agent_prompt)
        self.assertIn(CITE_HINT, t.agent_prompt)

    def test_transcript_truncates(self):
        ev = [{"type": "observation", "text": "x" * 1500}] * 20
        self.assertLess(len(assist.transcript("q", ev)), assist.MAX_TRANSCRIPT_CHARS + 100)


class UploadNames(unittest.TestCase):
    def test_plain_names_and_types(self):
        self.assertEqual(files.safe_upload_name("counts.csv"), "counts.csv")
        self.assertEqual(files.safe_upload_name("my data (1).xlsx"), "my data (1).xlsx")
        self.assertEqual(files.safe_upload_name("基因表达.tsv"), "基因表达.tsv")

    def test_path_parts_are_dropped(self):
        for evil in ("../../etc/passwd.csv", r"..\..\win.ini.txt", "/abs/path/x.csv", r"C:\Users\x\y.csv"):
            name = files.safe_upload_name(evil)
            self.assertNotIn("/", name)
            self.assertNotIn("\\", name)
            self.assertFalse(name.startswith("."))

    def test_rejected(self):
        for bad in ("run.exe", "script.bat", "noext", "", "..", ".csv.exe", "a.py"):
            with self.assertRaises(ValueError, msg=bad):
                files.safe_upload_name(bad)

    def test_describe_has_time_and_size(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.csv"
            p.write_bytes(b"x,y\n1,2\n")  # bytes: write_text would turn \n into \r\n on Windows
            info = files.describe(p)
            self.assertEqual((info["name"], info["kind"], info["size"]), ("a.csv", "table", 8))
            self.assertGreater(info["mtime"], 1_000_000_000)


class ProjectNotesPublishedTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "p.db")
        self.addCleanup(self.store.close)

    def test_default_project_always_listed_and_conversations_start_there(self):
        self.store.create_task("t1", "c1", "hello")
        projects = self.store.list_projects()
        self.assertEqual([p["id"] for p in projects], ["quick"])
        self.assertEqual(projects[0]["count"], 1)
        self.assertEqual(self.store.list_conversations()[0]["project_id"], "quick")

    def test_create_move_and_delete_project(self):
        self.store.create_task("t1", "c1", "hello")
        proj = self.store.create_project("CAR-T 研究")
        self.assertTrue(self.store.set_project("c1", proj["id"]))
        self.assertEqual(self.store.list_conversations()[0]["project_id"], proj["id"])
        with self.assertRaises(ValueError):
            self.store.create_project("CAR-T 研究")
        with self.assertRaises(ValueError):
            self.store.create_project("Quick task")
        self.assertTrue(self.store.delete_project(proj["id"]))
        self.assertEqual(self.store.list_conversations()[0]["project_id"], "quick")  # tasks are kept
        self.assertFalse(self.store.delete_project("quick"))

    def test_unknown_project_or_conversation_is_refused(self):
        self.store.create_task("t1", "c1", "hello")
        self.assertFalse(self.store.set_project("c1", "nope"))
        self.assertFalse(self.store.set_project("missing", "quick"))

    def test_notes_roundtrip(self):
        self.store.create_task("t1", "c1", "hello")
        self.assertEqual(self.store.get_notes("c1"), "")
        self.assertTrue(self.store.set_notes("c1", "记一下"))
        self.assertEqual(self.store.get_notes("c1"), "记一下")
        self.assertEqual(self.store.get_conversation("c1")["notes"], "记一下")
        self.assertIsNone(self.store.get_notes("missing"))
        self.assertFalse(self.store.set_notes("missing", "x"))

    def test_conversation_list_has_latest_status(self):
        self.store.create_task("t1", "c1", "hello")
        self.store.set_status("t1", "done")
        self.assertEqual(self.store.list_conversations()[0]["status"], "done")

    def test_published_list_and_delete(self):
        self.store.add_published("a1", "结果一", "t1")
        self.assertEqual([p["title"] for p in self.store.list_published()], ["结果一"])
        self.assertTrue(self.store.delete_published("a1"))
        self.assertFalse(self.store.delete_published("a1"))


class UsageTests(unittest.TestCase):
    def test_usage_counts_tasks_and_code(self):
        with tempfile.TemporaryDirectory() as d:
            store = Store(Path(d) / "u.db")
            store.create_task("t1", "c1", "q")
            store.set_status("t1", "done")
            store.add_event("t1", {"seq": 0, "type": "code", "language": "python", "code": "print(1)"})
            store.add_event("t1", {"seq": 1, "type": "observation", "text": "1", "elapsed": 2.5})
            u = store.usage(days=7)
            self.assertEqual((u["tasks_total"], u["status"], u["code_runs"], u["code_seconds"]), (1, {"done": 1}, 1, 2.5))
            self.assertEqual(len(u["series"]), 7)
            self.assertEqual(u["series"][-1]["tasks"], 1)
            store.close()  # before the folder is removed (Windows keeps open files locked)


if __name__ == "__main__":
    unittest.main()

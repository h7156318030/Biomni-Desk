import tempfile
import unittest
from pathlib import Path

from biomni_ui import prefs
from biomni_ui.models import ModelStore
from biomni_ui.store import Store


class CleanTests(unittest.TestCase):
    def test_unknown_values_fall_back_and_text_is_trimmed(self):
        v = prefs.clean({"prefs": {"language": "cobol", "image_format": "SVG", "style": "neon", "appearance": "dark"},
                         "profile": {"first_name": "  Xiaoming   ", "areas": ["基因组学", "不存在的领域"], "evil": "x"}})
        self.assertEqual(v["prefs"]["language"], "any")
        self.assertEqual(v["prefs"]["image_format"], "svg")
        self.assertEqual(v["prefs"]["style"], "classic")
        self.assertEqual(v["prefs"]["appearance"], "dark")
        self.assertEqual(v["profile"]["first_name"], "Xiaoming")
        self.assertEqual(v["profile"]["areas"], ["Genomics"])
        self.assertNotIn("evil", v["profile"])

    def test_instructions_are_deduped_and_capped(self):
        v = prefs.clean({"prefs": {"instructions": ["a", "a", " ", "b"] + [f"x{i}" for i in range(40)]}})
        self.assertEqual(v["prefs"]["instructions"][:2], ["a", "b"])
        self.assertEqual(len(v["prefs"]["instructions"]), prefs.MAX_INSTRUCTIONS)

    def test_garbage_input_gives_defaults(self):
        self.assertEqual(prefs.clean({"profile": 3, "prefs": "no"}), prefs.clean({}))


class BriefingTests(unittest.TestCase):
    def test_empty_prefs_say_nothing(self):
        self.assertEqual(prefs.briefing(prefs.clean({})), "")

    def test_profile_and_habits_reach_the_agent(self):
        v = prefs.clean({"profile": {"first_name": "小明", "last_name": "王", "institution": "上海交通大学", "areas": ["CRISPR / gene editing"]},
                         "prefs": {"language": "r", "image_format": "svg", "instructions": ["回答用中文"]}})
        text = prefs.briefing(v)
        for needle in ("王小明", "上海交通大学", "CRISPR / gene editing", "prefer R", "SVG", "回答用中文"):
            self.assertIn(needle, text)

    def test_project_context_instructions_and_last_files(self):
        v = prefs.clean({"prefs": {"instructions": ["全局规则"]}})
        text = prefs.briefing(v, {"context": "研究 CAR-T", "instructions": ["项目规则"], "skills": []}, ["a.png", "b.csv"])
        self.assertIn("研究 CAR-T", text)
        self.assertIn("1. 全局规则", text)
        self.assertIn("2. 项目规则", text)
        self.assertIn("a.png", text)

    def test_last_results_switch_is_honoured(self):
        v = prefs.clean({"prefs": {"use_last_results": False}})
        self.assertNotIn("a.png", prefs.briefing(v, None, ["a.png"]))


class StoreFileTests(unittest.TestCase):
    def test_roundtrip_and_bom_tolerance(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "prefs.json"
            s = prefs.PrefsStore(p)
            s.save({"prefs": {"language": "python"}})
            self.assertEqual(s.load()["prefs"]["language"], "python")
            p.write_text('﻿{"prefs": {"language": "r"}}', encoding="utf-8")  # a Windows editor may add a BOM
            self.assertEqual(s.load()["prefs"]["language"], "r")

    def test_project_settings_are_cleaned(self):
        v = prefs.clean_project_settings({"context": "x" * 5000, "instructions": ["a", "a"], "skills": ["s1", ""]})
        self.assertEqual(len(v["context"]), prefs.MAX_CONTEXT_CHARS)
        self.assertEqual((v["instructions"], v["skills"]), (["a"], ["s1"]))


class ProjectSettingsInStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "s.db")
        self.addCleanup(self.store.close)

    def test_settings_roundtrip_default_and_custom_project(self):
        self.assertEqual(self.store.get_project_settings("quick"), {"context": "", "instructions": [], "skills": []})
        self.assertTrue(self.store.set_project_settings("quick", {"context": "c", "instructions": ["i"], "skills": ["s"]}))
        self.assertEqual(self.store.get_project_settings("quick")["context"], "c")
        self.assertFalse(self.store.set_project_settings("nope", {"context": "x"}))

    def test_conversation_project_and_recent_files(self):
        self.store.create_task("t1", "c1", "q1")
        self.store.add_event("t1", {"seq": 0, "type": "observation", "text": "ok", "artifacts": [{"name": "a.png", "path": "a.png", "kind": "image"}]})
        self.store.create_task("t2", "c2", "q2")
        self.assertEqual(self.store.conversation_project("c1"), "quick")
        self.assertEqual(self.store.conversation_project(None), "quick")
        self.assertEqual(self.store.recent_files("quick", exclude_conversation="c2"), ["a.png"])
        self.assertEqual(self.store.recent_files("quick", exclude_conversation="c1"), [])  # not the conversation itself

    def test_export_and_clear(self):
        self.store.create_task("t1", "c1", "q1")
        self.assertEqual(len(self.store.export_all()["conversations"]), 1)
        self.assertEqual(self.store.data_info()["conversations"], 1)
        self.assertEqual(self.store.delete_all_conversations(), 1)
        self.assertEqual(self.store.list_conversations(), [])


class ModelHiddenTests(unittest.TestCase):
    def test_hide_and_show_without_touching_the_chatgpt_entry(self):
        with tempfile.TemporaryDirectory() as d:
            m = ModelStore(Path(d) / "m.json")
            self.assertFalse(m.set_hidden("chatgpt-luna", True))
            self.assertTrue(m.set_hidden("or-deepseek-v32", True))
            self.assertTrue({x["id"]: x["hidden"] for x in m.list()}["or-deepseek-v32"])
            added = m.add("vendor/some-model:free")
            m.set_hidden(added["id"], True)
            m.delete(added["id"])  # deleting must not leave the id behind
            self.assertTrue(m.set_hidden("or-deepseek-v32", False))
            self.assertFalse({x["id"]: x["hidden"] for x in m.list()}["or-deepseek-v32"])


if __name__ == "__main__":
    unittest.main()

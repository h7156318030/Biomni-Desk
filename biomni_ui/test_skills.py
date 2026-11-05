import tempfile
import unittest
from pathlib import Path

from biomni.know_how.loader import KnowHowLoader
from biomni_ui import skills as sk


class Agent:
    def __init__(self):
        self.know_how_loader = KnowHowLoader()


class SkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.store = sk.SkillStore(root / "mine", root / "state.json")

    def test_parse_dump_roundtrip(self):
        text = sk.dump({"title": "标题", "description": "说明", "uses": "a, b"}, "## 步骤\n1. x")
        meta, body = sk.parse(text)
        self.assertEqual(meta["title"], "标题")
        self.assertEqual(meta["uses"], "a, b")
        self.assertTrue(body.startswith("## 步骤"))

    def test_builtin_skills_are_valid(self):
        items = self.store.list()
        self.assertGreaterEqual(len(items), 4)
        for s in items:
            self.assertEqual(s["source"], "builtin")
            self.assertTrue(s["title"] and s["description"] and s["when_to_use"], s["id"])
            self.assertTrue(self.store.get(s["id"])["body"].strip(), s["id"])

    def test_create_update_delete_user_skill(self):
        s = self.store.save("my-skill", {"title": "我的", "description": "d"}, "正文")
        self.assertEqual(s["source"], "mine")
        self.store.save("my-skill", {"title": "我的2"}, "新正文")
        self.assertEqual(self.store.get("my-skill")["title"], "我的2")
        self.assertTrue(self.store.delete("my-skill"))
        self.assertIsNone(self.store.get("my-skill"))

    def test_validation(self):
        with self.assertRaises(ValueError):
            self.store.save("Bad ID", {"title": "t"}, "b")
        with self.assertRaises(ValueError):
            self.store.save("literature-review", {"title": "t"}, "b")  # clashes with a built-in
        with self.assertRaises(ValueError):
            self.store.save("ok", {"title": ""}, "b")
        with self.assertRaises(ValueError):
            self.store.save("ok", {"title": "t"}, "  ")
        self.assertFalse(self.store.delete("../x"))

    def test_path_traversal_is_not_resolved(self):
        self.assertIsNone(self.store.get("../../etc/passwd"))

    def test_toggle_and_sync_agent(self):
        agent = Agent()
        n = self.store.sync_agent(agent)
        docs = [d for d in agent.know_how_loader.documents if d.startswith("skill_")]
        self.assertEqual(n, len(docs))
        self.assertGreaterEqual(n, 4)
        # the retrieval path needs this key on every document
        for d in docs:
            self.assertIn("content_without_metadata", agent.know_how_loader.documents[d])
        self.store.set_enabled("literature-review", False)
        self.store.sync_agent(agent)
        self.assertNotIn("skill_literature-review", agent.know_how_loader.documents)
        self.store.set_enabled("literature-review", True)
        self.store.sync_agent(agent)
        self.assertIn("skill_literature-review", agent.know_how_loader.documents)

    def test_sync_is_idempotent(self):
        agent = Agent()
        self.store.sync_agent(agent)
        count = len(agent.know_how_loader.documents)
        self.store.sync_agent(agent)
        self.assertEqual(len(agent.know_how_loader.documents), count)


if __name__ == "__main__":
    unittest.main()

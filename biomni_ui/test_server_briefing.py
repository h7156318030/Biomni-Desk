"""The settings must reach the agent: check what `create_task` hands to the Manager, without running any model."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from biomni_ui import prefs as ui_prefs
from biomni_ui import server as srv
from biomni_ui.store import Store


class BriefingReachesTheAgent(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(Path(self.tmp.name) / "t.db")
        self.addCleanup(self.store.close)
        self.calls: list[tuple[str, str | None, str]] = []

        def fake_start(prompt, conversation_id=None, extra="", mode="ask"):
            self.calls.append((prompt, conversation_id, extra))
            self.store.create_task("t1", conversation_id or "c-new", prompt)
            return SimpleNamespace(id="t1", conversation_id=conversation_id or "c-new")

        self._saved = (srv.store, srv.prefs_store, srv.manager.start)
        srv.store = self.store
        srv.prefs_store = ui_prefs.PrefsStore(Path(self.tmp.name) / "prefs.json")
        srv.manager.start = fake_start
        self.addCleanup(self._restore)
        self.client = TestClient(srv.app)  # no `with`: the heavy start-up (loading the agent) is skipped

    def _restore(self):
        srv.store, srv.prefs_store, srv.manager.start = self._saved

    def test_profile_instructions_and_project_context_are_in_the_task_text(self):
        srv.prefs_store.save({"profile": {"last_name": "王", "first_name": "小明", "institution": "上海交通大学"},
                              "prefs": {"language": "r", "instructions": ["回答用中文"]}})
        self.store.set_project_settings("quick", {"context": "只关注免疫学", "instructions": ["项目指令甲"], "skills": []})
        r = self.client.post("/api/tasks", json={"prompt": "查王小明的论文"})
        self.assertEqual(r.status_code, 200)
        extra = self.calls[0][2]
        for needle in ("王小明", "上海交通大学", "prefer R", "回答用中文", "只关注免疫学", "项目指令甲"):
            self.assertIn(needle, extra)

    def test_empty_settings_add_nothing(self):
        self.client.post("/api/tasks", json={"prompt": "hi"})
        self.assertEqual(self.calls[0][2], "")

    def test_new_conversation_goes_into_the_chosen_project(self):
        proj = self.store.create_project("免疫项目")
        self.store.set_project_settings(proj["id"], {"context": "免疫项目背景", "instructions": [], "skills": []})
        self.client.post("/api/tasks", json={"prompt": "hi", "project_id": proj["id"]})
        self.assertIn("免疫项目背景", self.calls[0][2])
        self.assertEqual(self.store.conversation_project("c-new"), proj["id"])

    def test_follow_up_uses_the_conversation_s_own_project(self):
        proj = self.store.create_project("免疫项目")
        self.store.set_project_settings(proj["id"], {"context": "免疫项目背景", "instructions": [], "skills": []})
        self.store.create_task("t0", "c1", "first")
        self.store.set_project("c1", proj["id"])
        self.client.post("/api/tasks", json={"prompt": "next", "conversation_id": "c1"})
        self.assertIn("免疫项目背景", self.calls[0][2])

    def test_unknown_project_falls_back_to_the_default(self):
        self.client.post("/api/tasks", json={"prompt": "hi", "project_id": "no-such"})
        self.assertEqual(self.store.conversation_project("c-new"), "quick")


if __name__ == "__main__":
    unittest.main()


class ProjectSkillsAreMentioned(unittest.TestCase):
    def test_attached_skill_text_reaches_the_task(self):
        from biomni_ui import mentions
        from biomni_ui.skills import SkillStore

        with tempfile.TemporaryDirectory() as d:
            store = SkillStore(Path(d) / "skills", Path(d) / "state.json")
            sid = next(s["id"] for s in store.list() if s["source"] == "builtin" and s["enabled"])
            text = mentions.to_prompt([{"kind": "skill", "id": sid}], skills=store, tool_names=set(), data_names=set(), roots=[])
            self.assertIn(store.get(sid)["title"], text)
            self.assertGreater(len(text), 80)  # the skill's real steps are included, not just its name

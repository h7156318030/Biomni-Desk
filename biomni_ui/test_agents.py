import tempfile
import unittest
from pathlib import Path

from biomni_ui import agents, prefs, runner

EFFORTS = ("low", "medium", "high", "xhigh")


class Validation(unittest.TestCase):
    def test_a_good_profile_is_normalised(self):
        out = agents.clean({"name": "  Literature   scout ", "model_id": "m1", "effort": "high", "mode": "auto",
                            "tools_off": ["web_search", "web_search", "not_a_tool"], "skills": ["a", "a", " b "], "instructions": " be brief "},
                           {"m1"}, EFFORTS)
        self.assertEqual(out["name"], "Literature scout")
        self.assertEqual(out["tools_off"], ["web_search"])
        self.assertEqual(out["skills"], ["a", "b"])
        self.assertEqual(out["instructions"], "be brief")

    def test_empty_model_and_effort_mean_the_app_settings(self):
        out = agents.clean({"name": "Default-like", "model_id": "", "effort": None, "mode": "ask"}, set(), EFFORTS)
        self.assertIsNone(out["model_id"])
        self.assertIsNone(out["effort"])

    def test_refusals(self):
        with self.assertRaises(ValueError):
            agents.clean({"name": "", "mode": "ask"}, set(), EFFORTS)
        with self.assertRaises(ValueError):
            agents.clean({"name": "x", "model_id": "gone", "mode": "ask"}, {"m1"}, EFFORTS)
        with self.assertRaises(ValueError):
            agents.clean({"name": "x", "effort": "extreme", "mode": "ask"}, set(), EFFORTS)
        with self.assertRaises(ValueError):
            agents.clean({"name": "x", "mode": "yolo"}, set(), EFFORTS)


class Store(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = agents.AgentStore(Path(self._tmp.name) / "agents.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_update_get_delete(self):
        p = self.store.create({"name": "A", "model_id": None, "effort": None, "mode": "ask", "tools_off": [], "skills": [], "instructions": ""})
        self.assertEqual(self.store.get(p["id"])["name"], "A")
        u = self.store.update(p["id"], {"name": "B", "mode": "auto", "tools_off": ["delegate_task"], "skills": [], "instructions": "", "model_id": None, "effort": None})
        self.assertEqual(u["mode"], "auto")
        self.assertEqual(self.store.get(p["id"])["tools_off"], ["delegate_task"])
        self.assertTrue(self.store.delete(p["id"]))
        self.assertIsNone(self.store.get(p["id"]))
        self.assertIsNone(self.store.update("nope", {"name": "x"}))

    def test_limit_on_profiles(self):
        for i in range(agents.MAX_PROFILES):
            self.store.create({"name": f"p{i}", "mode": "ask"})
        with self.assertRaises(ValueError):
            self.store.create({"name": "one too many", "mode": "ask"})


class ToolsOff(unittest.TestCase):
    def test_profile_and_project_choices_add_up_and_only_optional_tools_count(self):
        off = agents.tools_off_for({"tools_off": ["web_search"]}, {"tools_off": ["delegate_task", "bash"]})
        self.assertEqual(off, {"web_search", "delegate_task"})  # bash is not optional, so it cannot be switched off

    def test_no_profile_no_project_switches_nothing(self):
        self.assertEqual(agents.tools_off_for(None, None), set())


class ProjectSettingsFields(unittest.TestCase):
    def test_project_files_and_tools_off_are_kept_and_filtered(self):
        out = prefs.clean_project_settings({"files": ["a.csv", "a.csv", ""], "tools_off": ["propose_memory", "x", "propose_memory"]})
        self.assertEqual(out["files"], ["a.csv"])
        self.assertEqual(out["tools_off"], ["propose_memory"])


class TaskCarriesProfile(unittest.TestCase):
    def test_a_task_keeps_its_profile_and_tool_choices(self):
        task = runner.Task("q", "conv1", None, "", mode="auto", agent={"model_id": "m1", "instructions": "x"}, tools_off={"web_search"})
        self.assertEqual(task.agent["model_id"], "m1")
        self.assertEqual(task.tools_off, {"web_search"})
        self.assertEqual(task.mode, "auto")
        self.assertFalse(task.allow_ask)

    def test_default_task_has_no_profile(self):
        task = runner.Task("q", "conv2")
        self.assertEqual(task.agent, {})
        self.assertEqual(task.tools_off, set())


if __name__ == "__main__":
    unittest.main()

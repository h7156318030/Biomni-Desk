import unittest
from types import SimpleNamespace

from biomni_ui import runner, settings


EFFORTS = {"low", "medium", "high"}


class Roles(unittest.TestCase):
    def test_a_saved_model_or_none_is_accepted(self):
        out = settings.validate_roles({"subagent_model_id": "m1", "reviewer_model_id": None}, {"m1", "m2"}, EFFORTS)
        self.assertEqual(out, {"subagent_model_id": "m1", "reviewer_model_id": None})

    def test_empty_means_same_as_the_main_model(self):
        out = settings.validate_roles({"subagent_model_id": "", "reviewer_model_id": "m2"}, {"m2"}, EFFORTS)
        self.assertEqual(out, {"subagent_model_id": None, "reviewer_model_id": "m2"})

    def test_an_unknown_model_is_refused(self):
        with self.assertRaises(ValueError):
            settings.validate_roles({"subagent_model_id": "gone"}, {"m1"}, EFFORTS)

    def test_planner_and_image_roles_and_levels_are_kept(self):
        out = settings.validate_roles({"planner_model_id": "m1", "image_model_id": "m2", "subagent_effort": "low", "planner_effort": None},
                                      {"m1", "m2"}, EFFORTS)
        self.assertEqual(out, {"planner_model_id": "m1", "image_model_id": "m2", "subagent_effort": "low", "planner_effort": None})

    def test_a_level_that_is_not_offered_is_refused(self):
        with self.assertRaises(ValueError):
            settings.validate_roles({"reviewer_effort": "extreme"}, set(), EFFORTS)

    def test_sub_agent_count_must_be_a_whole_number_in_range(self):
        self.assertEqual(settings.validate_roles({"subagent_max": 4}, set(), EFFORTS), {"subagent_max": 4})
        for bad in (0, 7, 2.5, True, None):
            with self.assertRaises(ValueError):
                settings.validate_roles({"subagent_max": bad}, set(), EFFORTS)

    def test_memory_switch_must_be_a_boolean(self):
        self.assertEqual(settings.validate_roles({"memory_auto": False}, set(), EFFORTS), {"memory_auto": False})
        with self.assertRaises(ValueError):
            settings.validate_roles({"memory_auto": "yes"}, set(), EFFORTS)

    def test_roles_and_settings_are_stored_keys(self):
        for k in ("planner_model_id", "subagent_model_id", "reviewer_model_id", "image_model_id", "subagent_effort", "subagent_max",
                  "memory_recall_chars", "memory_auto"):
            self.assertIn(k, settings.KEYS)
        self.assertEqual(settings.get(__import__("pathlib").Path("/nonexistent/x.json"), "subagent_max"), 3)


class LoopTarget(unittest.TestCase):
    def test_an_openai_compatible_model_gives_its_endpoint(self):
        class ChatOpenAI:  # the class name is what the runner checks
            openai_api_key = "k-test"
            openai_api_base = "https://example.org/v1"
            model_name = "some-model"
            extra_body = {"reasoning": {"effort": "low"}}

        ChatOpenAI.__name__ = "ChatOpenAI"
        model, endpoint = runner._loop_target(ChatOpenAI())
        self.assertEqual(model, "some-model")
        self.assertEqual(endpoint["base_url"], "https://example.org/v1")
        self.assertEqual(endpoint["extra"], {"reasoning": {"effort": "low"}})

    def test_a_model_that_cannot_run_the_loop_gives_none(self):
        self.assertIsNone(runner._loop_target(SimpleNamespace(model="x")))


if __name__ == "__main__":
    unittest.main()

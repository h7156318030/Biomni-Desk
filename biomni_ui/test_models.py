import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui.codex_llm import ChatCodex, resolve_effort
from biomni_ui.models import BUILTIN, ModelStore


class Registry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = ModelStore(Path(self.tmp.name) / "m" / "models.json")

    def test_builtin_has_exactly_one_gpt_and_it_is_luna(self):
        gpt = [m for m in BUILTIN if m["source"] == "Codex"]
        self.assertEqual([m["model"] for m in gpt], ["gpt-6-luna"])
        self.assertTrue(all(m["builtin"] for m in BUILTIN))
        self.assertEqual(len({m["id"] for m in BUILTIN}), len(BUILTIN))

    def test_add_find_delete(self):
        e = self.store.add("mistralai/mistral-large-2411", "Mistral Large", "测试")
        self.assertEqual(e["id"], "u-1")
        self.assertEqual(self.store.find("Custom", "mistralai/mistral-large-2411")["label"], "Mistral Large")
        self.assertEqual(self.store.add("z-ai/glm-4.6")["id"], "u-2")
        self.assertTrue(self.store.delete("u-1"))
        self.assertIsNone(self.store.get("u-1"))
        self.assertEqual(self.store.add("x-ai/grok-4")["id"], "u-3")  # ids are never reused
        self.assertFalse(self.store.delete("u-99"))
        self.assertFalse(self.store.delete("chatgpt-luna"))  # built-ins are not deletable here

    def test_label_defaults_to_model(self):
        self.assertEqual(self.store.add("a/b-c")["label"], "a/b-c")

    def test_rejects_bad_names_duplicates_and_other_gpt(self):
        for bad in ("", "has space", "-lead", "x" * 200, "openai/gpt-5", "gpt-4o", "vendor/gpt-5-mini", "OpenAI/o3"):
            with self.assertRaises(ValueError, msg=bad):
                self.store.add(bad)
        with self.assertRaises(ValueError):
            self.store.add("deepseek/deepseek-v3.2")  # already built in
        self.store.add("some/model")
        with self.assertRaises(ValueError):
            self.store.add("some/model")

    def test_gpt_neox_style_open_models_are_fine(self):
        self.assertEqual(self.store.add("EleutherAI/gpt-neox-20b")["source"], "Custom")

    def test_corrupt_file_is_ignored(self):
        self.store.path.parent.mkdir(parents=True)
        self.store.path.write_text("{oops", encoding="utf-8")
        self.assertEqual(len(self.store.list()), len(BUILTIN))


class Effort(unittest.TestCase):
    def setUp(self):
        # These tests cover the `codex exec` path, so pretend nobody is signed in to the ChatGPT backend.
        from unittest import mock

        p = mock.patch("biomni_ui.chatgpt_api.is_logged_in", return_value=False)
        p.start()
        self.addCleanup(p.stop)

    def test_resolve(self):
        self.assertEqual(resolve_effort(None), "high")
        self.assertEqual(resolve_effort(" XHigh "), "xhigh")
        with self.assertRaises(ValueError):
            resolve_effort("ultra")

    def test_command_carries_model_and_effort(self):
        calls = []

        def fake_run(cmd, **kw):
            calls.append(cmd)
            out = Path(cmd[cmd.index("-o") + 1])
            out.write_text("ok", encoding="utf-8")
            return mock.Mock(returncode=0, stderr="", stdout="")

        llm = ChatCodex(model="gpt-6-luna", reasoning_effort="medium", codex_bin="codex")
        with mock.patch("biomni_ui.codex_llm.subprocess.run", fake_run):
            self.assertEqual(llm.invoke([("human", "hi")]).content, "ok")
        cmd = calls[0]
        self.assertEqual(cmd[cmd.index("-m") + 1], "gpt-6-luna")
        self.assertIn('model_reasoning_effort="medium"', cmd)

    def test_default_effort_is_high(self):
        self.assertEqual(ChatCodex().reasoning_effort, "high")


if __name__ == "__main__":
    unittest.main()


class CostTests(unittest.TestCase):
    def test_cost_labels(self):
        from biomni_ui.models import BUILTIN, cost_of

        by_id = {m["id"]: cost_of(m) for m in BUILTIN}
        self.assertEqual(by_id["chatgpt-luna"], "member")
        self.assertEqual(by_id["or-nemotron-ultra"], "free")
        self.assertEqual(by_id["or-deepseek-v32"], "paid")
        self.assertEqual(by_id["or-kimi-k25"], "paid")

    def test_store_lists_cost_for_user_models(self):
        import tempfile
        from pathlib import Path

        from biomni_ui.models import ModelStore

        with tempfile.TemporaryDirectory() as d:
            store = ModelStore(Path(d) / "m.json")
            store.add("vendor/some-model:free")
            store.add("vendor/other-model")
            costs = {m["model"]: m["cost"] for m in store.list() if not m["builtin"]}
            self.assertEqual(costs, {"vendor/some-model:free": "free", "vendor/other-model": "paid"})

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from biomni_ui import settings as s


class SettingsTests(unittest.TestCase):
    def test_validate_ok(self):
        out = s.validate({"source": "Codex", "model": " gpt-x ", "use_tool_retriever": False}, custom_ready=False)
        self.assertEqual(out, {"source": "Codex", "model": "gpt-x", "use_tool_retriever": False})

    def test_validate_rejects(self):
        for bad, ready in [
            ({"source": "Nope"}, True),
            ({"source": "Custom"}, False),  # no endpoint configured
            ({"model": "  "}, True),
            ({"use_tool_retriever": "yes"}, True),
        ]:
            with self.assertRaises(ValueError):
                s.validate(bad, custom_ready=ready)
        self.assertEqual(s.validate({"source": "Custom"}, custom_ready=True), {"source": "Custom"})

    def test_save_load_ignores_unknown_keys(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "ui" / "settings.json"
            s.save(p, {}, {"source": "Codex", "api_key": "secret"})
            self.assertEqual(s.load(p), {"source": "Codex"})  # only known keys are read back
            s.save(p, s.load(p), {"model": "m"})
            self.assertEqual(s.load(p), {"source": "Codex", "model": "m"})

    def test_load_missing_or_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(s.load(Path(d) / "none.json"), {})
            bad = Path(d) / "bad.json"
            bad.write_text("{oops", encoding="utf-8")
            self.assertEqual(s.load(bad), {})

    def test_apply(self):
        cfg = SimpleNamespace(source=None, llm="a", use_tool_retriever=True, commercial_mode=False)
        s.apply(cfg, {"source": "Codex", "model": "default", "commercial_mode": True})
        self.assertEqual((cfg.source, cfg.llm, cfg.use_tool_retriever, cfg.commercial_mode),
                         ("Codex", "default", True, True))


if __name__ == "__main__":
    unittest.main()

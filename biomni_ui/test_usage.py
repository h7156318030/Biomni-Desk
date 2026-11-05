import json
import os
import tempfile
import unittest
from pathlib import Path

# every test writes its counts to a temporary file, never to the user's ui_data folder
_TMP = tempfile.mkdtemp(prefix="usage-test-")
os.environ["BIOMNI_UI_USAGE_FILE"] = str(Path(_TMP) / "usage.json")

from biomni_ui import providers, usage  # noqa: E402


class UsageCounts(unittest.TestCase):
    def setUp(self):
        self.path = Path(_TMP) / f"{self._testMethodName}.json"
        self.store = usage.UsageStore(self.path)

    def test_counts_persist_across_instances(self):
        self.store.bump("tool", "web_search")
        self.store.bump("tool", "web_search")
        again = usage.UsageStore(self.path)
        self.assertEqual(again.count("tool", "web_search"), 2)
        self.assertEqual(json.loads(self.path.read_text(encoding="utf-8")), {"tool:web_search": 2})

    def test_bonus_is_zero_when_unused_and_capped(self):
        self.assertEqual(self.store.bonus("skill", "never"), 0.0)
        for _ in range(500):
            self.store.bump("skill", "common")
        self.assertLessEqual(self.store.bonus("skill", "common"), 2.0)
        self.assertGreater(self.store.bonus("skill", "common"), 0.0)

    def test_top_lists_the_most_used_first_within_one_kind(self):
        self.store.bump("func", "pubmed_search", 3)
        self.store.bump("func", "gene_info", 5)
        self.store.bump("tool", "bash", 9)
        top = self.store.top("func")
        self.assertEqual([x["name"] for x in top], ["gene_info", "pubmed_search"])
        self.assertEqual(top[0]["count"], 5)

    def test_an_empty_name_is_not_counted_and_a_broken_file_starts_empty(self):
        self.store.bump("tool", "  ")
        self.assertEqual(self.store.top("tool"), [])
        self.path.write_text("not json", encoding="utf-8")
        self.assertEqual(usage.UsageStore(self.path).top("tool"), [])


class RoutesAreUnique(unittest.TestCase):
    def test_no_two_endpoints_share_a_path(self):
        # a second @app.get on the same path silently hides the first one (the model-usage page broke this way)
        from collections import Counter

        from biomni_ui import server as srv

        paths = [(getattr(r, "path", ""), tuple(sorted(getattr(r, "methods", ()) or ()))) for r in srv.app.routes]
        dupes = [p for p, n in Counter(paths).items() if n > 1]
        self.assertEqual(dupes, [])


class AnthropicPreset(unittest.TestCase):
    def test_claude_and_the_other_common_providers_are_offered(self):
        ids = {p["id"]: p for p in providers.PRESETS}
        self.assertEqual(ids["anthropic"]["base_url"], "https://api.anthropic.com/v1")
        self.assertEqual(ids["openai"]["base_url"], "https://api.openai.com/v1")
        self.assertIn("generativelanguage.googleapis.com", ids["google"]["base_url"])
        self.assertEqual(ids["xai"]["base_url"], "https://api.x.ai/v1")
        self.assertFalse(any(p["local"] for p in (ids["anthropic"], ids["openai"], ids["google"], ids["xai"])))

    def test_a_claude_preset_saves_under_its_own_id(self):
        with tempfile.TemporaryDirectory() as d:
            store = providers.ProviderStore(Path(d) / "p.json", env_base_url=lambda: "", env_api_key=lambda: "")
            p = store.add("Anthropic（Claude）", "https://api.anthropic.com/v1", "sk-test", preset="anthropic")
            self.assertEqual(p["id"], "anthropic")
            self.assertEqual(store.credentials("anthropic"), ("https://api.anthropic.com/v1", "sk-test"))


if __name__ == "__main__":
    unittest.main()

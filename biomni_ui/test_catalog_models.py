import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import AIMessage

from biomni_ui import chatgpt_api, llm_calls
from biomni_ui.catalog import Catalog, normalize
from biomni_ui.llm_guard import StopGuardLLM
from biomni_ui.models import ModelStore

RAW = [
    {"id": "acme/free-small:free", "name": "Acme Free Small", "context_length": 8000, "pricing": {"prompt": "0", "completion": "0"},
     "supported_parameters": ["reasoning", "stop"], "reasoning": {"supported_efforts": ["high", "medium", "none"], "default_effort": "high"}},
    {"id": "acme/big", "name": "Acme Big", "context_length": 200000, "pricing": {"prompt": "0.000001", "completion": "0.000004"},
     "supported_parameters": ["reasoning"], "reasoning": {}},
    {"id": "acme/plain", "name": "Acme Plain", "context_length": 4000, "pricing": {"prompt": "0.0000005", "completion": "0.000001"}, "supported_parameters": ["stop"]},
    {"id": "openai/gpt-5", "name": "GPT", "pricing": {"prompt": "0.00001", "completion": "0.00003"}, "supported_parameters": ["reasoning"]},
    {"id": "someone/gpt-4o-clone", "name": "clone", "pricing": {"prompt": "0.000001", "completion": "0.000002"}, "supported_parameters": []},
]


class CatalogTests(unittest.TestCase):
    def test_normalize_prices_and_efforts(self):
        free = normalize(RAW[0])
        self.assertTrue(free["free"])
        self.assertEqual(free["efforts"], ["high", "medium"])  # "none" is not an effort level
        self.assertEqual(free["default_effort"], "high")
        big = normalize(RAW[1])
        self.assertEqual((big["prompt_per_m"], big["completion_per_m"], big["free"]), (1.0, 4.0, False))
        self.assertEqual(big["efforts"], ["medium", "high"])  # reasoning supported, levels not listed -> the usual two (no level below the starting tier)
        self.assertEqual(normalize(RAW[2])["efforts"], [])  # cannot be adjusted

    def test_gpt_models_are_never_offered(self):
        c = Catalog(fetch=lambda: RAW)
        self.assertIsNone(c.get("openai/gpt-5"))
        self.assertIsNone(c.get("someone/gpt-4o-clone"))
        self.assertEqual({m["id"] for m in c.search()}, {"acme/free-small:free", "acme/big", "acme/plain"})

    def test_search_and_free_filter(self):
        c = Catalog(fetch=lambda: RAW)
        self.assertEqual([m["id"] for m in c.search("big")], ["acme/big"])
        self.assertEqual([m["id"] for m in c.search("acme", free_only=True)], ["acme/free-small:free"])

    def test_unknown_model_is_not_found(self):
        self.assertIsNone(Catalog(fetch=lambda: RAW).get("acme/nope"))

    def test_offline_keeps_the_old_copy_and_reports_unavailable_when_there_is_none(self):
        def boom():
            raise OSError("offline")

        self.assertFalse(Catalog(fetch=boom).available())
        self.assertIsNone(Catalog(fetch=boom).search("x"))
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] > 1:
                raise OSError("offline")
            return RAW

        c = Catalog(fetch=flaky, ttl=0)  # always stale: the second load fails, the first copy must survive
        self.assertIsNotNone(c.get("acme/big"))
        self.assertIsNotNone(c.get("acme/big"))

    def test_peek_never_fetches(self):
        c = Catalog(fetch=lambda: RAW)
        self.assertIsNone(c.peek("acme/big"))
        self.assertFalse(c.peek_ready())
        c.get("acme/big")
        self.assertTrue(c.peek_ready())


class ModelDeleteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.m = ModelStore(Path(self.tmp.name) / "m.json")

    def ids(self):
        return [x["id"] for x in self.m.list()]

    def test_builtin_models_can_be_deleted_and_restored(self):
        self.assertIn("or-kimi-k25", self.ids())
        self.assertTrue(self.m.delete("or-kimi-k25"))
        self.assertNotIn("or-kimi-k25", self.ids())
        self.assertEqual(self.m.restore_defaults(), 1)
        self.assertIn("or-kimi-k25", self.ids())

    def test_chatgpt_cannot_be_deleted(self):
        self.assertFalse(self.m.delete("chatgpt-luna"))
        self.assertIn("chatgpt-luna", self.ids())

    def test_deleted_models_stay_deleted_across_other_changes(self):
        self.m.delete("or-kimi-k25")
        self.m.add("vendor/new-model")  # writing the custom list must not bring it back
        self.m.set_hidden("or-qwen3-235b", True)
        self.assertNotIn("or-kimi-k25", self.ids())
        self.assertTrue({x["id"]: x["hidden"] for x in self.m.list()}["or-qwen3-235b"])

    def test_efforts_are_remembered_per_model_and_forgotten_on_delete(self):
        self.m.set_effort("or-deepseek-v32", "low")
        self.assertEqual(self.m.efforts(), {"or-deepseek-v32": "low"})
        self.m.delete("or-deepseek-v32")
        self.assertEqual(self.m.efforts(), {})


class CallRecordingTests(unittest.TestCase):
    def test_reply_metadata_wins_over_what_was_asked_for(self):
        reply = AIMessage(content="x", usage_metadata={"input_tokens": 10, "output_tokens": 30, "total_tokens": 40, "output_token_details": {"reasoning": 20}},
                          response_metadata={"model": "gpt-6-luna", "effort": "xhigh"})
        rec = llm_calls.from_reply(reply, model="asked-model", effort="low", seconds=1.234)
        self.assertEqual((rec["model"], rec["effort"], rec["reasoning_tokens"], rec["output_tokens"], rec["seconds"]), ("gpt-6-luna", "xhigh", 20, 30, 1.2))

    def test_reply_without_metadata_uses_the_request_values(self):
        rec = llm_calls.from_reply(AIMessage(content="x"), model="m", effort="high", seconds=0.5)
        self.assertEqual((rec["model"], rec["effort"], rec["reasoning_tokens"]), ("m", "high", None))

    def test_guard_records_every_call(self):
        llm_calls.drain()
        inner = SimpleNamespace(invoke=lambda *a, **k: AIMessage(content="a</execute>b"))
        out = StopGuardLLM(inner, model="m1", effort="medium").invoke("hi")
        self.assertEqual(out.content, "a</execute>")
        calls = llm_calls.drain()
        self.assertEqual([(c["model"], c["effort"]) for c in calls], [("m1", "medium")])
        self.assertEqual(llm_calls.drain(), [])

    def test_chatgpt_usage_and_applied_effort_are_read_from_the_stream(self):
        events = iter([
            {"type": "response.output_text.delta", "delta": "hi"},
            {"type": "response.completed", "response": {"model": "gpt-6-luna", "reasoning": {"effort": "high"},
                                                        "usage": {"input_tokens": 5, "output_tokens": 9, "output_tokens_details": {"reasoning_tokens": 7}}}},
        ])
        text, info = chatgpt_api.collect(events)
        self.assertEqual(text, "hi")
        self.assertEqual((info["effort"], info["usage"]["output_tokens_details"]["reasoning_tokens"]), ("high", 7))


if __name__ == "__main__":
    unittest.main()

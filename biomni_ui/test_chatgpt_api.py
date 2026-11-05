import base64
import json
import tempfile
import time
import unittest
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from biomni_ui import chatgpt_api as api


def fake_jwt(claims: dict) -> str:
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
    return f"{enc({'alg': 'none'})}.{enc(claims)}.sig"


class RequestTests(unittest.TestCase):
    def test_system_becomes_instructions_and_no_tools(self):
        body = api.build_request(
            [SystemMessage(content="rules"), HumanMessage(content="q"), AIMessage(content="a"), HumanMessage(content="q2")],
            "gpt-6-luna", "high",
        )
        self.assertEqual(body["instructions"], "rules")
        self.assertEqual([i["role"] for i in body["input"]], ["user", "assistant", "user"])
        self.assertEqual(body["input"][1]["content"][0]["type"], "output_text")
        self.assertEqual(body["tools"], [])
        self.assertEqual(body["tool_choice"], "none")
        self.assertTrue(body["stream"])
        self.assertFalse(body["store"])
        self.assertEqual(body["reasoning"], {"effort": "high"})

    def test_instructions_never_empty(self):
        self.assertTrue(api.build_request([HumanMessage(content="q")], "m", "low")["instructions"])


class StreamTests(unittest.TestCase):
    def test_text_deltas_are_joined(self):
        lines = [
            "event: response.created", 'data: {"type":"response.created"}', "",
            'data: {"type":"response.output_text.delta","delta":"Hel"}',
            'data: {"type":"response.output_text.delta","delta":"lo"}',
            "data: [DONE]",
        ]
        self.assertEqual(api.collect_text(api.iter_sse(iter(lines))), "Hello")

    def test_reading_stops_at_the_stop_tag_and_never_touches_the_tail(self):
        consumed = []

        def stream():
            created = {"type": "response.created", "response": {"reasoning": {"effort": "high"}, "model": "m"}}
            yield created
            for piece in ["<execute>print(1)", "</exec", "ute>", " <observation>fake</observation>", " more"]:
                consumed.append(piece)
                yield {"type": "response.output_text.delta", "delta": piece}

        text, info = api.collect(stream(), ["</execute>"])
        self.assertTrue(text.startswith("<execute>print(1)</execute>"))
        self.assertTrue(info["stopped_early"])
        self.assertEqual(info["effort"], "high")  # known from the first event, even though no usage arrives
        self.assertEqual(consumed, ["<execute>print(1)", "</exec", "ute>"])  # the generator was not advanced past the tag

    def test_without_a_stop_tag_everything_is_read(self):
        lines = ['data: {"type":"response.output_text.delta","delta":"a"}', 'data: {"type":"response.output_text.delta","delta":"b"}']
        text, info = api.collect(api.iter_sse(iter(lines)), ["</execute>"])
        self.assertEqual(text, "ab")
        self.assertNotIn("stopped_early", info)

    def test_failure_raises(self):
        lines = ['data: {"type":"response.failed","response":{"error":{"message":"boom"}}}']
        with self.assertRaises(RuntimeError):
            api.collect_text(api.iter_sse(iter(lines)))

    def test_final_item_used_when_no_deltas(self):
        item = {"type": "message", "content": [{"type": "output_text", "text": "whole"}]}
        lines = ["data: " + json.dumps({"type": "response.output_item.done", "item": item})]
        self.assertEqual(api.collect_text(api.iter_sse(iter(lines))), "whole")


class TokenTests(unittest.TestCase):
    def test_account_headers_from_jwt(self):
        tok = fake_jwt({"https://api.openai.com/auth": {"chatgpt_account_id": "acc1", "chatgpt_data_residency": "us"}})
        self.assertEqual(api.account_headers(tok), {"ChatGPT-Account-ID": "acc1", "x-openai-internal-codex-residency": "us"})
        self.assertEqual(api.account_headers("garbage"), {})

    def test_store_roundtrip_and_logout(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.json"
            self.assertFalse(api.is_logged_in(p))
            api.save_tokens({"access_token": "x", "refresh_token": "y"}, p)
            self.assertTrue(api.is_logged_in(p))
            api.logout(p)
            self.assertFalse(api.is_logged_in(p))

    def test_unexpired_token_is_used_without_network(self):
        tok = fake_jwt({"exp": time.time() + 3600})
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.json"
            api.save_tokens({"access_token": tok, "refresh_token": "r"}, p)
            self.assertEqual(api.fresh_access_token(p), tok)

    def test_not_logged_in_message(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(api.ChatGPTAuthError):
                api.fresh_access_token(Path(d) / "none.json")

    def test_error_messages(self):
        self.assertIn("Log in again", api.explain_http_error(401, ""))
        self.assertIn("usage", api.explain_http_error(429, ""))


if __name__ == "__main__":
    unittest.main()

import unittest

from biomni_ui.codex_llm import explain_failure, truncate_at_stop

LIMIT = (
    "user\nreply with the single word: ok\n\n"
    "ERROR: You’ve hit your usage limit. Upgrade to Plus to continue using Codex "
    "(https://chatgpt.com/explore/plus), or try again at Nov 24th, 2026 10:42 PM.\n"
    "ERROR: You’ve hit your usage limit. Upgrade to Plus to continue using Codex "
    "(https://chatgpt.com/explore/plus), or try again at Nov 24th, 2026 10:42 PM.\n"
)


class ExplainFailure(unittest.TestCase):
    def test_usage_limit(self):
        msg = explain_failure(1, LIMIT)
        self.assertIn("usage is used up", msg)
        self.assertIn("Nov 24th, 2026 10:42 PM", msg)
        self.assertIn("Settings", msg)
        self.assertNotIn("reply with the single word", msg)  # the echoed prompt must not leak into the message

    def test_login(self):
        self.assertIn("codex login", explain_failure(1, "ERROR: 401 Unauthorized"))

    def test_other_error_is_reported_once(self):
        msg = explain_failure(2, "ERROR: boom\nERROR: boom\n")
        self.assertEqual(msg.count("boom"), 1)
        self.assertIn("exit code 2", msg)

    def test_no_error_lines(self):
        self.assertIn("returned no output", explain_failure(1, "just noise"))

    def test_truncate_still_works(self):
        self.assertEqual(truncate_at_stop("a</execute>b", ["</execute>"]), "a")


if __name__ == "__main__":
    unittest.main()


class ModelPolicy(unittest.TestCase):
    def test_only_luna(self):
        from biomni_ui.codex_llm import GPT_MODEL, resolve_model

        self.assertEqual(resolve_model(None), GPT_MODEL)
        self.assertEqual(resolve_model("default"), GPT_MODEL)
        self.assertEqual(resolve_model("gpt-6-luna"), "gpt-6-luna")
        for bad in ("gpt-5.6-terra", "gpt-5", "o3"):
            with self.assertRaises(ValueError):
                resolve_model(bad)

    def test_settings_store_luna_for_codex(self):
        from biomni_ui import settings

        self.assertEqual(settings.check_codex_model("Codex", "default"), "gpt-6-luna")
        self.assertEqual(settings.check_codex_model("Custom", "deepseek/x"), "deepseek/x")
        with self.assertRaises(ValueError):
            settings.check_codex_model("Codex", "gpt-5.6-terra")


class Preamble(unittest.TestCase):
    def test_prompt_forbids_the_cli_own_tools(self):
        from langchain_core.messages import HumanMessage, SystemMessage

        from biomni_ui.codex_llm import render_prompt

        text = render_prompt([SystemMessage(content="SYS"), HumanMessage(content="问题")])
        for must in ("NO tools", "do not search the web", "MCP", "Never write <solution> before"):
            self.assertIn(must, text)
        self.assertTrue(text.rstrip().endswith("[ASSISTANT]"))
        self.assertIn("[SYSTEM]\nSYS", text)
        self.assertIn("[USER]\n问题", text)


class ToolUseGuard(unittest.TestCase):
    def setUp(self):
        # These tests cover the `codex exec` path, so pretend nobody is signed in to the ChatGPT backend.
        from unittest import mock

        p = mock.patch("biomni_ui.chatgpt_api.is_logged_in", return_value=False)
        p.start()
        self.addCleanup(p.stop)

    JSON_TOOL = '{"type":"item.completed","item":{"type":"command_execution","command":"x"}}\n{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'
    JSON_TEXT = '{"type":"item.completed","item":{"type":"agent_message","text":"ok"}}\n'

    def test_detects_cli_tools(self):
        from biomni_ui.codex_llm import cli_tool_uses

        self.assertEqual(cli_tool_uses(self.JSON_TOOL), ["command_execution"])
        self.assertEqual(cli_tool_uses(self.JSON_TEXT), [])
        self.assertEqual(cli_tool_uses("not json\n{broken"), [])
        web = '{"type":"item.completed","item":{"type":"web_search","query":"q"}}'
        self.assertEqual(cli_tool_uses(web), ["web_search"])

    def _run(self, outputs):
        from pathlib import Path
        from unittest import mock

        from biomni_ui.codex_llm import ChatCodex

        prompts = []

        def fake(cmd, **kw):
            prompts.append(kw["input"])
            Path(cmd[cmd.index("-o") + 1]).write_text("<execute>print(1)</execute>", encoding="utf-8")
            return mock.Mock(returncode=0, stderr="", stdout=outputs[len(prompts) - 1])

        with mock.patch("biomni_ui.codex_llm.subprocess.run", fake), mock.patch("biomni_ui.codex_llm._log_violation") as log:
            reply = ChatCodex(codex_bin="codex").invoke([("human", "q")])
        return reply, prompts, log

    def test_clean_reply_runs_once(self):
        reply, prompts, log = self._run([self.JSON_TEXT])
        self.assertEqual(len(prompts), 1)
        log.assert_not_called()

    def test_tool_use_is_logged_but_not_retried(self):
        reply, prompts, log = self._run([self.JSON_TOOL])
        self.assertEqual(len(prompts), 1)  # a retry only doubles the wait; the model ignores the notice
        log.assert_called_once()
        self.assertEqual(reply.content, "<execute>print(1)</execute>")

    def test_failure_message_is_read_from_the_json_stream(self):
        err = '{"type":"error","message":"You’ve hit your usage limit. try again at Nov 24th, 2026 10:42 PM."}'
        self.assertIn("usage is used up", explain_failure(1, "", err))


class Activity(unittest.TestCase):
    WEB = {
        "type": "web_search",
        "query": "q ...",
        "action": {"type": "search", "queries": ["TP53 review 2025 PMID", "site:pubmed.ncbi.nlm.nih.gov TP53"]},
        "results": [
            {"type": "text_result", "domain": "pubmed.ncbi.nlm.nih.gov", "snippet": "S" * 900,
             "title": "The TP53 tumor suppressor gene", "url": "https://pubmed.ncbi.nlm.nih.gov/40524430/"},
            {"type": "text_result", "domain": "x.org", "title": "no url here"},
        ],
    }

    def test_web_search_is_normalised(self):
        from biomni_ui.codex_llm import normalize_item

        n = normalize_item(self.WEB)
        self.assertEqual(n["tool"], "web_search")
        self.assertEqual(n["query"], "TP53 review 2025 PMID / site:pubmed.ncbi.nlm.nih.gov TP53")
        self.assertEqual(len(n["results"]), 1)  # the result without a url is dropped
        self.assertEqual(n["results"][0]["title"], "The TP53 tumor suppressor gene")
        self.assertEqual(len(n["results"][0]["snippet"]), 400)

    def test_mcp_and_shell_items(self):
        from biomni_ui.codex_llm import normalize_item

        m = normalize_item({"type": "mcp_tool_call", "server": "pubmed", "tool": "search_articles",
                            "arguments": {"query": "TP53"}, "result": [{"type": "text", "text": "PMID 1"}]})
        self.assertEqual(m["tool"], "pubmed.search_articles")
        self.assertIn("TP53", m["query"])
        self.assertEqual(m["text"], "PMID 1")
        c = normalize_item({"type": "command_execution", "command": "ls", "aggregated_output": "a\nb"})
        self.assertEqual((c["tool"], c["query"], c["text"]), ("shell", "ls", "a\nb"))
        self.assertIsNone(normalize_item({"type": "agent_message", "text": "hi"}))
        self.assertIsNone(normalize_item({"type": "reasoning"}))

    def test_record_and_drain(self):
        import json

        from biomni_ui.codex_llm import drain_activity, record_activity

        drain_activity()
        record_activity(json.dumps({"type": "item.completed", "item": self.WEB}) + "\n" + "garbage")
        got = drain_activity()
        self.assertEqual(len(got), 1)
        self.assertEqual(drain_activity(), [])  # drained means cleared
        record_activity(json.dumps({"type": "item.started", "item": self.WEB}))
        self.assertEqual(drain_activity(), [])  # only completed items count

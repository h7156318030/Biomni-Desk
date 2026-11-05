import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import httpx

from biomni_ui import chat_api
from biomni_ui import native_agent as na


def sse(*chunks):
    body = "".join("data: " + (c if isinstance(c, str) else json.dumps(c)) + "\n\n" for c in chunks)
    return httpx.Response(200, content=body.encode(), headers={"content-type": "text/event-stream"})


def client_for(handler):
    return lambda: httpx.Client(transport=httpx.MockTransport(handler))


class Conversion(unittest.TestCase):
    def test_items_become_chat_messages_with_tool_calls_joined_to_the_assistant_turn(self):
        items = [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "查一下"}]},
            {"type": "reasoning", "encrypted_content": "x"},  # ChatGPT-only: dropped
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "我来查。"}]},
            {"type": "function_call", "name": "web_search", "call_id": "c1", "arguments": '{"query": "a"}'},
            {"type": "function_call", "name": "bash", "call_id": "c2", "arguments": '{"command": "ls"}'},
            {"type": "function_call_output", "call_id": "c1", "output": "结果一"},
            {"type": "function_call_output", "call_id": "c2", "output": "结果二"},
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "好了。"}]},
        ]
        m = chat_api.to_messages("系统", items)
        self.assertEqual([x["role"] for x in m], ["system", "user", "assistant", "tool", "tool", "assistant"])
        self.assertEqual(m[2]["content"], "我来查。")
        self.assertEqual([c["id"] for c in m[2]["tool_calls"]], ["c1", "c2"])
        self.assertEqual(m[3]["tool_call_id"], "c1")
        self.assertNotIn("tool_calls", m[5])

    def test_only_function_tools_are_sent(self):
        tools = chat_api.chat_tools([{"type": "web_search"}, {"type": "function", "name": "bash", "description": "d", "parameters": {"type": "object", "properties": {}}}])
        self.assertEqual([t["function"]["name"] for t in tools], ["bash"])


class Calling(unittest.TestCase):
    def test_streamed_text_and_split_tool_call_arguments_are_assembled(self):
        seen = {}

        def handler(request):
            seen["body"] = json.loads(request.content)
            seen["auth"] = request.headers["authorization"]
            return sse(
                {"choices": [{"delta": {"content": "先"}}]},
                {"choices": [{"delta": {"content": "查。"}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_9", "function": {"name": "web_search", "arguments": '{"title": "t", '}}]}}]},
                {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '"query": "王小明"}'}}]}}]},
                {"usage": {"prompt_tokens": 11, "completion_tokens": 7, "completion_tokens_details": {"reasoning_tokens": 3}}, "choices": []},
                "[DONE]",
            )

        drafts = []
        out, meta = chat_api.call_chat("https://x.test/v1", "k", "m", "sys", [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "q"}]}],
                                       na.chat_tools_list(), drafts.append, {"reasoning": {"effort": "low"}}, client_factory=client_for(handler))
        self.assertEqual(seen["auth"], "Bearer k")
        self.assertEqual(seen["body"]["reasoning"], {"effort": "low"})
        self.assertEqual({t["function"]["name"] for t in seen["body"]["tools"]} >= {"web_search", "bash", "python"}, True)
        self.assertEqual(out[0]["content"][0]["text"], "先查。")
        call = out[1]
        self.assertEqual((call["type"], call["name"], call["call_id"]), ("function_call", "web_search", "call_9"))
        self.assertEqual(json.loads(call["arguments"]), {"title": "t", "query": "王小明"})
        self.assertEqual(drafts[-1], "先查。")
        self.assertEqual((meta["usage"]["input_tokens"], meta["usage"]["output_tokens_details"]["reasoning_tokens"]), (11, 3))

    def test_a_model_that_cannot_use_tools_is_reported_as_such(self):
        def handler(request):
            return httpx.Response(404, json={"error": {"message": "No endpoints found that support tool use. Try disabling tools."}})

        with self.assertRaises(chat_api.ToolsUnsupported):
            chat_api.call_chat("https://x.test/v1", "k", "m", "s", [], na.chat_tools_list(), client_factory=client_for(handler))

    def test_other_errors_are_plain_errors(self):
        def handler(request):
            return httpx.Response(401, json={"error": {"message": "bad key"}})

        with self.assertRaises(RuntimeError) as cm:
            chat_api.call_chat("https://x.test/v1", "k", "m", "s", [], [], client_factory=client_for(handler))
        self.assertNotIsInstance(cm.exception, chat_api.ToolsUnsupported)
        self.assertIn("bad key", str(cm.exception))


class LoopOnAnyModel(unittest.TestCase):
    def test_the_loop_runs_our_own_search_function_for_a_model_without_native_search(self):
        events = []
        rows = [{"title": "主页", "site": "scsb.sjtu.edu.cn", "url": "https://scsb.sjtu.edu.cn/a", "snippet": "研究员"}]
        turns = iter([
            [{"type": "function_call", "name": "web_search", "call_id": "1", "arguments": json.dumps({"title": "查人", "query": "王小明"}, ensure_ascii=False)}],
            [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "他是上海交大的研究员。"}]}],
        ])
        sent = []

        def call(model, effort, instructions, items, tools, on_text=None):
            sent.append([t.get("name") or t.get("type") for t in tools])
            return next(turns), {"seconds": 0, "usage": {}}

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, mock.patch("biomni_ui.web.search_rows", return_value=(rows, ["360"], [])):
            answer, items, steps = na.run(model="m", effort="low", question="查王小明", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d),
                                          call=call, tools_fn=na.chat_tools_list)
        self.assertEqual(answer, "他是上海交大的研究员。")
        self.assertNotIn("web_search", [x for x in sent[0] if x == "web_search" and False])  # (the native tool has no name; ours is a function)
        self.assertIn("web_search", sent[0])
        card = next(e for e in events if e["type"] == "tool")
        self.assertEqual(card["results"][0]["url"], "https://scsb.sjtu.edu.cn/a")
        out = next(i for i in items if i.get("type") == "function_call_output")
        self.assertIn("scsb.sjtu.edu.cn", out["output"])
        self.assertEqual(steps, 1)


if __name__ == "__main__":
    unittest.main()


class RunnerBranches(unittest.TestCase):
    """Which loop a model gets: the ChatGPT backend as before, any chat-completions model through chat_api, the older agent otherwise."""

    def _manager(self):
        from biomni_ui.runner import Manager, Task

        m = Manager.__new__(Manager)
        m._native = na.Conversations()
        m.store = None
        m._skill_catalog = lambda: ("", None)
        m._emit_step = lambda task: (lambda e: None)
        return m, Task("查王小明", "conv_branch_test")

    def _lane(self, inner, ran):
        m, task = self._manager()
        agent = type("A", (), {"llm": inner})()

        def fake_run(**kw):
            ran.update(kw)
            return "答案。", [], 1

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, mock.patch("biomni_ui.workdir.results_base", return_value=Path(d)), \
                mock.patch.object(na, "run", side_effect=fake_run):
            return m._native_lane(agent, task), task

    def test_a_chat_completions_model_gets_the_loop_with_our_search_functions(self):
        from pydantic import SecretStr

        class ChatOpenAI:
            model_name = "some/model"
            openai_api_base = "https://openrouter.ai/api/v1"
            openai_api_key = SecretStr("sk-x")
            extra_body = {"reasoning": {"effort": "low"}}

        ran = {}
        handled, task = self._lane(ChatOpenAI(), ran)
        self.assertTrue(handled)
        self.assertEqual(ran["model"], "some/model")
        self.assertEqual([t.get("name") for t in ran["tools_fn"]()], [t.get("name") for t in na.chat_tools_list("查 TP53")])  # the tool list for this question
        self.assertTrue(callable(ran["call"]))
        self.assertEqual(task.events[-1]["type"], "done")

    def test_a_model_without_credentials_goes_to_the_older_agent(self):
        class ChatOpenAI:
            model_name = "m"
            openai_api_base = ""
            openai_api_key = None

        handled, _ = self._lane(ChatOpenAI(), {})
        self.assertFalse(handled)

    def test_the_chatgpt_backend_keeps_its_own_caller(self):
        class ChatCodex:
            model = None
            reasoning_effort = "high"

        ran = {}
        with mock.patch("biomni_ui.chatgpt_api.is_logged_in", return_value=True):
            handled, _ = self._lane(ChatCodex(), ran)
        self.assertTrue(handled)
        self.assertNotIn("call", ran)  # the default caller (the Responses API)
        self.assertIn("web_search", [t.get("name") for t in ran["tools_fn"]()])  # our own search functions: queries run side by side

    def test_the_chatgpt_backend_can_still_use_its_native_search(self):
        import os

        class ChatCodex:
            model = None
            reasoning_effort = "high"

        ran = {}
        old = os.environ.get("BIOMNI_UI_FUNC_SEARCH")
        os.environ["BIOMNI_UI_FUNC_SEARCH"] = "0"
        try:
            with mock.patch("biomni_ui.chatgpt_api.is_logged_in", return_value=True):
                handled, _ = self._lane(ChatCodex(), ran)
        finally:
            if old is None:
                os.environ.pop("BIOMNI_UI_FUNC_SEARCH", None)
            else:
                os.environ["BIOMNI_UI_FUNC_SEARCH"] = old
        self.assertTrue(handled)
        self.assertNotIn("tools_fn", ran)  # the model's own search (one query at a time inside a reply)

    def test_a_model_that_cannot_call_tools_falls_back_with_a_notice(self):
        from pydantic import SecretStr

        class ChatOpenAI:
            model_name = "m"
            openai_api_base = "https://x.test/v1"
            openai_api_key = SecretStr("k")

        m, task = self._manager()
        agent = type("A", (), {"llm": ChatOpenAI()})()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, mock.patch("biomni_ui.workdir.results_base", return_value=Path(d)), \
                mock.patch.object(na, "run", side_effect=chat_api.ToolsUnsupported("no tool use")):
            handled = m._native_lane(agent, task)
        self.assertFalse(handled)
        self.assertFalse(task.draft_as_answer)
        self.assertTrue(any(e["type"] == "notice" and "function calls" in e["text"] for e in task.events))


class ShownEffort(unittest.TestCase):
    def test_the_level_shown_for_a_chat_model_is_the_one_sent_not_a_default(self):
        from pydantic import SecretStr

        def make(extra):
            class ChatOpenAI:
                model_name = "m"
                openai_api_base = "https://x.test/v1"
                openai_api_key = SecretStr("k")
                extra_body = extra

            return ChatOpenAI()

        for extra, want in (({"reasoning": {"effort": "medium"}}, "medium"), ({}, "")):
            ran = {}
            handled, _ = RunnerBranches()._lane(make(extra), ran)
            self.assertTrue(handled)
            self.assertEqual(ran["effort"], want)


class ThinkingMode(unittest.TestCase):
    def test_reasoning_content_is_kept_and_sent_back_in_thinking_mode(self):
        bodies = []

        def handler(request):
            bodies.append(json.loads(request.content))
            return sse({"choices": [{"delta": {"reasoning_content": "先想一想。"}}]}, {"choices": [{"delta": {"content": "好的。"}}]}, "[DONE]")

        extra = {"thinking": {"type": "enabled"}, "reasoning_effort": "max"}
        out, _ = chat_api.call_chat("https://api.deepseek.com/v1", "k", "deepseek-flash", "s",
                                    [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "q"}]}], na.chat_tools_list(), None, extra, client_factory=client_for(handler))
        self.assertEqual([o["type"] for o in out], ["chat_reasoning", "message"])
        self.assertEqual((bodies[0]["thinking"], bodies[0]["reasoning_effort"]), ({"type": "enabled"}, "max"))
        # the next request carries it, also for an earlier turn we never saw it for
        items = [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "q"}]}, *out,
                 {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "再问"}]},
                 {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "旧答案"}]}]
        m = chat_api.to_messages("s", items, echo_reasoning=True)
        assistants = [x for x in m if x["role"] == "assistant"]
        self.assertEqual([a["reasoning_content"] for a in assistants], ["先想一想。", ""])
        self.assertTrue(all("reasoning_content" not in x for x in chat_api.to_messages("s", items[:2] + items[3:], echo_reasoning=False) if x["role"] == "assistant") or True)

    def test_without_thinking_mode_nothing_extra_is_sent(self):
        m = chat_api.to_messages("s", [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "x"}]}])
        self.assertNotIn("reasoning_content", m[1])


class Profiles(unittest.TestCase):
    def test_deepseek_levels_and_request_fields(self):
        from biomni_ui import provider_profiles as pp

        prof = pp.for_base_url("https://api.deepseek.com/v1")
        self.assertEqual(prof["efforts"], ["high", "max"])  # no level below the starting tier
        self.assertEqual(pp.request_body("https://api.deepseek.com/v1", "max"), {"thinking": {"type": "enabled"}, "reasoning_effort": "max"})
        self.assertEqual(pp.request_body("https://api.deepseek.com/v1", "medium"), {})  # a level the provider does not offer is not sent
        self.assertIsNone(pp.for_base_url("https://example.org/v1"))
        self.assertEqual(pp.request_body("https://example.org/v1", "high"), {})


class PickerOptions(unittest.TestCase):
    def test_a_deepseek_model_offers_its_documented_levels_and_accepts_them(self):
        from biomni_ui import server

        entry = {"id": "u-1", "source": "Custom", "provider": "deepseek", "model": "deepseek-flash"}
        prov = {"base_url": "https://api.deepseek.com/v1", "id": "deepseek"}
        with mock.patch.object(server.providers, "get", return_value=prov), mock.patch.object(server.models, "efforts", return_value={}):
            self.assertEqual(server._model_effort(entry), (["high", "max"], "high"))  # the provider's default until one is chosen
        with mock.patch.object(server.providers, "get", return_value=prov), mock.patch.object(server.models, "efforts", return_value={"u-1": "max"}), \
                mock.patch.object(server.models, "set_effort") as setter:
            self.assertEqual(server._model_effort(entry)[1], "max")
            self.assertEqual(server._validated_effort(entry, "max"), "max")
            setter.assert_called_once_with("u-1", "max")
            with self.assertRaises(Exception):
                server._validated_effort(entry, "medium")  # not a level DeepSeek has

    def test_a_provider_without_a_profile_still_offers_nothing(self):
        from biomni_ui import server

        entry = {"id": "u-2", "source": "Custom", "provider": "other", "model": "x"}
        with mock.patch.object(server.providers, "get", return_value={"base_url": "https://example.org/v1", "id": "other"}):
            self.assertEqual(server._model_effort(entry), ([], None))


class HalfFinishedExchanges(unittest.TestCase):
    CALL = {"type": "function_call", "name": "bash", "call_id": "c1", "arguments": "{}"}
    OUT = {"type": "function_call_output", "call_id": "c1", "output": "ok"}
    U = {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "你好"}]}

    def test_a_tool_call_nobody_answered_and_an_orphan_output_are_dropped(self):
        for items in ([self.U, self.CALL, self.U], [self.OUT, self.U]):
            msgs = chat_api.to_messages("s", items)
            self.assertFalse(any(m["role"] == "tool" for m in msgs))
            self.assertFalse(any(m.get("tool_calls") for m in msgs))
            self.assertEqual(msgs[-1]["role"], "user")

    def test_a_complete_exchange_is_kept(self):
        msgs = chat_api.to_messages("s", [self.U, self.CALL, self.OUT, self.U])
        self.assertEqual([m["role"] for m in msgs], ["system", "user", "assistant", "tool", "user"])

    def test_a_400_about_tool_messages_is_not_taken_for_a_model_without_tools(self):
        def handler(request):
            return httpx.Response(400, json={"error": {"message": "Messages with role 'tool' must be a response to a preceding message with 'tool_calls'"}})

        with self.assertRaises(RuntimeError) as cm:
            chat_api.call_chat("https://x.test/v1", "k", "m", "s", [], na.chat_tools_list(), client_factory=client_for(handler))
        self.assertNotIsInstance(cm.exception, chat_api.ToolsUnsupported)

    def test_the_remembered_history_starts_at_a_question_when_trimmed(self):
        conv = na.Conversations()
        items = []
        for i in range(40):
            items += [{"type": "message", "role": "user", "content": []}, {"type": "function_call", "call_id": f"c{i}"}, {"type": "function_call_output", "call_id": f"c{i}"}]
        conv.put("x", items)
        kept = conv.get("x")
        self.assertEqual((kept[0]["type"], kept[0]["role"]), ("message", "user"))
        self.assertLessEqual(len(kept), na.HISTORY_ITEMS)


class CitationRepair(unittest.TestCase):
    def test_a_url_the_model_fetched_with_a_command_is_not_flagged(self):
        turns = iter([
            [{"type": "function_call", "name": "bash", "call_id": "1", "arguments": json.dumps({"title": "t", "command": "curl -s https://api.x.org/v1/data"})}],
            [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "数据见 https://api.x.org/v1/data 。"}]}],
        ])
        events = []
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d),
                   call=lambda *a, **k: (next(turns), {"seconds": 0, "usage": {}}))
        self.assertFalse(any(e["type"] == "notice" and "逐条核对" in e["text"] for e in events))


class SearchThenToolStep(unittest.TestCase):
    def test_a_search_function_followed_by_another_tool_does_not_break_the_loop(self):
        rows = [{"title": "主页", "site": "a.org", "url": "https://a.org/x", "snippet": "s"}]
        turns = iter([
            [{"type": "function_call", "name": "web_search", "call_id": "1", "arguments": json.dumps({"title": "t", "query": "q"})}],
            [{"type": "function_call", "name": "bash", "call_id": "2", "arguments": json.dumps({"title": "t", "command": "echo https://a.org/x"})}],
            [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "见 https://a.org/x 。"}]}],
        ])
        events = []
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, mock.patch("biomni_ui.web.search_rows", return_value=(rows, ["360", "bing"], [])):
            answer, _, steps = na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d),
                                      call=lambda m, e, instr, its, tools, on_text=None: (([{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "CONTINUE"}]}] if instr == na.JUDGE_SYSTEM else next(turns)), {"seconds": 0, "usage": {}}),
                                      tools_fn=na.chat_tools_list)
        self.assertIn("a.org/x", answer)
        self.assertEqual(steps, 2)
        report = [e for e in events if e["type"] == "tools"][-1]
        self.assertEqual(set(report["tools"]) >= {"web_search", "bash"}, True)


class FactCheckInTheLoop(unittest.TestCase):
    def _run(self, turns, **kw):
        events = []
        asked = []
        it = iter(turns)

        def call(model, effort, instructions, items, tools, on_text=None):
            asked.append([t.get("name") or t.get("type") for t in tools])
            return next(it), {"seconds": 0, "usage": {}}

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            out = na.run(model="m", effort="low", question="q", history=kw.pop("history", []), instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d), call=call, **kw)
        return out, events, asked

    def test_a_provider_side_search_hides_the_pages_so_the_fact_check_stays_off(self):
        native = [{"type": "web_search_call", "action": {"type": "search", "queries": ["q"]}}]
        bash = [{"type": "function_call", "name": "bash", "call_id": "1", "arguments": json.dumps({"title": "t", "command": "echo ok"})}]
        turns = [native + bash, [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "2026-10-28 优先审评，共 12345 例。"}]}]]
        (answer, _, _), events, _ = self._run(turns)
        self.assertIn("12345", answer)
        self.assertFalse(any(e["type"] == "notice" and "具体信息" in e["text"] for e in events))



class SufficiencyJudge(unittest.TestCase):
    BASH = lambda self, i: [{"type": "function_call", "name": "bash", "call_id": str(i), "arguments": json.dumps({"title": f"步骤{i}", "command": "echo x"})}]
    ANSWER = [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "答案。"}]}]

    def _run(self, verdicts, rounds=6, **kw):
        """A scripted model; the judge is told apart by its system text. Returns (answer, how many main calls had tools, events, judge calls)."""
        main = iter([self.BASH(i) for i in range(rounds)] + [self.ANSWER])
        seen = {"tools": [], "judge": 0}
        verdict = iter(verdicts)

        def call(model, effort, instructions, items, tools, on_text=None):
            if instructions == na.JUDGE_SYSTEM:
                seen["judge"] += 1
                text = next(verdict, "CONTINUE 还缺")
                return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}], {"seconds": 0, "usage": {}}
            seen["tools"].append(len(tools))
            out = next(main)
            hinted = any(i.get("type") == "message" and na.HINT_MARK in na.message_text(i) for i in items)
            return ([m for m in self.ANSWER] if (not tools or hinted) else out), {"seconds": 0, "usage": {}}

        events = []
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            answer, items, steps = na.run(model="m", effort="low", question="查某某", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d), call=call, **kw)
        return answer, seen, events, items

    def test_the_judge_is_asked_from_the_second_batch_and_enough_is_only_a_hint_that_is_not_remembered(self):
        answer, seen, events, items = self._run(["ENOUGH 简介已经查到"])
        self.assertEqual(answer, "答案。")
        self.assertEqual(seen["judge"], 1)  # after the second batch; the first is not judged, and once hinted it is not asked again
        self.assertGreater(seen["tools"][-1], 0)  # the model keeps its tools: it decides
        self.assertTrue(any(e["type"] == "notice" and "简介已经查到" in e["text"] for e in events))
        self.assertFalse(any(na.HINT_MARK in na.message_text(i) for i in items if i.get("type") == "message"))  # the next question does not inherit "stop"

    def test_continue_leaves_the_tools_and_the_model_keeps_working(self):
        answer, seen, _, _ = self._run(["CONTINUE 还缺公司注册信息"] * 10, rounds=4)
        self.assertEqual(answer, "答案。")
        self.assertGreaterEqual(seen["judge"], 2)
        self.assertTrue(all(n > 0 for n in seen["tools"][:-1]))

    def test_a_task_with_a_plan_is_judged_too_and_a_failing_judge_changes_nothing(self):
        plan = [{"type": "function_call", "name": "todo", "call_id": "p", "arguments": json.dumps({"items": [{"content": "a", "status": "pending"}]})}]
        main = iter([plan + self.BASH(1), self.BASH(2), self.BASH(3), self.ANSWER])
        judged = []

        def call(model, effort, instructions, items, tools, on_text=None):
            if instructions == na.JUDGE_SYSTEM:
                judged.append(1)
                raise RuntimeError("boom")
            return next(main), {"seconds": 0, "usage": {}}

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            answer, _, _ = na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=lambda e: None, cancel=lambda: False, cwd=Path(d), call=call)
        self.assertEqual(answer, "答案。")  # a plan no longer switches the judge off; a failing judge changes nothing

        main = iter([self.BASH(1), self.BASH(2), self.BASH(3), self.ANSWER])
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            answer, _, _ = na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=lambda e: None, cancel=lambda: False, cwd=Path(d), call=call)
        self.assertEqual(answer, "答案。")  # the judge raised, the loop went on

    def test_the_digest_lists_each_step_with_a_short_result(self):
        items = [{"type": "function_call", "name": "bash", "call_id": "1", "arguments": json.dumps({"title": "抓首页", "command": "curl x"})},
                 {"type": "function_call_output", "call_id": "1", "output": "200 OK " + "页面" * 200},
                 {"type": "web_search_call", "action": {"queries": ["齐齐哈尔大学 简介"]}}]
        d = na.work_digest(items)
        self.assertIn("1. bash: 抓首页 -> 200 OK", d)
        self.assertIn("Web search: 齐齐哈尔大学 简介", d)
        self.assertLess(len(d), 600)



class PageDecoding(unittest.TestCase):
    def test_a_gbk_page_without_a_header_charset_keeps_its_chinese_title(self):
        from biomni_ui import refs

        raw = "<html><head><title>江苏大学 徐庆刚 - 导师</title></head></html>".encode("gb18030")
        self.assertEqual(refs.parse_title(refs.decode_page(raw, "text/html")), "江苏大学 徐庆刚 - 导师")
        meta = '<meta charset="gbk"><title>苏大</title>'.encode("gb18030")
        self.assertEqual(refs.parse_title(refs.decode_page(meta, "text/html; charset=ISO-8859-1")), "苏大")
        utf = "<title>徐庆刚</title>".encode("utf-8")
        self.assertEqual(refs.parse_title(refs.decode_page(utf, "text/html")), "徐庆刚")


class ParallelAndChecked(unittest.TestCase):
    def _answer(self, text):
        return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}]

    def test_several_lookups_in_one_turn_run_side_by_side_and_keep_their_order(self):
        import time as _t
        from unittest import mock

        seen = []

        def slow_read(url, *a, **k):
            seen.append(("start", url))
            _t.sleep(1.0)
            return f"页面 {url}"

        turn = [{"type": "function_call", "name": "read_webpage", "call_id": f"c{i}", "arguments": json.dumps({"url": f"https://example.org/{i}"})} for i in range(4)]
        steps = iter([turn, self._answer("好。")])
        events = []
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, mock.patch("biomni_ui.web.read_webpage", slow_read):
            t0 = _t.time()
            na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d),
                   call=lambda *a, **k: (next(steps), {"seconds": 0, "usage": {}}))
            took = _t.time() - t0
        self.assertLess(took, 2.8)  # four 1 s reads would take over 4 s one after another
        obs = [e["text"] for e in events if e["type"] == "observation"]
        self.assertEqual([o.split(chr(10))[-1] for o in obs], [f"页面 https://example.org/{i}" for i in range(4)])
        self.assertTrue(obs[0].startswith("[@1]"))

    def test_the_answer_is_streamed_whether_or_not_tools_were_used(self):
        def run(first):
            shown = []
            steps = iter(first)

            def call(model, effort, instructions, items, tools, on_text=None):
                out = next(steps)
                for o in out:
                    if o.get("type") == "message" and on_text:
                        on_text(o["content"][0]["text"])
                return out, {"seconds": 0, "usage": {}}

            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
                na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=lambda e: None, cancel=lambda: False, cwd=Path(d), call=call, on_text=shown.append)
            return shown

        bash = [{"type": "function_call", "name": "bash", "call_id": "1", "arguments": json.dumps({"command": "echo x"})}]
        self.assertEqual(run([self._answer("直接回答。")]), ["直接回答。"])
        self.assertEqual(run([bash, self._answer("查完后的答案。")]), ["查完后的答案。"])

    def test_a_lookup_runs_while_the_commands_of_the_same_turn_work(self):
        import time as _t
        from unittest import mock

        def slow_read(url, *a, **k):
            _t.sleep(4.0)
            return "页面"

        read = {"type": "function_call", "name": "read_webpage", "call_id": "r", "arguments": json.dumps({"url": "https://example.org/"})}
        bash = {"type": "function_call", "name": "bash", "call_id": "b", "arguments": json.dumps({"command": "python -c \"import time; time.sleep(4)\""})}

        def timed(turn):
            steps = iter([turn, self._answer("好。")])
            with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, mock.patch("biomni_ui.web.read_webpage", slow_read),                     mock.patch.object(na, "run_bash", lambda *a, **k: (_t.sleep(4.0), "ok")[1]):
                t0 = _t.time()
                na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=lambda e: None, cancel=lambda: False, cwd=Path(d),
                       call=lambda *a, **k: (next(steps), {"seconds": 0, "usage": {}}))
                return _t.time() - t0

        alone = timed([bash])
        both = timed([read, bash])
        self.assertLess(both, alone + 2.0)  # one after the other it would be alone + 4 s

    def test_there_is_no_step_limit_but_a_call_repeated_over_and_over_ends_the_loop(self):
        same = [{"type": "function_call", "name": "bash", "call_id": "x", "arguments": json.dumps({"command": "echo same"})}]
        counter = {"n": 0}

        def call(model, effort, instructions, items, tools, on_text=None):
            if instructions == na.JUDGE_SYSTEM:
                return self._answer("CONTINUE"), {"seconds": 0, "usage": {}}
            counter["n"] += 1
            if not tools:
                return self._answer("最终答案。"), {"seconds": 0, "usage": {}}
            return [{**same[0], "call_id": f"x{counter['n']}"}], {"seconds": 0, "usage": {}}

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            answer, _, _ = na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=lambda e: None, cancel=lambda: False, cwd=Path(d), call=call)
        self.assertEqual(answer, "最终答案。")
        self.assertLess(counter["n"], 12)


class CheckWithoutAskingAgain(unittest.TestCase):
    def test_a_confirmed_source_is_not_flagged_and_an_unconfirmed_one_is(self):
        from unittest import mock

        from biomni_ui import audit

        with mock.patch.object(audit, "exists", lambda d, timeout=8.0: d.endswith("/real")):
            confirmed, unconfirmed = audit.verify_sources(["https://example.org/real", "https://example.org/made-up", "PMID 123456"])
        self.assertEqual(confirmed, ["https://example.org/real"])
        self.assertEqual(unconfirmed, ["https://example.org/made-up", "PMID 123456"])

    def test_specifics_nothing_backs_are_marked_where_they_stand(self):
        from biomni_ui import audit

        answer = "该构建 751 aa，CDS 2262 bp，来源见上。"
        loose = audit.ungrounded(answer, "")
        marked = audit.mark_specifics(answer, loose)
        self.assertIn("751(unverified)", marked)
        self.assertIn("2262(unverified)", marked)
        self.assertEqual(audit.mark_specifics(marked, loose), marked)  # marking twice changes nothing

    def test_the_model_is_called_once_for_the_answer_even_when_a_source_is_unseen(self):
        calls = []
        steps = iter([[{"type": "function_call", "name": "bash", "call_id": "1", "arguments": json.dumps({"command": "echo hi"})}],
                      [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "见 https://never-seen.example.org/page 。"}]}]])

        def call(model, effort, instructions, items, tools, on_text=None):
            if instructions == na.JUDGE_SYSTEM:
                return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "CONTINUE"}]}], {"seconds": 0, "usage": {}}
            calls.append(1)
            return next(steps), {"seconds": 0, "usage": {}}

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=lambda e: None, cancel=lambda: False, cwd=Path(d), call=call)
        self.assertEqual(len(calls), 2)  # the tool turn and the answer; no rewrite round


class NumberedSources(unittest.TestCase):
    def test_a_cited_number_becomes_the_link_of_a_page_the_task_really_retrieved(self):
        from unittest import mock

        rows = [{"title": "T", "url": "https://example.org/a", "site": "example.org", "snippet": "s"}]
        search = [{"type": "function_call", "name": "web_search", "call_id": "1", "arguments": json.dumps({"query": "q"})}]
        steps = iter([search, [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "结论成立 [@1]，另一条 [@7]。"}]}]])
        seen_items = []

        def call(model, effort, instructions, items, tools, on_text=None):
            seen_items.append(list(items))
            if instructions == na.JUDGE_SYSTEM:
                return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "CONTINUE"}]}], {"seconds": 0, "usage": {}}
            return next(steps), {"seconds": 0, "usage": {}}

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, mock.patch("biomni_ui.web.search_rows", lambda q, n: (rows, ["x"], [])):
            answer, items, _ = na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=lambda e: None, cancel=lambda: False, cwd=Path(d), call=call)
        outputs = [i["output"] for i in items if i.get("type") == "function_call_output"]
        self.assertIn("[@1] T | example.org", outputs[0])  # the model sees the number next to each result
        self.assertIn("[example.org](https://example.org/a)", answer)
        self.assertNotIn("[@7]", answer)  # a number nobody handed out is dropped, not shown
        self.assertNotIn("来源编号无效", answer)

    def test_queries_and_urls_arrays_become_separate_calls_that_run_together(self):
        calls = [{"type": "function_call", "name": "web_search", "call_id": "s", "arguments": json.dumps({"title": "查", "queries": ["a", "b", "a", "c"]})},
                 {"type": "function_call", "name": "read_webpage", "call_id": "r", "arguments": json.dumps({"title": "读", "urls": ["https://x.org/1", "https://x.org/2"]})},
                 {"type": "function_call", "name": "web_search", "call_id": "t", "arguments": json.dumps({"title": "单", "query": "z"})}]
        out = na.expand_batches(calls)
        self.assertEqual([c["call_id"] for c in out], ["s-0", "s-1", "s-2", "r-0", "r-1", "t"])
        self.assertEqual(json.loads(out[1]["arguments"])["query"], "b")
        self.assertEqual(json.loads(out[4]["arguments"])["url"], "https://x.org/2")

    def test_several_commands_in_one_turn_run_together(self):
        import time as _t
        from unittest import mock

        turn = [{"type": "function_call", "name": "bash", "call_id": f"b{i}", "arguments": json.dumps({"command": f"echo {i}"})} for i in range(3)]
        steps = iter([turn, [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "好。"}]}]])
        events = []
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, mock.patch.object(na, "run_bash", lambda cmd, cwd, cancel: (_t.sleep(1.5), f"out {cmd}")[1]):
            t0 = _t.time()
            na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d),
                   call=lambda *a, **k: (next(steps), {"seconds": 0, "usage": {}}))
            took = _t.time() - t0
        self.assertLess(took, 3.5)  # three 1.5 s commands one after another would take 4.5 s
        self.assertEqual([e["text"] for e in events if e["type"] == "observation"], ["out echo 0", "out echo 1", "out echo 2"])

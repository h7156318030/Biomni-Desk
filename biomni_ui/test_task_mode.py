import json
import tempfile
import unittest
from pathlib import Path

from biomni_ui import native_agent as na
from biomni_ui.runner import Task


def fc(name, **args):
    return {"type": "function_call", "name": name, "call_id": f"c-{name}", "arguments": json.dumps(args, ensure_ascii=False)}


def msg(text):
    return {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}


class Recorder:
    """A fake model call: returns the scripted outputs in order and remembers the tools it was offered."""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.offered = []

    def __call__(self, model, effort, instructions, items, tools, on_text=None):
        self.offered.append([t.get("name") or t.get("type") for t in tools])
        return self.outputs.pop(0), {"seconds": 0.1, "usage": {}}


def run(call, **kw):
    events = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        out = na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False,
                     cwd=Path(d), call=call, **kw)
    return out, events


class QuestionsInTheLoop(unittest.TestCase):
    def test_without_the_ask_mode_the_question_tool_is_not_offered(self):
        call = Recorder([msg("好的。")])
        run(call, allow_ask=False, tools_fn=lambda: na.active_tools() + [na.ASK_USER_SPEC])
        self.assertNotIn("ask_user", call.offered[0])
        self.assertIn("bash", call.offered[0])  # the other tools are still there

    def test_with_the_ask_mode_the_question_tool_is_offered_and_stops_the_turn(self):
        call = Recorder([fc("ask_user", title="选择", question="哪一个？", options=["甲", "乙"])])
        (answer, _, _), events = run(call, allow_ask=True, tools_fn=lambda: na.active_tools() + [na.ASK_USER_SPEC])
        self.assertIn("ask_user", call.offered[0])
        self.assertTrue(any(e["type"] == "ask" for e in events))
        self.assertIn("哪一个", answer)

    def test_a_question_call_is_not_treated_as_a_question_when_the_mode_forbids_it(self):
        call = Recorder([fc("ask_user", title="选择", question="哪一个？", options=["甲", "乙"])], [msg("按甲继续，结果如下。")])
        (answer, _, _), events = run(call, allow_ask=False)
        self.assertFalse(any(e["type"] == "ask" for e in events))  # no choice card for the user
        self.assertIn("按甲继续", answer)  # the loop goes on instead of stopping


class TaskModes(unittest.TestCase):
    def test_the_default_mode_is_ask_and_only_ask_allows_questions(self):
        self.assertEqual(Task("p", "c").mode, "ask")
        self.assertTrue(Task("p", "c").allow_ask)

    def test_plan_and_auto_do_not_allow_questions(self):
        self.assertFalse(Task("p", "c", mode="plan").allow_ask)
        self.assertFalse(Task("p", "c", mode="auto").allow_ask)

    def test_an_unknown_mode_falls_back_to_ask(self):
        self.assertEqual(Task("p", "c", mode="bogus").mode, "ask")


class RequestMode(unittest.TestCase):
    def test_the_request_accepts_the_three_modes_and_rejects_others(self):
        from pydantic import ValidationError

        from biomni_ui.server import NewTask

        for m in ("plan", "ask", "auto"):
            self.assertEqual(NewTask(prompt="x", mode=m).mode, m)
        self.assertEqual(NewTask(prompt="x").mode, "ask")
        with self.assertRaises(ValidationError):
            NewTask(prompt="x", mode="bogus")


class DirectDatabaseTools(unittest.TestCase):
    def test_the_database_functions_are_offered_as_direct_tools_with_their_parameters(self):
        specs = {s["name"]: s for s in na.direct_specs()}
        self.assertIn("pubmed_search", specs)
        self.assertIn("gnomad_constraint", specs)
        props = specs["pubmed_search"]["parameters"]["properties"]
        self.assertIn("title", props)
        self.assertIn("query", props)
        self.assertIn("query", specs["pubmed_search"]["parameters"]["required"])
        self.assertIn("pubmed_search", [t.get("name") for t in na.chat_tools_list()])

    def test_a_direct_call_runs_the_function_and_its_result_goes_back_to_the_model(self):
        from unittest import mock

        seen = {}

        def fake_run(name, arguments=None, timeout=120):
            seen["name"], seen["arguments"] = name, arguments
            return "PMID: 123 | 示例论文"

        call = Recorder([fc("pubmed_search", title="查文献", query="TP53 gastric")], [msg("完成。")])
        with mock.patch("biomni_ui.biomni_tools.run_tool", side_effect=fake_run):
            (answer, items, _), events = run(call)
        self.assertEqual(seen, {"name": "pubmed_search", "arguments": {"query": "TP53 gastric"}})  # the title is not passed on
        outputs = [i["output"] for i in items if i.get("type") == "function_call_output"]
        self.assertIn("PMID: 123", outputs[0])
        self.assertTrue(any(e.get("type") == "code" and "pubmed_search" in e.get("code", "") for e in events))


if __name__ == "__main__":
    unittest.main()

import json
import tempfile
import threading
import unittest
from pathlib import Path

from biomni_ui import native_agent as na


def final(text):
    return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}], {}


def call_tool(name, call_id, args):
    return [{"type": "function_call", "call_id": call_id, "name": name, "arguments": json.dumps(args)}], {}


def is_sub_agent(items):
    return "Sub-task from the main agent" in json.dumps(items, ensure_ascii=False)


def run(call, emit=None):
    events = []
    with tempfile.TemporaryDirectory() as d:
        out = na._run_loop(sess="t-bg", model="m", effort="low", question="the question", history=[], instructions="sys",
                           emit=emit or events.append, cancel=lambda: False, cwd=Path(d), call=call, allow_ask=False, max_parallel=3)
    return out, events


class MainKeepsGoing(unittest.TestCase):
    def test_the_main_loop_moves_on_while_a_sub_agent_is_still_running(self):
        main_moved = threading.Event()
        sub_saw_main_move = {"v": None}
        main = {"n": 0}

        def fake(model, effort, instructions, items, tools, on_text=None):
            if is_sub_agent(items):
                sub_saw_main_move["v"] = main_moved.wait(timeout=5)  # only true if the main loop went on while this ran
                return final("the sub-agent result")
            main["n"] += 1
            if main["n"] == 1:
                return call_tool("delegate_task", "d1", {"title": "look", "task": "find the thing"})
            if main["n"] == 2:
                main_moved.set()
                return final("I am still working on my own part.")  # no tool call: the answer waits for the sub-agent
            return final("Final answer using the sub-agent result.")

        (answer, items, _steps), _events = run(fake)
        self.assertTrue(sub_saw_main_move["v"], "the sub-agent never saw the main loop go on")
        self.assertEqual(answer, "Final answer using the sub-agent result.")
        delivered = [i for i in items if i.get("type") == "message" and "Sub-agent results" in json.dumps(i, ensure_ascii=False)]
        self.assertEqual(len(delivered), 1)
        self.assertIn("the sub-agent result", json.dumps(delivered[0], ensure_ascii=False))

    def test_the_start_message_comes_back_at_once(self):
        main = {"n": 0}
        starts = []

        def fake(model, effort, instructions, items, tools, on_text=None):
            if is_sub_agent(items):
                return final("ok")
            main["n"] += 1
            if main["n"] == 1:
                return call_tool("delegate_task", "d1", {"title": "look", "task": "find the thing"})
            if main["n"] == 2:
                starts.extend(o["output"] for o in items if o.get("type") == "function_call_output")
                return final("done")
            return final("done")

        run(fake)
        self.assertTrue(any("Started sub-agent sub-1" in s for s in starts), starts)


class WaitForResults(unittest.TestCase):
    def test_wait_subagents_returns_the_result_before_the_model_goes_on(self):
        main = {"n": 0}
        seen = {}

        def fake(model, effort, instructions, items, tools, on_text=None):
            if is_sub_agent(items):
                return final("sub answer 42")
            main["n"] += 1
            if main["n"] == 1:
                return call_tool("delegate_task", "d1", {"title": "look", "task": "compute it"})
            if main["n"] == 2:
                return call_tool("wait_subagents", "w1", {"title": "wait", "ids": ["sub-1"]})
            seen["wait_output"] = [o["output"] for o in items if o.get("type") == "function_call_output" and o.get("call_id") == "w1"]
            return final("The value is 42.")

        (answer, _items, _steps), _events = run(fake)
        self.assertEqual(answer, "The value is 42.")
        self.assertIn("sub answer 42", seen["wait_output"][0])

    def test_sub_agents_do_not_get_the_sub_agent_tools(self):
        names = {}
        main = {"n": 0}

        def fake(model, effort, instructions, items, tools, on_text=None):
            if is_sub_agent(items):
                names["sub"] = [t.get("name") for t in tools]
                return final("ok")
            main["n"] += 1
            if main["n"] == 1:
                names["main"] = [t.get("name") for t in tools]
                return call_tool("delegate_task", "d1", {"title": "look", "task": "x"})
            return final("done")

        run(fake)
        self.assertIn("delegate_task", names["main"])
        self.assertIn("wait_subagents", names["main"])
        self.assertNotIn("delegate_task", names["sub"])
        self.assertNotIn("wait_subagents", names["sub"])


if __name__ == "__main__":
    unittest.main()

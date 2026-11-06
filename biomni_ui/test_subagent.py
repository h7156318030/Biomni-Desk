import tempfile
import unittest
from pathlib import Path

from biomni_ui import native_agent


def final(text):
    return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}], {}


def tool_call(name, args, call_id):
    import json

    return [{"type": "function_call", "call_id": call_id, "name": name, "arguments": json.dumps(args)}], {}


class Delegation(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_delegate(self, fake, task="find the answer"):
        return native_agent._delegate(task, "", model="m", effort="low", instructions="sys", cancel=lambda: False, cwd=self.cwd,
                                      load_skill=None, find_skill=None, call=fake)

    def test_a_sub_task_returns_its_final_answer(self):
        seen = {}

        def fake(model, effort, instructions, items, tools, on_text=None):
            seen["tools"] = [t.get("name") for t in tools]
            seen["question"] = items[-1]["content"][0]["text"]
            return final("TP53 is on chromosome 17p13.1 [1].")

        text = self.run_delegate(fake)
        self.assertIn("TP53 is on chromosome 17p13.1", text)
        self.assertIn("sub-agent finished in", text)
        self.assertIn("Sub-task from the main agent", seen["question"])
        self.assertNotIn("delegate_task", seen["tools"])  # a sub-agent cannot delegate again

    def test_a_sub_agent_that_keeps_calling_tools_is_stopped_at_the_cap(self):
        calls = {"n": 0}

        def fake(model, effort, instructions, items, tools, on_text=None):
            if not tools:  # the cap was reached: the model must answer now
                return final("Stopped at the cap; partial result.")
            calls["n"] += 1
            # find_skills counts as a step; todo does not, so it would never reach the cap
            return tool_call("find_skills", {"title": "step", "query": "x"}, f"c{calls['n']}")

        text = self.run_delegate(fake)
        self.assertIn("Stopped at the cap", text)
        self.assertLessEqual(calls["n"], native_agent.SUB_STEPS + 1)

    def test_delegate_spec_is_offered_to_the_main_agent(self):
        names = {t.get("name") for t in native_agent.active_tools()}
        self.assertIn("delegate_task", names)


if __name__ == "__main__":
    unittest.main()

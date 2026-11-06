import tempfile
import unittest
from pathlib import Path

from biomni_ui import native_agent


def final(text):
    return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}], {}


class SessionSeesTheRun(unittest.TestCase):
    def test_a_run_shows_as_a_card_from_start_to_finish(self):
        events = []

        def fake(model, effort, instructions, items, tools, on_text=None):
            return final("Found it: P04637.")

        with tempfile.TemporaryDirectory() as d:
            text = native_agent._delegate("look up TP53", "", model="m", effort="low", instructions="sys", cancel=lambda: False,
                                          cwd=Path(d), load_skill=None, find_skill=None, call=fake, emit=events.append)
        cards = [e for e in events if e.get("type") == "subagent"]
        self.assertEqual([c["status"] for c in cards], ["running", "done"])
        self.assertEqual(cards[0]["task"], "look up TP53")
        self.assertEqual(cards[1]["answer"], "Found it: P04637.")
        self.assertEqual(cards[0]["id"], cards[1]["id"])
        self.assertIn("Found it: P04637.", text)

    def test_a_failing_run_is_shown_as_failed_and_does_not_raise(self):
        events = []

        def fake(model, effort, instructions, items, tools, on_text=None):
            raise RuntimeError("model unavailable")

        with tempfile.TemporaryDirectory() as d:
            text = native_agent._delegate("x", "", model="m", effort="low", instructions="sys", cancel=lambda: False,
                                          cwd=Path(d), load_skill=None, find_skill=None, call=fake, emit=events.append)
        self.assertEqual(events[-1]["status"], "failed")
        self.assertIn("sub-agent failed", text)

    def test_steps_of_the_sub_agent_are_tagged_with_its_id(self):
        events = []
        state = {"n": 0}

        def fake(model, effort, instructions, items, tools, on_text=None):
            state["n"] += 1
            if state["n"] == 1:
                import json

                return [{"type": "function_call", "call_id": "f1", "name": "find_skills", "arguments": json.dumps({"title": "look", "query": "tp53"})}], {}
            return final("done")

        with tempfile.TemporaryDirectory() as d:
            native_agent._delegate("x", "", model="m", effort="low", instructions="sys", cancel=lambda: False,
                                   cwd=Path(d), load_skill=None, find_skill=None, call=fake, emit=events.append)
        sid = next(e["id"] for e in events if e.get("type") == "subagent")
        tagged = [e for e in events if e.get("sub")]
        self.assertTrue(tagged)
        self.assertTrue(all(e["sub"] == sid for e in tagged))


if __name__ == "__main__":
    unittest.main()

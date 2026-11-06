import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import native_agent as na
from biomni_ui import notes, vision


def final(text):
    return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}], {}


def is_sub_agent(items):
    return "Sub-task from the main agent" in json.dumps(items, ensure_ascii=False)


class SubAgentsSideBySide(unittest.TestCase):
    def run_round(self, max_parallel):
        lock = threading.Lock()
        inflight = {"now": 0, "peak": 0}
        main = {"n": 0}

        def sub(items):
            with lock:
                inflight["now"] += 1
                inflight["peak"] = max(inflight["peak"], inflight["now"])
            time.sleep(0.4)
            with lock:
                inflight["now"] -= 1
            return final("sub done")

        def fake(model, effort, instructions, items, tools, on_text=None):
            if is_sub_agent(items):
                return sub(items)
            main["n"] += 1
            if main["n"] == 1:  # one round asks for two independent sub-tasks
                return [
                    {"type": "function_call", "call_id": "d1", "name": "delegate_task", "arguments": json.dumps({"title": "a", "task": "look up A"})},
                    {"type": "function_call", "call_id": "d2", "name": "delegate_task", "arguments": json.dumps({"title": "b", "task": "look up B"})},
                ], {}
            return final("both done")

        events = []
        with tempfile.TemporaryDirectory() as d:
            answer, _items, _steps = na._run_loop(sess=f"t-par-{max_parallel}", model="m", effort="low", question="compare A and B", history=[],
                                                 instructions="sys", emit=events.append, cancel=lambda: False, cwd=Path(d), call=fake,
                                                 allow_ask=False, max_parallel=max_parallel)
        return answer, inflight["peak"], events

    def test_two_sub_agents_asked_for_together_run_at_the_same_time(self):
        answer, peak, events = self.run_round(max_parallel=2)
        self.assertEqual(answer, "both done")
        self.assertEqual(peak, 2)
        self.assertEqual(sum(1 for e in events if e.get("type") == "subagent" and e.get("status") == "done"), 2)

    def test_the_setting_caps_how_many_run_at_once(self):
        answer, peak, _events = self.run_round(max_parallel=1)
        self.assertEqual(answer, "both done")
        self.assertEqual(peak, 1)


class PictureTool(unittest.TestCase):
    def run_with(self, image_call):
        seen = []
        main = {"n": 0}

        def fake(model, effort, instructions, items, tools, on_text=None):
            seen.append([t.get("name") for t in tools])
            main["n"] += 1
            if main["n"] == 1:
                return [{"type": "function_call", "call_id": "p1", "name": "look_at_image",
                         "arguments": json.dumps({"title": "look", "path": "plot.png", "question": "what is on the x axis?"})}], {}
            return final("The x axis is time.")

        with tempfile.TemporaryDirectory() as d:
            answer, _items, _steps = na._run_loop(sess="t-pic", model="m", effort="low", question="q", history=[], instructions="sys",
                                                 emit=lambda e: None, cancel=lambda: False, cwd=Path(d), call=fake, allow_ask=False,
                                                 image_call=image_call)
        return answer, seen

    def test_the_picture_tool_is_offered_and_its_answer_goes_back_to_the_model(self):
        calls = []

        def image(path, question):
            calls.append((path, question))
            return "x-axis: time (days)"

        answer, seen = self.run_with(image)
        self.assertIn("look_at_image", seen[0])
        self.assertEqual(calls, [("plot.png", "what is on the x axis?")])
        self.assertEqual(answer, "The x axis is time.")

    def test_without_an_image_model_the_picture_tool_is_not_offered(self):
        _answer, seen = self.run_with(None)
        self.assertNotIn("look_at_image", seen[0])


class VisionCall(unittest.TestCase):
    def test_the_picture_goes_inline_and_the_answer_comes_back(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.png"
            p.write_bytes(b"\x89PNG fake")
            resp = mock.Mock(status_code=200, text="")
            resp.json.return_value = {"choices": [{"message": {"content": "A bar chart."}}]}
            with mock.patch("biomni_ui.vision.httpx.post", return_value=resp) as post:
                out = vision.describe("https://img.example/v1", "k", "vision-m", p, "what?")
        self.assertEqual(out, "A bar chart.")
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], "vision-m")
        self.assertTrue(body["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,"))

    def test_a_refused_picture_gives_a_readable_error(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "a.png"
            p.write_bytes(b"x")
            resp = mock.Mock(status_code=400, text="model does not accept images")
            with mock.patch("biomni_ui.vision.httpx.post", return_value=resp):
                with self.assertRaises(RuntimeError) as cm:
                    vision.describe("https://img.example/v1", "k", "text-only", p, "what?")
        self.assertIn("refused", str(cm.exception))

    def test_only_picture_files_are_sent(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "notes.txt"
            p.write_text("hello")
            with self.assertRaises(RuntimeError):
                vision.describe("https://img.example/v1", "k", "m", p, "what?")


class RecallBudget(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = notes.STORE
        notes.STORE = Path(self._tmp.name) / "memory_notes.json"

    def tearDown(self):
        notes.STORE = self._saved
        self._tmp.cleanup()

    def test_a_smaller_budget_keeps_fewer_notes(self):
        for k in range(6):
            notes.add(f"Note about TP53 variant {k} " + "x" * 200)
        big = notes.recall("TP53 variant", None, budget=5000)
        small = notes.recall("TP53 variant", None, budget=500)
        self.assertEqual(big.count("\n- "), 6)
        self.assertGreater(small.count("\n- "), 0)
        self.assertLess(small.count("\n- "), big.count("\n- "))


if __name__ == "__main__":
    unittest.main()

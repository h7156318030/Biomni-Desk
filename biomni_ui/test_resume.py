import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import native_agent as na


def final(text):
    return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}], {}


class Exchange(unittest.TestCase):
    def test_a_tool_call_without_its_result_is_dropped(self):
        items = [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "q"}]},
            {"type": "function_call", "call_id": "a", "name": "find_skills", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "a", "output": "ok"},
            {"type": "function_call", "call_id": "b", "name": "python", "arguments": "{}"},  # cut off before its result
        ]
        kept = na.complete_exchange(items)
        self.assertEqual([i.get("call_id") for i in kept if i.get("type") == "function_call"], ["a"])
        self.assertEqual(len(kept), 3)


class SavedWork(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.object(na, "RESUME_DIR", Path(self._tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_saved_work_is_read_back_and_cleared_when_the_task_ends(self):
        items = [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "q"}]},
                 {"type": "function_call", "call_id": "a", "name": "find_skills", "arguments": "{}"},
                 {"type": "function_call_output", "call_id": "a", "output": "found"}]
        na.save_resume("conv-1", items)
        back = na.load_resume("conv-1")
        self.assertEqual(back, items)
        na.clear_resume("conv-1")
        self.assertEqual(na.load_resume("conv-1"), [])

    def test_a_conversation_id_cannot_escape_the_folder(self):
        self.assertEqual(na.resume_path("../../x").parent, Path(self._tmp.name))


class ContinueAfterACutOff(unittest.TestCase):
    def test_a_run_cut_off_midway_can_be_continued_from_its_checkpoint(self):
        saved = {}
        state = {"n": 0}

        def cut_off(model, effort, instructions, items, tools, on_text=None):
            state["n"] += 1
            if state["n"] == 1:
                return [{"type": "function_call", "call_id": "f1", "name": "find_skills", "arguments": json.dumps({"title": "look", "query": "tp53"})}], {}
            raise RuntimeError("the server restarted")

        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(RuntimeError):
                na._run_loop(sess="t-cut", model="m", effort="low", question="find things", history=[], instructions="sys",
                             emit=lambda e: None, cancel=lambda: False, cwd=Path(d), call=cut_off, allow_ask=False,
                             checkpoint=lambda items: saved.__setitem__("items", list(items)))  # the latest checkpoint is what is kept
        kept = na.complete_exchange(saved["items"])
        self.assertTrue(any(i.get("type") == "function_call_output" and i.get("call_id") == "f1" for i in kept))

        seen = {}

        def resumed(model, effort, instructions, items, tools, on_text=None):
            seen["items"] = items
            return final("Continued from the earlier result.")

        with tempfile.TemporaryDirectory() as d:
            answer, _items, _steps = na._run_loop(sess="t-cut-2", model="m", effort="low", question="continue", history=kept, instructions="sys",
                                                 emit=lambda e: None, cancel=lambda: False, cwd=Path(d), call=resumed, allow_ask=False)
        self.assertEqual(answer, "Continued from the earlier result.")
        self.assertTrue(any(i.get("type") == "function_call_output" and i.get("call_id") == "f1" for i in seen["items"]))


if __name__ == "__main__":
    unittest.main()

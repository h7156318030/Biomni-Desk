import time
import unittest
from pathlib import Path

from biomni_ui import native_agent as na
from biomni_ui import pykernel as pk

CWD = Path(__file__).resolve().parent.parent


class Session(unittest.TestCase):
    def tearDown(self):
        pk.POOL.close_all()

    def test_variables_survive_between_steps_and_the_last_value_is_printed(self):
        self.assertEqual(pk.run("t-state", "x = 41\nx + 1", CWD).strip(), "42")
        self.assertIn("41", pk.run("t-state", "print(x)", CWD))

    def test_an_error_is_reported_without_this_files_frames_and_the_session_lives_on(self):
        out = pk.run("t-err", "y = 5\n1/0", CWD)
        self.assertIn("ZeroDivisionError", out)
        self.assertNotIn("pykernel_server", out)
        self.assertIn("5", pk.run("t-err", "print(y)", CWD))

    def test_a_step_that_takes_too_long_restarts_the_session_and_says_so(self):
        pk.run("t-slow", "z = 1", CWD)
        out = pk.run("t-slow", "import time\ntime.sleep(10)", CWD, timeout=1)
        self.assertIn("restarted", out)
        again = pk.run("t-slow", "print('z' in dir())", CWD)
        self.assertIn("False", again)

    def test_cancel_stops_the_step(self):
        t0 = time.time()
        out = pk.run("t-cancel", "import time\ntime.sleep(20)", CWD, cancel=lambda: time.time() - t0 > 1)
        self.assertIn("cancelled", out)

    def test_the_tool_finder_is_there_from_the_first_step(self):
        self.assertIn("author_papers", pk.run("t-find", "find_tools('author papers', 3)", CWD))

    def test_sessions_are_separate_per_conversation(self):
        pk.run("a", "q = 1", CWD)
        self.assertIn("False", pk.run("b", "print('q' in dir())", CWD))


class InTheLoop(unittest.TestCase):
    def tearDown(self):
        pk.POOL.close_all()

    def test_the_python_tool_runs_in_the_loop_and_keeps_state_across_calls(self):
        events = []
        steps = iter([
            [{"type": "function_call", "name": "python", "call_id": "1", "arguments": '{"title": "a", "code": "v = 7"}'}],
            [{"type": "function_call", "name": "python", "call_id": "2", "arguments": '{"title": "b", "code": "print(v * 6)"}'}],
            [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "完成。"}]}],
        ])

        def call(model, effort, instructions, items, tools, on_text=None):
            if instructions == na.JUDGE_SYSTEM:
                return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "CONTINUE"}]}], {"seconds": 0, "usage": {}}
            return next(steps), {"seconds": 0, "usage": {}}

        answer, _, n = na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=CWD, call=call)
        self.assertEqual(answer, "完成。")
        outs = [e["text"] for e in events if e["type"] == "observation"]
        self.assertIn("42", outs[-1])

    def test_a_loop_without_a_session_name_closes_its_own_kernel(self):
        before = len(pk.POOL._kernels)
        steps = iter([[{"type": "function_call", "name": "python", "call_id": "1", "arguments": '{"title": "a", "code": "1"}'}],
                      [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "好。"}]}]])
        na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=lambda e: None, cancel=lambda: False, cwd=CWD,
               call=lambda *a, **k: (next(steps), {"seconds": 0, "usage": {}}))
        self.assertEqual(len(pk.POOL._kernels), before)

    def test_python_is_a_default_tool_and_parallel_calls_are_on(self):
        names = {t.get("name") for t in na.active_tools()}
        self.assertIn("python", names)
        import inspect

        self.assertIn('"parallel_tool_calls": True', inspect.getsource(na.call_model))


if __name__ == "__main__":
    unittest.main()

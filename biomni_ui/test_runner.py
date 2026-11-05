import time
import unittest
from types import SimpleNamespace
from unittest import mock

from biomni_ui.runner import Busy, Manager


class FakeMsg:
    def __init__(self, content):
        self.content = content


class ChatOpenAI:
    """Stands in for the model class the runner recognises: an OpenAI-compatible model on a chat-completions endpoint. No request is sent."""

    def __init__(self):
        self.openai_api_key = "test-key"
        self.openai_api_base = "http://127.0.0.1:9/v1"
        self.model_name = "test-model"
        self.extra_body = {}


def native_model():
    return SimpleNamespace(llm=ChatOpenAI())


def scripted_native(answers, delay=0.0, steps=()):
    """Stands in for the native loop. Each task emits the given step events, waits `delay` seconds (or until it is cancelled),
    then takes the next answer from the list ("" once the list is empty)."""
    queue = list(answers)

    def run(**kw):
        for step in steps:
            kw["emit"](dict(step))
        end = time.time() + delay
        while time.time() < end and not kw["cancel"]():
            time.sleep(0.02)
        if kw["cancel"]():
            return "", [], 0
        return (queue.pop(0) if queue else ""), [], 0

    return run


def use_native(testcase, answers, delay=0.0, steps=()):
    """For this test, the native loop is replaced by scripted_native. The patch is removed when the test ends."""
    patcher = mock.patch("biomni_ui.native_agent.run", side_effect=scripted_native(answers, delay, steps))
    patcher.start()
    testcase.addCleanup(patcher.stop)


def collect(task):
    return [e for e in task.stream() if e is not None]


class RunnerTests(unittest.TestCase):
    def test_full_run_event_order(self):
        use_native(self, ["done"], steps=[{"type": "code", "language": "python", "code": "print(1)"}, {"type": "observation", "text": "1"}])
        ev = collect(Manager(native_model).start("q"))
        types = [e["type"] for e in ev]
        self.assertEqual(types[:2], ["status", "status"])
        self.assertEqual(types[2:], ["code", "observation", "answer", "done"])
        self.assertEqual([e["seq"] for e in ev], list(range(len(ev))))
        self.assertTrue(ev[-2]["text"].startswith("done"))

    def test_empty_answer_is_replaced_by_a_message(self):
        use_native(self, [""])
        ev = collect(Manager(native_model).start("q"))
        self.assertEqual(ev[-2]["type"], "answer")
        self.assertIn("No answer was received", ev[-2]["text"])
        self.assertEqual(ev[-1]["type"], "done")

    def test_busy_then_free(self):
        use_native(self, ["x", "y"], delay=0.3)
        m = Manager(native_model)
        t = m.start("q")
        with self.assertRaises(Busy):
            m.start("q2")
        collect(t)
        collect(m.start("q3"))  # no longer busy

    def test_cancel(self):
        use_native(self, [], delay=5.0)
        m = Manager(native_model)
        t = m.start("q")
        time.sleep(0.25)
        self.assertTrue(m.cancel(t.id))
        ev = collect(t)
        self.assertEqual(ev[-1]["type"], "cancelled")

    def test_resume_from_seq(self):
        use_native(self, ["x"])
        t = Manager(native_model).start("q")
        all_ev = collect(t)
        rest = [e for e in t.stream(2) if e is not None]
        self.assertEqual(rest, all_ev[2:])

    def test_agent_error_becomes_event(self):
        def boom():
            raise ValueError("no key")

        ev = collect(Manager(boom).start("q"))
        self.assertEqual(ev[-1]["type"], "error")
        self.assertIn("no key", ev[-1]["message"])


if __name__ == "__main__":
    unittest.main()

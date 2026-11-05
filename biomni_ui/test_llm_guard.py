import unittest
from types import SimpleNamespace

from langchain_core.messages import AIMessage

from biomni_ui.llm_guard import StopGuardLLM, cut_after_first_close, guard


class Cut(unittest.TestCase):
    def test_invented_observation_and_solution_are_dropped(self):
        text = "查一下。<execute>print(1)</execute>\n<observation>假的</observation>\n<solution>编造的答案</solution>"
        self.assertEqual(cut_after_first_close(text), "查一下。<execute>print(1)</execute>")

    def test_solution_alone_is_kept(self):
        text = "好。<solution>答案</solution>多余"
        self.assertEqual(cut_after_first_close(text), "好。<solution>答案</solution>")

    def test_first_closer_wins(self):
        self.assertEqual(cut_after_first_close("<solution>a</solution><execute>x</execute>"), "<solution>a</solution>")

    def test_no_tags_untouched(self):
        self.assertEqual(cut_after_first_close("plain"), "plain")
        self.assertEqual(cut_after_first_close("<execute>open"), "<execute>open")


class Fake:
    model_name = "fake-model"

    def __init__(self, content):
        self.content = content
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        return AIMessage(content=self.content)


class Wrapper(unittest.TestCase):
    def test_invoke_truncates_and_proxies(self):
        inner = Fake("<execute>a</execute><observation>x</observation><solution>y</solution>")
        g = StopGuardLLM(inner)
        out = g.invoke([("human", "hi")])
        self.assertEqual(out.content, "<execute>a</execute>")
        self.assertEqual(inner.calls, 1)
        self.assertEqual(g.model_name, "fake-model")  # attribute access reaches the real model

    def test_clean_reply_passes_through(self):
        g = StopGuardLLM(Fake("<execute>a</execute>"))
        self.assertEqual(g.invoke([]).content, "<execute>a</execute>")

    def test_guard_wraps_once(self):
        agent = SimpleNamespace(llm=Fake("x"))
        guard(agent)
        first = agent.llm
        guard(agent)
        self.assertIs(agent.llm, first)
        self.assertIsInstance(first, StopGuardLLM)


if __name__ == "__main__":
    unittest.main()

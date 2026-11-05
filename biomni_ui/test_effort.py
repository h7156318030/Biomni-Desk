import unittest
from types import SimpleNamespace

from biomni_ui import effort


def fake(reply):
    return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=reply))


class Level(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(effort.parse_level('{"level": "simple"}'), "simple")
        self.assertEqual(effort.parse_level('好的：{"level":"normal"}'), "normal")
        for bad in ("", "no json", '{"level": "x"}', '{"level": 3}'):
            self.assertEqual(effort.parse_level(bad), "deep")

    def test_never_above_the_ceiling_or_below_the_need(self):
        self.assertEqual(effort.effort_for("simple", "high"), "medium")  # the starting tier, not below it
        self.assertEqual(effort.effort_for("normal", "high"), "medium")
        self.assertEqual(effort.effort_for("deep", "high"), "high")
        self.assertEqual(effort.effort_for("simple", "low"), "medium")  # a stored low is raised to the starting tier
        self.assertEqual(effort.effort_for("normal", "low"), "medium")  # never below the starting tier
        self.assertEqual(effort.effort_for("simple", "weird"), "weird")


class Pick(unittest.TestCase):
    def test_simple_question_lowers_effort(self):
        self.assertEqual(effort.pick(fake('{"level":"simple"}'), "上海今天天气", "high"), ("medium", "simple"))

    def test_files_and_failures_keep_the_ceiling(self):
        self.assertEqual(effort.pick(fake('{"level":"simple"}'), "分析 a.csv", "high", has_files=True), ("high", "deep"))
        boom = SimpleNamespace(invoke=lambda m: (_ for _ in ()).throw(RuntimeError("down")))
        self.assertEqual(effort.pick(boom, "x", "high"), ("high", "deep"))
        self.assertEqual(effort.pick(fake("garbage"), "x", "high"), ("high", "deep"))


class Heuristic(unittest.TestCase):
    def test_wording_decides_without_a_model(self):
        self.assertEqual(effort.heuristic("TP53 基因在哪条染色体上"), "simple")
        self.assertEqual(effort.heuristic("查询上海今天天气"), "simple")
        self.assertEqual(effort.heuristic("PCSK9 抑制剂有哪些已上市药物"), "normal")
        self.assertEqual(effort.heuristic("CD19 CAR-T 的常见耐药机制"), "normal")
        self.assertEqual(effort.heuristic("分析 uploads 里的 test_two_group.csv"), "deep")
        self.assertEqual(effort.heuristic("设计 PCR 引物"), "deep")
        self.assertEqual(effort.heuristic("随便问问", has_files=True), "deep")


class InRunner(unittest.TestCase):
    def test_prompt_has_todays_date_and_realtime_rule(self):
        from biomni_ui import runner

        t = runner.Task("查询上海今天天气", "c1")
        self.assertIn("Today's date is", t.agent_prompt)
        self.assertIn("Real-time information", t.agent_prompt)


class StartingTier(unittest.TestCase):
    """No call on the answer path reasons below the starting tier (medium). A lower level is neither offered nor sent."""

    def test_a_level_below_the_starting_tier_is_raised_to_it(self):
        self.assertEqual(effort.floor("low"), "medium")
        self.assertEqual(effort.floor("minimal"), "medium")
        self.assertEqual(effort.floor("medium"), "medium")
        self.assertEqual(effort.floor("high"), "high")
        self.assertEqual(effort.floor(""), "")  # a model with no reasoning setting keeps none

    def test_the_levels_offered_have_no_low_one(self):
        self.assertEqual(effort.offered(["low", "medium", "high"]), ["medium", "high"])
        self.assertEqual(effort.offered(["low", "high", "max"]), ["high", "max"])
        self.assertEqual(effort.offered(["low"]), ["medium"])  # a provider offering only low still gets one choice, at the floor
        self.assertEqual(effort.offered([]), [])

    def test_a_deep_question_keeps_the_setting_but_never_goes_below_the_floor(self):
        self.assertEqual(effort.effort_for("deep", "low"), "medium")
        self.assertEqual(effort.effort_for("deep", "xhigh"), "xhigh")

    def test_chatgpt_accepts_a_stored_low_as_the_starting_tier(self):
        from biomni_ui.codex_llm import resolve_effort

        self.assertEqual(resolve_effort("low"), "medium")
        self.assertEqual(resolve_effort("high"), "high")
        with self.assertRaises(ValueError):
            resolve_effort("turbo")


if __name__ == "__main__":
    unittest.main()

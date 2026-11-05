import unittest


class RefusalPattern(unittest.TestCase):
    def test_pattern(self):
        from biomni_ui.runner import REFUSAL_RE

        for yes in ("未能核实", "无法核实 TP53", "没有取得可引用的结果", "未执行数据库查询"):
            self.assertTrue(REFUSAL_RE.search(yes), yes)
        for no in ("TP53 是抑制基因", "已完成查询", "结果如下"):
            self.assertFalse(REFUSAL_RE.search(no), no)


class PrematureSolution(unittest.TestCase):
    PLAN = [{"text": "查 ClinicalTrials.gov", "status": "todo"}, {"text": "汇总", "status": "todo"}]

    def test_plan_only_solution_with_open_steps_is_rejected(self):
        from biomni_ui.runner import premature

        text = "1. [ ] 查 ClinicalTrials.gov\n2. [ ] 汇总\n接下来我会检索。"
        self.assertTrue(premature(text, 0, self.PLAN))
        self.assertIn("checklist", premature(text, 3, self.PLAN))  # even after real work, an answer that is just the unticked checklist is not accepted

    def test_hedging_short_answer_without_any_execution_is_rejected(self):
        from biomni_ui.runner import premature

        self.assertIn("without running any operation", premature("当前还没有实际检索到数据库或网页结果，因此不能据此判断。", 0, None))

    def test_real_answers_are_accepted(self):
        from biomni_ui.runner import premature

        done = [{"text": "查", "status": "done"}]
        self.assertEqual(premature("## 结果\n" + "共 12 项试验，其中 3 项为 II 期。" * 10, 2, done), "")
        self.assertEqual(premature("6", 0, None), "")  # a plain answer that needs no tool is fine
        self.assertEqual(premature("今天没有新的临床试验登记。" * 3, 3, done), "")  # it did execute, so a negative result is a result

    def test_nudge_names_the_open_steps(self):
        from biomni_ui.runner import nudge_text

        self.assertIn("查 ClinicalTrials.gov", nudge_text(self.PLAN))


class PlanText(unittest.TestCase):
    def test_a_plan_restated_three_times_leaves_only_the_narration(self):
        from biomni_ui.events import message_to_events

        plan = "1. [ ] 查名称\n2. [ ] 查试验"
        content = f"我先检索公司信息。{plan}我现在执行搜索。{plan}<execute>print(1)</execute>"
        ev = message_to_events(content)
        reasoning = [e["text"] for e in ev if e["type"] == "reasoning"]
        self.assertTrue(reasoning and "[ ]" not in reasoning[0])
        self.assertEqual([e["type"] for e in ev if e["type"] == "plan"], ["plan"])


class GiveUpTooEarly(unittest.TestCase):
    def test_the_screenshot_case_is_rejected(self):
        from biomni_ui.runner import GIVE_UP_NUDGE, nudge_text, premature

        text = "目前无法确认“示例生物”对应哪个基因；按该词检索 ClinicalTrials.gov，未找到匹配的登记试验。请提供标准基因符号（如 BRCA1）或英文全名，我才能进一步查其临床试验。"
        why = premature(text, 1, None)
        self.assertIn("only tried 1 approaches", why)
        self.assertEqual(nudge_text(None, why), GIVE_UP_NUDGE)
        self.assertIn("web_search", GIVE_UP_NUDGE)

    def test_a_negative_result_after_real_effort_is_accepted(self):
        from biomni_ui.runner import premature

        text = "在 ClinicalTrials.gov、中国登记平台和公司公告里都没有找到该产品的登记。已尝试：英文名、别名、网页搜索。"
        self.assertEqual(premature(text, 4, None), "")

    def test_a_long_substantive_answer_that_mentions_missing_pieces_is_accepted(self):
        from biomni_ui.runner import premature

        self.assertEqual(premature("共 12 项试验。" * 120 + "其中 1 项没有找到登记号。", 1, None), "")


class FellBackToMemory(unittest.TestCase):
    def test_memory_fallback_after_one_try_is_sent_back(self):
        from biomni_ui.runner import premature

        self.assertIn("only tried", premature("未经检索核实（来自模型自身知识）：sotorasib 已上市……" * 40, 1, None))
        self.assertEqual(premature("未经检索核实（来自模型自身知识）：x", 4, None), "")


class NegativeFindingWithSources(unittest.TestCase):
    def test_not_found_with_two_sources_is_an_answer(self):
        from biomni_ui.runner import premature

        text = "本周没有查到全新活性成分获批。([FDA](https://www.fda.gov/a))([FDA](https://www.fda.gov/b))"
        self.assertEqual(premature(text, 1, None), "")
        self.assertIn("only tried", premature("本周没有查到全新活性成分获批。", 1, None))


if __name__ == "__main__":
    unittest.main()

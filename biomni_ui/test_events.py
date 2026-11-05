import unittest

from biomni_ui.events import extract_files, message_to_events, parse_plan


class ParsePlan(unittest.TestCase):
    def test_statuses(self):
        steps = parse_plan("1. [✓] Import\n2. [ ] Query\n3. [✗] Bad (failed because x)")
        self.assertEqual([s["status"] for s in steps], ["done", "todo", "failed"])
        self.assertEqual(steps[1]["text"], "Query")

    def test_none(self):
        self.assertIsNone(parse_plan("just prose"))


class MessageEvents(unittest.TestCase):
    def test_plan_then_code(self):
        msg = "Thinking about it.\n1. [ ] A\n2. [ ] B\n\n<execute>\nprint(1)\n</execute>"
        ev = message_to_events(msg)
        self.assertEqual([e["type"] for e in ev], ["plan", "reasoning", "code"])
        self.assertEqual(ev[1]["text"], "Thinking about it.")
        self.assertEqual(ev[2]["code"], "print(1)")

    def test_unclosed_execute(self):
        # stop sequences remove the closing tag in real runs
        ev = message_to_events("<execute>print(2)")
        self.assertEqual(ev, [{"type": "code", "language": "python", "code": "print(2)"}])

    def test_languages(self):
        self.assertEqual(message_to_events("<execute>#!R\nx<-1</execute>")[0]["language"], "r")
        self.assertEqual(message_to_events("<execute>#!BASH\nls</execute>")[0]["language"], "bash")

    def test_observation_files(self):
        ev = message_to_events("<observation>saved to out/plot.png and 'bad.png</observation>")
        self.assertEqual(ev[0]["type"], "observation")
        self.assertEqual(ev[0]["files"], ["out/plot.png"])

    def test_answer(self):
        ev = message_to_events("<solution>TP53 is p53.</solution>")
        self.assertEqual(ev, [{"type": "answer", "text": "TP53 is p53."}])

    def test_answer_drops_repeated_checklist(self):
        ev = message_to_events("<solution>1. [✓] 查询\n2. [✓] 总结\n\n结论：TP53 是抑制基因。\n1. 普通列表保留</solution>")
        self.assertEqual(ev[0]["text"], "结论：TP53 是抑制基因。\n1. 普通列表保留")

    def test_plain_text_no_tags_is_not_reasoning(self):
        self.assertEqual(message_to_events("hello"), [])

    def test_extract_files_filters(self):
        self.assertEqual(extract_files("Error:x.png ./a.png ok/b.csv"), ["ok/b.csv"])


if __name__ == "__main__":
    unittest.main()


class PlanRestatedTests(unittest.TestCase):
    def test_normal_multiline_list(self):
        from biomni_ui.events import parse_plan
        self.assertEqual(
            parse_plan("1. [✓] 查询\n2. [ ] 汇总"),
            [{"text": "查询", "status": "done"}, {"text": "汇总", "status": "todo"}],
        )

    def test_checklist_repeated_on_one_line_keeps_last_run(self):
        from biomni_ui.events import parse_plan
        text = "1. [ ] 画图\n2. [ ] 存 CSV。1. [ ] 画图\n2. [ ] 存 CSV。1. [✓] 画图\n2. [ ] 存 CSV"
        self.assertEqual(
            parse_plan(text),
            [{"text": "画图", "status": "done"}, {"text": "存 CSV", "status": "todo"}],
        )

    def test_no_checklist(self):
        from biomni_ui.events import parse_plan
        self.assertIsNone(parse_plan("没有清单，只是说明 1. 或 [ ] 之类"))

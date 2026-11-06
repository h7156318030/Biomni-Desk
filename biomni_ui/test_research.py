import unittest
from types import SimpleNamespace
from unittest import mock

from biomni_ui import research


class FakeLLM:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.replies.pop(0))


WEB = "Web search: q (360, 2 results in all)\n[1] 标题甲 | a.org\n    https://a.org/1\n    摘要\n[2] 视频 | bilibili.com\n    https://www.bilibili.com/v/1\n    x"


class Gate(unittest.TestCase):
    def test_only_author_lookups_take_the_lane(self):
        for q in ["查询王小明的论文", "查询Li Xiaohua的论文", "查一下凌思凯的论文", "papers by Wang Xiaoming", "Xiaohua Li 的论文列表", "查李小华的论文"]:
            self.assertTrue(research.wants_research(q), q)

    def test_everything_else_goes_to_the_agent_and_its_tools(self):
        for q in ["上海佰炼医药是做什么的？最近有什么公开合作？", "查询君赛生物的临床研究", "示例生物近两年有什么进展", "对比两家公司的管线",
                  "TP53 在乳腺癌中的作用机制和相关文献", "查一下本月发表的CAR-T文献", "查最近的论文"]:
            self.assertFalse(research.wants_research(q), q)

    def test_data_code_and_chat_are_not(self):
        for q in ["分析这个 csv 文件", "画一张火山图", "1+5等于？", "设计 sgRNA 靶向 TP53", "你好", ""]:
            self.assertFalse(research.wants_research(q), q)


class Planning(unittest.TestCase):
    def test_plan_parses_json_dedupes_and_caps(self):
        reply = '前言 {"queries":[{"tool":"web","q":"a"},{"tool":"web","q":"a"},{"tool":"bogus","q":"x"},{"tool":"author","q":"王小明"}],"note":"先查主页"} 后记'
        qs, note = research.plan(FakeLLM([reply]), "问题", "今天", "")
        self.assertEqual(qs, [{"tool": "web", "q": "a"}, {"tool": "author", "q": "王小明"}])
        self.assertEqual(note, "先查主页")

    def test_unusable_plan_falls_back_to_the_question(self):
        qs, _ = research.plan(FakeLLM(["不是 JSON"]), "问题X", "今天", "")
        self.assertEqual(qs, [{"tool": "web", "q": "问题X"}])

    def test_context_reaches_the_planner(self):
        llm = FakeLLM(['{"queries":[]}'])
        research.plan(llm, "他的论文", "今天", "问：王小明是谁")
        self.assertIn("王小明", llm.calls[0][1].content)


class Pages(unittest.TestCase):
    def test_pages_are_spread_across_queries_and_junk_hosts_skipped(self):
        a = "\n".join(f"[{i}] t | h{i}.org\n    https://h{i}.org/p\n    s" for i in range(1, 4))
        b = "[1] t | z.org\n    https://z.org/p\n    s\n[2] 视频 | bilibili.com\n    https://www.bilibili.com/v/1\n    s"
        urls = research.pick_pages([a, b], 3)
        self.assertEqual(urls, ["https://h1.org/p", "https://z.org/p", "https://h2.org/p"])


class Run(unittest.TestCase):
    def test_run_emits_steps_reads_pages_and_writes_from_the_material(self):
        llm = FakeLLM(['{"queries":[{"tool":"web","q":"a"}],"note":"开始"}', '{"queries":[]}', "最终答案"])
        events = []
        with mock.patch.object(research.web, "web_search", return_value=WEB), mock.patch.object(research.web, "read_webpage", return_value="Title: 甲\n正文内容"):
            out = research.run(llm, "问题", "今天", "", events.append)
        self.assertEqual(out, "最终答案")
        kinds = [e["type"] for e in events]
        self.assertEqual(kinds[0], "plan")
        plans = [e["steps"] for e in events if e["type"] == "plan"]
        done = [sum(x["status"] == "done" for x in st) for st in plans]
        self.assertEqual(done, sorted(done))  # the checklist only ever moves forward
        labels = [x["text"] for x in plans[-1]]
        self.assertEqual((done[0], done[-1]), (0, len(labels)))
        self.assertTrue(any("Web search: a" in t for t in labels))  # the checklist names what is really being searched, not a template
        self.assertEqual(kinds.count("code"), 2)  # one search and one page read (the bilibili result is skipped)
        material = llm.calls[2][1].content
        self.assertIn("正文内容", material)
        self.assertIn("https://a.org/1", material)

    def test_refine_round_runs_the_extra_queries_before_writing(self):
        plan = '{"queries":[{"tool":"web","q":"a"}]}'
        refine = '{"queries":[{"tool":"pubmed","q":"\\"Wang X\\"[Author] AND Aarhus[Affiliation]"}],"note":"补查曾用单位"}'
        llm = FakeLLM([plan, refine, "答案"])
        events = []
        with mock.patch.object(research.web, "web_search", return_value=WEB), mock.patch.object(research.web, "read_webpage", return_value="页面"),                 mock.patch.object(research.lit, "pubmed_search", return_value="PMID: 1 | 旧论文 | Wang X | eLife 2014") as ps:
            research.run(llm, "问题", "今天", "", events.append)
        ps.assert_called_once()
        self.assertIn("补查曾用单位", [e.get("text") for e in events])
        self.assertIn("旧论文", llm.calls[2][1].content)

    def test_nothing_found_hands_the_task_back(self):
        llm = FakeLLM(['{"queries":[{"tool":"web","q":"a"}]}', '{"queries":[]}'])
        with mock.patch.object(research.web, "web_search", return_value="Web search returned no results (possibly rate-limited). Query: a"):
            self.assertIsNone(research.run(llm, "问题", "今天", "", lambda e: None))


if __name__ == "__main__":
    unittest.main()


class Needles(unittest.TestCase):
    def test_only_results_that_mention_the_person_are_read(self):
        out = ("[1] Xiaohua Li - Independent Researcher | academia.edu\n    https://a.edu/hao\n    Papers by Xiaohua Li\n"
               "[2] 房源 | lianjia.com\n    https://lianjia.com/x\n    二手房\n")
        needles = research.anchors_of([{"tool": "author", "q": "Li Xiaohua"}])
        self.assertEqual(research.pick_pages([out], 5, needles), ["https://a.edu/hao"])
        self.assertEqual(len(research.pick_pages([out], 5)), 2)  # no author query: nothing is filtered

    def test_chinese_name_is_a_needle(self):
        self.assertIn("王小明", research.anchors_of([{"tool": "author", "q": "王小明"}]))


class ZenodoTable(unittest.TestCase):
    MATERIAL = ("### ORCID 登记的同名者\nORCID 0000 | x\n\n### Zenodo 存档（含预印本）\n"
                "2026-08-13 | 标题甲 | DOI 10.5281/zenodo.1 | 作者栏：Li, Xiaohua（Jiangsu University）\n"
                "2026-07-19 | 标题乙 | DOI 10.5281/zenodo.2 | 作者栏：Li, Xiaohua（Jiangsu University）\n\n### 其他\nx")

    def test_table_is_built_from_the_records(self):
        t = research.zenodo_table(self.MATERIAL)
        self.assertIn("| 2026-08-13 | 标题甲 | [10.5281/zenodo.1](https://doi.org/10.5281/zenodo.1) |", t)
        self.assertIn("not peer reviewed", t)
        self.assertNotIn("其他", t)

    def test_no_zenodo_section_means_no_table(self):
        self.assertEqual(research.zenodo_table("### ORCID\nx"), "")

    def test_anchor_filter_needs_every_word_of_the_name(self):
        needles = research.anchors_of([{"tool": "author", "q": "Li Xiaohua"}])
        self.assertFalse(research._relevant("Zhang Li publications", needles))
        self.assertTrue(research._relevant("papers by Xiaohua Li", needles))

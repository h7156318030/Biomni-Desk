import os
import tempfile
import unittest
from pathlib import Path

from biomni_ui import report


class InTempDir(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory()
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()


class Charts(InTempDir):
    def test_each_kind_writes_a_png(self):
        for kind in ("bar", "barh", "line", "pie"):
            name = report.make_chart(kind, ["甲", "乙", "丙"], [1, 2, 3], title=f"测试{kind}", filename=f"t_{kind}")
            self.assertTrue(Path(name).read_bytes().startswith(b"\x89PNG"), kind)

    def test_several_series_and_length_check(self):
        name = report.make_chart("bar", ["a", "b"], {"2024": [1, 2], "2025": [2, 3]}, title="x")
        self.assertTrue(Path(name).exists())
        with self.assertRaises(ValueError):
            report.make_chart("bar", ["a", "b"], [1, 2, 3])

    def test_unknown_kind(self):
        with self.assertRaises(ValueError):
            report.make_chart("radar", ["a"], [1])


class Report(InTempDir):
    def test_report_embeds_figure_table_and_sources_and_escapes_html(self):
        fig = report.make_chart("bar", ["2024", "2025"], [1.64, 2.33], title="亏损")
        msg = report.build_report("财务复核 <b>", "结论：**增加** 42%", [
            {"heading": "核对表", "table": [["说法", "结论"], ["亏损 | 近4亿", "✅"]]},
            {"heading": "趋势", "text": "- 要点一\n- 要点二 https://example.org/x", "figure": fig, "caption": "图1"},
        ], filename="r1", sources=["PMID: 123 | 标题", "https://example.org/p"])
        self.assertIn("r1.html", msg)
        page = Path("r1.html").read_text(encoding="utf-8")
        self.assertIn("data:image/png;base64,", page)
        self.assertIn("<table>", page)
        self.assertIn("<strong>增加</strong>", page)
        self.assertIn("&lt;b&gt;", page)  # the title is escaped
        self.assertNotIn("<b>", page.split("<style>")[1].split("</style>")[1])
        self.assertIn('<a href="https://example.org/x">', page)
        md = Path("r1.md").read_text(encoding="utf-8")
        self.assertIn("![图1](" + fig + ")", md)
        self.assertIn("亏损 \| 近4亿", md)
        self.assertIn("1. PMID: 123 | 标题", md)

    def test_missing_figure_does_not_crash(self):
        report.build_report("t", "s", [{"heading": "h", "figure": "nope.png"}], filename="r2")
        self.assertIn("not found", Path("r2.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()


class FromAnswer(InTempDir):
    def test_answer_becomes_a_report_with_table_and_sources(self):
        from biomni_ui import research

        answer = "结论一句话。\n\n## 关键发现\n\n- 要点 [站点](https://a.org/x)\n\n## 论文\n\n| 年份 | 标题 |\n|---|---|\n| 2024 | 甲 |\n"
        code, msg = research.report_from_answer("上海佰炼医药近期合作？", answer, ["https://a.org/x"])
        self.assertIn("build_report", code)
        name = msg.split("Report saved: ")[1].split(" (")[0]
        page = Path(name).read_text(encoding="utf-8")
        self.assertIn("<table>", page)
        self.assertIn('<a href="https://a.org/x">站点</a>', page)
        self.assertIn("<h2>论文</h2>", page)

    def test_wants_report(self):
        from biomni_ui import research

        self.assertTrue(research.wants_report("请给我详细的图文报告"))
        self.assertFalse(research.wants_report("查询王小明的论文"))

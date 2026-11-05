import os
import tempfile
import unittest

from biomni_ui import biomni_tools, files, report


class Deck(unittest.TestCase):
    def test_a_deck_is_written_with_a_cover_and_the_given_slides(self):
        from pptx import Presentation

        old = os.getcwd()
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            os.chdir(d)
            try:
                png = report.make_chart("bar", ["甲", "乙"], [3, 5], title="示例")
                msg = report.make_deck("药物概览", [
                    {"heading": "已上市", "bullets": ["甲", "乙"], "table": [["药物", "类型"], ["甲", "单抗"]], "source": "https://example.org/a", "notes": "讲稿"},
                    {"heading": "图", "figure": png, "bullets": ["要点"]},
                ], filename="t", subtitle="日期")
                self.assertIn("3 slides", msg)
                prs = Presentation("t.pptx")
                self.assertEqual(len(prs.slides), 3)
                self.assertEqual(prs.slides[1].notes_slide.notes_text_frame.text, "讲稿")
            finally:
                os.chdir(old)

    def test_the_deck_tool_is_in_the_index_and_the_file_type_is_served(self):
        self.assertIn("make_deck", {t["name"] for t in biomni_tools.catalog()})
        self.assertIn(".pptx", files.ALLOWED_EXT)


if __name__ == "__main__":
    unittest.main()

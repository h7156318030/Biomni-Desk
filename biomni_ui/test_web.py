import base64
import unittest
from unittest import mock

from biomni_ui import web

SO360 = """<ul><li class="res-list"><h3><a href="https://www.so.com/link?m=xx" data-mdurl="https://example.org/a">示例 <em>标题</em></a></h3>
<p class="res-desc">一段摘要 文字</p></li><li class="res-list"><h3><a href="/relative">没有真实网址</a></h3></li></ul>"""
BING = """<ol><li class="b_algo"><h2><a href="https://bing.com/ck/a?u=a1{enc}">Bing 标题</a></h2><div class="b_caption"><p>摘要</p></div></li></ol>"""


class Parsing(unittest.TestCase):
    def test_360_uses_the_real_address_and_skips_unusable_rows(self):
        rows = web.parse_so360(SO360, 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["url"], rows[0]["site"], rows[0]["title"]), ("https://example.org/a", "example.org", "示例 标题"))
        self.assertEqual(rows[0]["snippet"], "一段摘要 文字")

    def test_bing_redirect_is_unwrapped(self):
        enc = base64.urlsafe_b64encode(b"https://real.example.com/p?q=1").decode().rstrip("=")
        rows = web.parse_results(BING.format(enc=enc), 5)
        self.assertEqual(rows[0]["url"], "https://real.example.com/p?q=1")

    def test_limit_is_respected(self):
        self.assertEqual(len(web.parse_so360(SO360 * 3, 2)), 2)


class Search(unittest.TestCase):
    def test_falls_back_to_bing_when_360_is_thin(self):
        thin = [{"title": "a", "url": "https://a.org", "site": "a.org", "snippet": "s"}]
        more = [{"title": "b", "url": "https://b.org", "site": "b.org", "snippet": "s"}] * 1 + [{"title": "c", "url": "https://c.org", "site": "c.org", "snippet": "s"}] * 1
        with mock.patch.dict(web.ENGINES, {"360": lambda q, n, lang: thin, "bing": lambda q, n, lang: more}):
            out = web.web_search("q", 5)
        self.assertIn("360+bing", out)
        self.assertIn("https://b.org", out)

    def test_no_results_is_said_plainly(self):
        with mock.patch.dict(web.ENGINES, {"360": lambda q, n, lang: [], "bing": lambda q, n, lang: []}):
            self.assertIn("returned no results", web.web_search("q"))

    def test_unknown_engine(self):
        self.assertIn("Unknown", web.web_search("q", engine="nope"))


if __name__ == "__main__":
    unittest.main()

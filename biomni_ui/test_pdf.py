import http.server
import io
import threading
import unittest

from biomni_ui import web


def make_pdf(pages: list[str]) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    matplotlib.rcParams["pdf.fonttype"] = 42  # embedded TrueType: the text stays extractable
    matplotlib.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        for text in pages:
            fig = plt.figure(figsize=(8, 5))
            fig.text(0.05, 0.5, text, fontsize=14)
            pdf.savefig(fig)
            plt.close(fig)
    return buf.getvalue()


class Server:
    def __init__(self, routes: dict[str, tuple[bytes, str]]):
        class H(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                body, ctype = routes.get(self.path, (b"nope", "text/html"))
                self.send_response(200 if self.path in routes else 404)
                self.send_header("Content-Type", ctype)
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *a):
                pass

        self.httpd = http.server.HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


class ReadPdf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pages = ["Cover page", "Risk factors only", "Net loss 2025: 233 million RMB, cash 80.68 million", "Redemption liabilities 840 million", "Appendix", "净亏损 2.33 亿元 赎回负债 8.40 亿元"]
        cls.srv = Server({"/f.pdf": (make_pdf(pages), "application/pdf"), "/fake.pdf": (b"<html>blocked</html>", "application/pdf"), "/p.html": (b"<html><title>t</title><body><p>hello</p></body></html>", "text/html")})

    @classmethod
    def tearDownClass(cls):
        cls.srv.close()

    def setUp(self):
        web._PDF_CACHE.clear()
        web._CACHE.clear()

    def test_pages_matching_the_query_come_back_with_their_page_numbers(self):
        out = web.read_pdf(self.srv.url + "/f.pdf", "Net loss cash", 2000)
        self.assertIn("6 pages", out)
        self.assertIn("[page 3]", out)
        self.assertIn("233 million", out)
        self.assertNotIn("[page 5]", out)

    def test_chinese_text_is_extracted_and_matched(self):
        out = web.read_pdf(self.srv.url + "/f.pdf", "净亏损 赎回负债", 2000)
        self.assertIn("[page 6]", out)
        self.assertIn("2.33", out)

    def test_without_a_query_the_first_pages_are_returned(self):
        out = web.read_pdf(self.srv.url + "/f.pdf", "", 2000)
        self.assertIn("[page 1]", out)

    def test_no_matching_page_is_reported(self):
        self.assertIn("no page contains", web.read_pdf(self.srv.url + "/f.pdf", "zzzzqqq", 2000))

    def test_blocked_download_is_explained(self):
        self.assertIn("not a PDF", web.read_pdf(self.srv.url + "/fake.pdf", "x"))

    def test_read_webpage_hands_pdf_links_to_read_pdf(self):
        self.assertIn("6 pages", web.read_webpage(self.srv.url + "/f.pdf", 2000))

    def test_query_terms_drop_filler_words(self):
        self.assertEqual(web._terms("君赛生物 最近 有什么 净亏损"), ["君赛生物", "净亏损"])


if __name__ == "__main__":
    unittest.main()

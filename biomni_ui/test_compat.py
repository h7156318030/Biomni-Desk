import unittest

import httpx

from biomni_ui import compat


class Proxies(unittest.TestCase):
    def test_translate(self):
        self.assertEqual(compat._translate({"a": 1}), {"a": 1})
        self.assertEqual(compat._translate({"proxies": "http://p:1"}), {"proxy": "http://p:1"})
        self.assertEqual(compat._translate({"proxies": {"http://": "http://a", "https://": "http://b"}}), {"proxy": "http://b"})
        self.assertEqual(compat._translate({"proxies": {"http": "http://a"}}), {"proxy": "http://a"})
        self.assertEqual(compat._translate({"proxies": None}), {})
        self.assertEqual(compat._translate({"proxies": "http://x", "proxy": "http://keep"}), {"proxy": "http://keep"})

    def test_patched_client_accepts_the_old_argument(self):
        compat.patch_httpx()
        with httpx.Client(proxies={"http": "http://127.0.0.1:9", "https": "http://127.0.0.1:9"}) as c:
            self.assertIsInstance(c, httpx.Client)
        with httpx.Client(timeout=3) as c:  # ordinary use is unaffected
            self.assertEqual(c.timeout.read, 3)
        self.assertFalse(compat.patch_httpx())  # applying twice does nothing more


if __name__ == "__main__":
    unittest.main()

import unittest
from unittest import mock

from biomni_ui import lit


class FakeResponse:
    def __init__(self, body):
        self._body = body
        self.content = b"x"

    def json(self):
        return self._body


class PubmedIds(unittest.TestCase):
    def test_an_error_body_is_retried_and_a_later_result_is_used(self):
        answers = [FakeResponse({"esearchresult": {"ERROR": "API rate limit exceeded"}}), FakeResponse({"esearchresult": {"idlist": ["123", "456"]}})]
        with mock.patch.object(lit, "_get", side_effect=answers), mock.patch.object(lit.time, "sleep"):
            self.assertEqual(lit.pubmed_ids("TP53 gastric review"), ["123", "456"])

    def test_repeated_error_bodies_give_ncbis_words_not_a_key_error(self):
        bad = FakeResponse({"esearchresult": {"ERROR": "Invalid query"}})
        with mock.patch.object(lit, "_get", return_value=bad), mock.patch.object(lit.time, "sleep"):
            with self.assertRaises(RuntimeError) as ctx:
                lit.pubmed_ids("((bad", attempts=2)
        self.assertIn("Invalid query", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()

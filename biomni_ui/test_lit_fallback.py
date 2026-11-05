import unittest
from unittest import mock

from biomni_ui import lit


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


CROSSREF_PAYLOAD = {"message": {"items": [
    {"DOI": "10.1000/xyz1", "title": ["Acquired resistance to KRAS G12C inhibition"], "container-title": ["Nature"],
     "issued": {"date-parts": [[2021, 6]]}, "author": [{"family": "Awad", "given": "Marcus"}, {"family": "Liu", "given": "S"}]},
    {"DOI": "10.1000/xyz2", "title": [], "container-title": [], "issued": {}, "author": []},
]}}


class PubmedFallback(unittest.TestCase):
    def test_a_pubmed_error_falls_back_to_europe_pmc_and_says_so(self):
        with mock.patch.object(lit, "pubmed_ids", side_effect=RuntimeError("NCBI ERROR 500")), \
                mock.patch.object(lit, "europepmc_search", return_value="Query: q\n1 papers:\n2021 | Nature | 论文甲"):
            out = lit.pubmed_search("q", 5)
        self.assertIn("论文甲", out)
        self.assertIn("using the PubMed-indexed records in Europe PMC", out)
        self.assertIn("PubMed error: RuntimeError", out)

    def test_when_europe_pmc_finds_nothing_crossref_answers_with_its_dois(self):
        with mock.patch.object(lit, "pubmed_ids", return_value=[]), \
                mock.patch.object(lit, "europepmc_search", return_value="Europe PMC found no results. Query: q"), \
                mock.patch.object(lit, "_get", return_value=_Resp(CROSSREF_PAYLOAD)):
            out = lit.pubmed_search("q", 5)
        self.assertIn("Crossref", out)
        self.assertIn("DOI 10.1000/xyz1", out)
        self.assertIn("Awad M, Liu S", out.replace("Liu S", "Liu S"))  # both authors, with initials
        self.assertIn("using Crossref", out)
        self.assertNotIn("xyz2", out)  # a record with no title is not listed

    def test_when_every_source_fails_the_answer_says_why(self):
        def boom(*a, **k):
            raise ConnectionError("offline")

        with mock.patch.object(lit, "pubmed_ids", return_value=[]), \
                mock.patch.object(lit, "europepmc_search", side_effect=boom), \
                mock.patch.object(lit, "_get", side_effect=boom):
            out = lit.pubmed_search("q", 5)
        self.assertIn("Found no results", out)
        self.assertIn("Crossref error", out)
        self.assertIn("Europe PMC error", out)

    def test_crossref_with_no_usable_records_gives_nothing(self):
        with mock.patch.object(lit, "_get", return_value=_Resp({"message": {"items": []}})):
            self.assertEqual(lit.crossref_search("q", 5), "")


if __name__ == "__main__":
    unittest.main()

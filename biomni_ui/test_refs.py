import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import refs

PUBMED_JSON = {
    "result": {
        "uids": ["38480892", "1"],
        "38480892": {
            "title": "APOE4 microglia lipid droplets.",
            "authors": [{"name": "Haney MS"}, {"name": "Palovics R"}, {"name": "Munson CN"}, {"name": "Long C"}],
            "fulljournalname": "Nature",
            "pubdate": "2024 Mar",
            "articleids": [{"idtype": "pubmed", "value": "38480892"}, {"idtype": "doi", "value": "10.1038/s41586-024-07185-7"}],
        },
        "1": {"error": "cannot get document summary"},
    }
}


class Parsers(unittest.TestCase):
    def test_pubmed(self):
        out = refs.parse_pubmed(PUBMED_JSON, ["38480892", "1", "999"])
        rec = out["pmid:38480892"]
        self.assertEqual(rec["title"], "APOE4 microglia lipid droplets")
        self.assertEqual(rec["authors"], "Haney MS and others")
        self.assertEqual((rec["journal"], rec["year"], rec["doi"]), ("Nature", "2024", "10.1038/s41586-024-07185-7"))
        self.assertNotIn("pmid:1", out)  # error record
        self.assertNotIn("pmid:999", out)  # missing record

    def test_crossref(self):
        rec = refs.parse_crossref({"message": {
            "title": ["A <i>great</i> paper"], "DOI": "10.1/x",
            "author": [{"given": "Ada", "family": "Lovelace"}, {"given": "Alan", "family": "Turing"}],
            "container-title": ["Journal of Tests"], "issued": {"date-parts": [[2023, 5]]}}})
        self.assertEqual(rec["title"], "A great paper")
        self.assertEqual(rec["authors"], "A Lovelace, A Turing")
        self.assertEqual((rec["journal"], rec["year"]), ("Journal of Tests", "2023"))
        self.assertIsNone(refs.parse_crossref({}))

    def test_title(self):
        self.assertEqual(refs.parse_title("<html><title>\n  A &amp; B \n</title>"), "A & B")
        self.assertEqual(refs.parse_title("no title"), "")


class Safety(unittest.TestCase):
    def test_private_hosts_are_not_public(self):
        for host in ("localhost", "127.0.0.1", "10.0.0.5", "192.168.1.1", "169.254.169.254", "", "::1"):
            self.assertFalse(refs.is_public_host(host), host)

    def test_public_ip_literal(self):
        self.assertTrue(refs.is_public_host("8.8.8.8"))


class Resolver(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.r = refs.RefResolver(Path(self.tmp.name) / "c" / "refs.json")

    def test_pmid_lookup_is_cached(self):
        resp = mock.Mock(json=lambda: PUBMED_JSON)
        with mock.patch.object(refs, "_get", return_value=resp) as g:
            out = self.r.resolve([{"kind": "pmid", "id": "38480892"}])
            self.assertEqual(out["pmid:38480892"]["journal"], "Nature")
            out2 = self.r.resolve([{"kind": "pmid", "id": "38480892"}])
            self.assertEqual(out2, out)
            self.assertEqual(g.call_count, 1)  # second time comes from the cache
        again = refs.RefResolver(self.r.cache_file)  # and survives a restart
        self.assertIn("pmid:38480892", again.resolve([{"kind": "pmid", "id": "38480892"}]))

    def test_bad_identifiers_are_ignored(self):
        with mock.patch.object(refs, "_get") as g:
            out = self.r.resolve([{"kind": "pmid", "id": "abc"}, {"kind": "doi", "id": "nope"},
                                  {"kind": "url", "id": "file:///etc/passwd"}, {"kind": "x", "id": "1"}])
            self.assertEqual(out, {})
            g.assert_not_called()

    def test_url_to_private_host_is_not_fetched(self):
        with mock.patch.object(refs, "_get") as g:
            out = self.r.resolve([{"kind": "url", "id": "http://127.0.0.1:8765/api/health"}])
            g.assert_not_called()
            self.assertEqual(out["url:http://127.0.0.1:8765/api/health"]["title"], "")

    def test_network_failure_returns_nothing_not_an_error(self):
        import requests

        with mock.patch.object(refs, "_get", side_effect=requests.ConnectionError("down")):
            self.assertEqual(self.r.resolve([{"kind": "pmid", "id": "38480892"}, {"kind": "doi", "id": "10.1038/x"}]), {})

    def test_item_cap(self):
        with mock.patch.object(refs, "_get", side_effect=ValueError()):
            items = [{"kind": "pmid", "id": str(10000 + i)} for i in range(100)]
            self.r.resolve(items)  # must not raise and must only look at the first MAX_ITEMS


if __name__ == "__main__":
    unittest.main()

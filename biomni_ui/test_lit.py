import unittest
from unittest import mock

from biomni_ui import lit

XML = """<PubmedArticleSet>
<PubmedArticle><MedlineCitation><PMID>111</PMID><Article>
<Journal><Title>Nature</Title><JournalIssue><PubDate><Year>2023</Year></PubDate></JournalIssue></Journal>
<ArticleTitle>Real paper by Li.</ArticleTitle>
<AuthorList>
<Author><LastName>Li</LastName><ForeName>Xiaohua</ForeName><Initials>X</Initials><AffiliationInfo><Affiliation>Tsinghua University, Beijing, China.</Affiliation></AffiliationInfo></Author>
<Author><LastName>Smith</LastName><ForeName>Jo</ForeName><Initials>J</Initials></Author>
</AuthorList></Article></MedlineCitation>
<PubmedData><ArticleIdList><ArticleId IdType="doi">10.1/abc</ArticleId></ArticleIdList></PubmedData></PubmedArticle>
<PubmedArticle><MedlineCitation><PMID>222</PMID><Article>
<Journal><Title>Cell</Title><JournalIssue><PubDate><MedlineDate>2021 Jan-Feb</MedlineDate></PubDate></JournalIssue></Journal>
<ArticleTitle>Other person.</ArticleTitle>
<AuthorList><Author><LastName>Li</LastName><ForeName>Wei</ForeName><Initials>W</Initials><AffiliationInfo><Affiliation>MIT, USA.</Affiliation></AffiliationInfo></Author></AuthorList></Article></MedlineCitation></PubmedArticle>
</PubmedArticleSet>"""


class Names(unittest.TestCase):
    def test_both_orders_are_tried(self):
        v = lit.name_variants("Li Xiaohua")
        self.assertIn(("Li", "X", "Xiaohua"), v)
        self.assertIn(("Xiaohua", "L", "Li"), v)

    def test_initials_style(self):
        self.assertEqual(lit.name_variants("Li XH"), [("Li", "XH", "")])
        self.assertEqual(lit.name_variants("Li"), [("Li", "", "")])
        self.assertEqual(lit.name_variants(""), [])

    def test_terms(self):
        t = lit.build_terms("Li XH", orcid="0000-0001-2345-6789")
        self.assertEqual(t[0], "0000-0001-2345-6789[Auid]")
        self.assertIn("Li XH[Author]", t)
        self.assertIn("Li X[Author]", t)
        t2 = lit.build_terms("Li XH", affiliation="Tsinghua")
        self.assertTrue(all("\"Tsinghua\"[Affiliation]" in x for x in t2))


class Parsing(unittest.TestCase):
    def test_records(self):
        recs = lit.parse_records(XML)
        self.assertEqual([r["pmid"] for r in recs], ["111", "222"])
        self.assertEqual(recs[0]["doi"], "10.1/abc")
        self.assertEqual((recs[0]["journal"], recs[0]["year"]), ("Nature", "2023"))
        self.assertEqual(recs[1]["year"], "2021")  # MedlineDate fallback
        self.assertEqual(recs[0]["authors"][0]["affiliation"], "Tsinghua University, Beijing, China.")

    def test_author_matching_kills_namesakes(self):
        recs = lit.parse_records(XML)
        self.assertIsNotNone(lit.matches_author(recs[0], "Li Xiaohua"))
        self.assertIsNone(lit.matches_author(recs[1], "Li Xiaohua"))  # Li Wei is somebody else
        self.assertIsNotNone(lit.matches_author(recs[1], "Li W"))


class Flow(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(lit, "save_csv", return_value="papers_test.csv")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_author_papers_groups_and_filters(self):
        recs = lit.parse_records(XML)
        with mock.patch.object(lit, "pubmed_ids", return_value=["111", "222"]), \
             mock.patch.object(lit, "fetch_records", return_value=recs), mock.patch.object(lit.time, "sleep"):
            out = lit.author_papers("Li Xiaohua")
        self.assertIn("PMID: 111 | Real paper by Li | Li X, Smith J | Nature 2023 | DOI: 10.1/abc", out)
        self.assertIn("Tsinghua University", out)
        self.assertNotIn("PMID: 222", out)  # a different Li
        self.assertIn("1 papers kept", out)

    def test_nothing_found(self):
        with mock.patch.object(lit, "pubmed_ids", return_value=[]), mock.patch.object(lit.time, "sleep"):
            self.assertIn("has no papers by", lit.author_papers("Nobody Here"))

    def test_namesakes_are_flagged(self):
        recs = lit.parse_records(XML)
        with mock.patch.object(lit, "pubmed_ids", return_value=["111", "222"]), \
             mock.patch.object(lit, "fetch_records", return_value=recs), mock.patch.object(lit.time, "sleep"):
            out = lit.author_papers("Li W")  # matches only the second paper... and not Li Xiaohua unless initials fit
        self.assertIn("PMID: 222", out)


if __name__ == "__main__":
    unittest.main()


class ChineseNameTests(unittest.TestCase):
    def test_to_latin_puts_surname_first_and_fixes_jia(self):
        from biomni_ui.lit import to_latin
        self.assertEqual(to_latin("王小明"), "Wang Xiaoming")
        self.assertEqual(to_latin("欧阳娜娜"), "Ouyang Nana")
        self.assertEqual(to_latin("Li Xiaohua"), "Li Xiaohua")

    def test_chinese_name_has_one_reading_and_no_bare_initial_term(self):
        from biomni_ui.lit import build_terms, name_variants
        self.assertEqual(name_variants("王小明"), [("Wang", "XM", "Xiaoming")])
        self.assertNotIn("Wang X[Author]", build_terms("王小明"))

    def test_full_given_name_required_before_initials(self):
        from biomni_ui.lit import matches_author
        rec = {"authors": [{"last": "Wang", "initials": "XM", "fore": "X", "affiliation": ""}]}
        self.assertIsNotNone(matches_author(rec, "王小明"))
        self.assertIsNone(matches_author(rec, "王小明", initials_ok=False))


class AffiliationRelaxation(unittest.TestCase):
    def test_several_affiliations_are_or_ed_and_bare_initial_is_searched(self):
        terms = lit.build_terms("王小明", None, "Shanghai Jiao Tong | Aarhus University")
        self.assertTrue(any("Wang X[Author]" in t for t in terms))
        self.assertTrue(all('"Shanghai Jiao Tong"[Affiliation] OR "Aarhus University"[Affiliation]' in t for t in terms))

    def test_bare_initial_matches_only_when_allowed(self):
        rec = {"authors": [{"last": "Wang", "initials": "X", "fore": "X", "affiliation": ""}]}
        self.assertIsNone(lit.matches_author(rec, "王小明", initials_ok=False))
        self.assertIsNotNone(lit.matches_author(rec, "王小明", initials_ok=False, first_initial_ok=True))


class OpenAlexMixedProfile(unittest.TestCase):
    def test_a_profile_with_unrelated_institutions_is_flagged_and_each_paper_shows_its_own(self):
        def work(title, inst):
            return {"title": title, "publication_year": 2026, "primary_location": {"source": {"display_name": "J"}}, "doi": None, "cited_by_count": 0,
                    "type": "article", "authorships": [{"author": {"id": "https://openalex.org/A1"}, "institutions": [{"display_name": inst}]}]}

        payload = {"results": [work("TIL study", "Example Bio"), work("Manganese neurotoxicity", "University of Georgia")]}
        with mock.patch.object(lit, "_get", return_value=mock.Mock(json=lambda: payload)):
            out = lit.openalex_author_works("A1")
        self.assertTrue(out.startswith("⚠"))
        self.assertIn("Affiliation on this paper: University of Georgia", out)
        self.assertIn("Affiliation on this paper: Example Bio", out)

    def test_a_consistent_profile_has_no_warning(self):
        w = {"title": "T", "publication_year": 2026, "primary_location": None, "doi": None, "cited_by_count": 0, "type": "article",
             "authorships": [{"author": {"id": "https://openalex.org/A1"}, "institutions": [{"display_name": "X"}]}]}
        with mock.patch.object(lit, "_get", return_value=mock.Mock(json=lambda: {"results": [w, w]})):
            self.assertFalse(lit.openalex_author_works("A1").startswith("⚠"))

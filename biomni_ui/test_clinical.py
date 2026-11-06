import unittest
from types import SimpleNamespace
from unittest import mock

from biomni_ui import clinical


def study(nct, title, sponsor="Acme", status="RECRUITING", phase=("PHASE1",)):
    return {"protocolSection": {"identificationModule": {"nctId": nct, "briefTitle": title},
                                "statusModule": {"overallStatus": status, "startDateStruct": {"date": "2025-01"}},
                                "designModule": {"phases": list(phase), "enrollmentInfo": {"count": 9}},
                                "sponsorCollaboratorsModule": {"leadSponsor": {"name": sponsor}},
                                "conditionsModule": {"conditions": ["X"]}, "armsInterventionsModule": {"interventions": [{"name": "BD111"}]}}}


class FakeLLM:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []

    def invoke(self, messages):
        self.calls.append(messages)
        return SimpleNamespace(content=self.replies.pop(0))


class Routing(unittest.TestCase):
    def test_plain_trial_questions_are_taken(self):
        for q in ["示例生物的临床试验", "查询君赛生物的临床研究", "beta thalassemia gene therapy clinical trials", "NCT04211480", "CAR-T 淋巴瘤临床试验有哪些"]:
            self.assertTrue(clinical.wants_clinical(q), q)

    def test_analysis_papers_and_chat_are_not(self):
        for q in ["分析这个 csv 文件", "查询王小明的论文", "CAR-T 的论文综述", "TP53 是什么基因", "1+5等于？", "请用临床试验数据做生存分析并画图"]:
            self.assertFalse(clinical.wants_clinical(q), q)

    def test_subject_is_the_name_without_filler(self):
        self.assertEqual(clinical.subject_of("示例生物的临床试验"), "示例生物")
        self.assertEqual(clinical.subject_of("查询君赛生物的临床研究"), "君赛生物")
        self.assertEqual(clinical.subject_of("CAR-T 淋巴瘤临床试验有哪些"), "CAR-T 淋巴瘤")


class Gather(unittest.TestCase):
    def test_a_chinese_name_is_resolved_to_english_names_and_searched_again(self):
        def fake_search(params):
            term = params.get("query.term") or params.get("query.spons") or params.get("query.intr") or params.get("query.cond")
            return [study("NCT1", "BD111 in HSV keratitis", sponsor="Shanghai ExampleBio Co., Ltd.")] if term == "ExampleBio" else []

        llm = FakeLLM('{"kind":"company","what":"杭州本导生物，基因治疗公司","aliases":["ExampleBio","BD111"]}')
        events = []
        with mock.patch.object(clinical, "_search", side_effect=fake_search), mock.patch.object(clinical.web, "web_search", return_value="[1] 示例生物 | bdgene.com\n    https://bdgene.com\n    CTR20240001 临床试验"):
            data = clinical.gather("示例生物的临床试验", llm, events.append)
        self.assertEqual([t["nct"] for t in data["trials"]], ["NCT1"])
        self.assertEqual(data["info"]["kind"], "company")
        self.assertIn("CTR20240001", data["ctr"])
        codes = [e["code"] for e in events if e["type"] == "code"]
        self.assertTrue(any("ExampleBio" in c for c in codes), codes)

    def test_trials_found_directly_are_not_duplicated_across_the_four_fields(self):
        with mock.patch.object(clinical, "_search", return_value=[study("NCT9", "t")]):
            self.assertEqual(len(clinical.search_all_fields("pembrolizumab")), 1)

    def test_nothing_found_anywhere_is_reported_honestly(self):
        llm = FakeLLM('{"kind":"other","what":"","aliases":[]}', "ClinicalTrials.gov 没有找到任何登记。")
        with mock.patch.object(clinical, "_search", return_value=[]), mock.patch.object(clinical.web, "web_search", return_value="没有结果"):
            text = clinical.run(llm, llm, "某某公司的临床试验", "今天", lambda e: None)
        self.assertIn("没有找到", text)

    def test_a_failing_registry_call_does_not_raise(self):
        with mock.patch.object(clinical.lit, "_json", side_effect=RuntimeError("down")):
            self.assertEqual(clinical.search_all_fields("x"), [])


class RegistryFailures(unittest.TestCase):
    def test_a_failed_search_is_retried_and_then_reported_as_failed_not_as_zero(self):
        from unittest import mock

        from biomni_ui import clinical

        calls = {"n": 0}

        def flaky(params):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise TimeoutError("slow")
            return []

        with mock.patch.object(clinical, "_search", flaky), mock.patch.object(clinical.time, "sleep", lambda s: None):
            hits, failed = clinical.search_checked("x")
        self.assertEqual((hits, failed), ([], 0))  # two failures were retried and recovered

        def down(params):
            raise TimeoutError("down")

        with mock.patch.object(clinical, "_search", down), mock.patch.object(clinical.time, "sleep", lambda s: None):
            hits, failed = clinical.search_checked("x")
        self.assertEqual((hits, failed), ([], 4))

    def test_when_the_registry_never_answers_the_lane_gives_up_instead_of_saying_no_trials(self):
        from unittest import mock

        from biomni_ui import clinical

        events = []
        with mock.patch.object(clinical, "search_checked", lambda name: ([], 4)), mock.patch.object(clinical.web, "web_search", lambda *a, **k: "x"), \
                mock.patch.object(clinical, "resolve_aliases", lambda llm, name, text: {"kind": "company", "what": "", "aliases": []}):
            with self.assertRaises(clinical.RegistryUnavailable):
                clinical.gather("查君赛的临床", None, events.append)
        self.assertTrue(any("search failed" in e.get("text", "") for e in events if e["type"] == "observation"))


class CacheHit(unittest.TestCase):
    def test_a_repeated_search_is_served_from_the_cache_even_if_the_response_refuses_new_attributes(self):
        from unittest import mock

        from biomni_ui import lit

        class Strict:  # like requests_cache's CachedResponse: no new attributes allowed
            __slots__ = ("status_code",)

            def __init__(self):
                self.status_code = 200

            def raise_for_status(self):
                pass

        calls = {"n": 0}

        def fake_get(url, **kw):
            calls["n"] += 1
            return Strict()

        lit._CACHE.clear()
        with mock.patch.object(lit.requests, "get", fake_get):
            a = lit._get("https://example.org/x", params={"q": 1})
            b = lit._get("https://example.org/x", params={"q": 1})  # used to raise AttributeError and count as a failed search
        self.assertIs(a, b)
        self.assertEqual(calls["n"], 1)
        lit._CACHE.clear()


if __name__ == "__main__":
    unittest.main()


class Specificity(unittest.TestCase):
    def test_a_drug_and_condition_combination_is_not_drowned_by_the_drug_alone(self):
        def fake(params):
            term = params.get("query.term") or ""
            if "AND" in term:
                return [study("NCTHCC", "pembrolizumab in HCC")]
            if term == "pembrolizumab":
                return [study(f"NCTX{i}", "pembrolizumab in something else") for i in range(30)]
            return []

        llm = FakeLLM('{"kind":"combo","what":"帕博利珠单抗用于肝癌","aliases":["pembrolizumab","pembrolizumab AND hepatocellular carcinoma"]}')
        with mock.patch.object(clinical, "_search", side_effect=fake), mock.patch.object(clinical.web, "web_search", return_value="x"):
            data = clinical.gather("帕博利珠单抗肝癌的临床试验", llm)
        self.assertEqual([t["nct"] for t in data["trials"]], ["NCTHCC"])
        self.assertIn("not listed", data["scope"])
        self.assertEqual(data["total"], 1)

    def test_company_alias_from_model_knowledge_is_searched(self):
        seen = []

        def fake(params):
            seen.append(params.get("query.term"))
            return [study("NCTJ", "TIL", sponsor="Shanghai Juncell Therapeutics")] if params.get("query.term") == "Juncell Therapeutics" else []

        llm = FakeLLM('{"kind":"company","what":"TIL 公司","aliases":["Juncell Therapeutics"]}')
        with mock.patch.object(clinical, "_search", side_effect=fake), mock.patch.object(clinical.web, "web_search", return_value="x"):
            data = clinical.gather("君赛生物的临床研究", llm)
        self.assertIn("Juncell Therapeutics", seen)
        self.assertEqual(data["total"], 1)

    def test_prompt_allows_translating_standard_terms(self):
        self.assertIn("pembrolizumab", clinical.ALIAS_SYSTEM)
        self.assertIn("Juncell", clinical.ALIAS_SYSTEM)

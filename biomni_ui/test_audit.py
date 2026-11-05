import unittest

from biomni_ui import audit


class Audit(unittest.TestCase):
    SEEN = "PMID: 123456789 | Title | DOI: 10.1007/s12519-025-00955-x\nNCT04560790 | HSV\nhttps://example.org/page/1\n问题：查询"

    def test_everything_seen_passes(self):
        ans = "见 PMID 123456789，DOI: 10.1007/S12519-025-00955-X。（NCT04560790；https://example.org/page/1）"
        self.assertEqual(audit.unsupported(ans, self.SEEN), [])

    def test_invented_identifiers_are_reported(self):
        ans = "PMID: 99999999；DOI 10.1000/abc.def；NCT01234567；https://made.up/x"
        got = audit.unsupported(ans, self.SEEN)
        self.assertEqual(got, ["PMID 99999999", "DOI 10.1000/abc.def", "NCT NCT01234567", "made.up/x"])

    def test_punctuation_and_link_forms_do_not_cause_false_alarms(self):
        ans = "（来源：https://example.org/page/1。）[NCT04560790](https://clinicaltrials.gov/study/NCT04560790)"
        self.assertEqual(audit.unsupported(ans, self.SEEN), [])

    def test_full_width_brackets_are_not_part_of_an_identifier(self):
        seen = "DOI: 10.1056/nejmoa2504835 https://www.example.edu/eng/2025/page.htm"
        ans = "（DOI 10.1056/nejmoa2504835）和（https://www.example.edu/eng/2025/page.htm）以及【10.1056/nejmoa2504835】"
        self.assertEqual(audit.unsupported(ans, seen), [])

    def test_no_citations_no_footnote(self):
        self.assertEqual(audit.footnote(audit.unsupported("TP53 是抑制基因。", "")), "")

    def test_footnote_lists_and_caps(self):
        note = audit.footnote([f"PMID {i}" for i in range(10)])
        self.assertIn("10 in all", note)
        self.assertIn("verify them before use", note)


if __name__ == "__main__":
    unittest.main()


class NativeSearch(unittest.TestCase):
    def test_search_calls_become_step_cards_with_sources(self):
        from biomni_ui import chatgpt_api

        items = chatgpt_api.search_activity([
            {"type": "search", "queries": ["JS001 toripalimab", "君实 JS001"], "sources": [{"type": "url", "url": "https://www.junshipharma.com/pipeline/"}, {"type": "api", "name": "oai-weather"}]},
            {"type": "open_page", "url": "https://www.fda.gov/x"},
        ])
        self.assertEqual(items[0]["tool"], "web_search")
        self.assertEqual(items[0]["results"][0]["domain"], "www.junshipharma.com")
        self.assertIn("JS001 toripalimab", items[0]["query"])
        self.assertEqual(items[1]["results"][0]["url"], "https://www.fda.gov/x")

    def test_request_enables_search_only_when_asked(self):
        from langchain_core.messages import HumanMessage

        from biomni_ui import chatgpt_api

        plain = chatgpt_api.build_request([HumanMessage(content="x")], "m", "low")
        self.assertEqual(plain["tools"], [])
        on = chatgpt_api.build_request([HumanMessage(content="x")], "m", "low", search=True)
        self.assertEqual(on["tools"], [{"type": "web_search"}])
        self.assertEqual(on["tool_choice"], "auto")

    def test_collect_keeps_the_searches_and_the_usage(self):
        from biomni_ui import chatgpt_api

        events = iter([
            {"type": "response.output_item.done", "item": {"type": "web_search_call", "action": {"type": "search", "queries": ["q"]}}},
            {"type": "response.output_text.delta", "delta": "答案"},
            {"type": "response.completed", "response": {"usage": {"output_tokens": 3}}},
        ])
        text, info = chatgpt_api.collect(events)
        self.assertEqual(text, "答案")
        self.assertEqual(info["searches"][0]["queries"], ["q"])
        self.assertEqual(info["usage"]["output_tokens"], 3)


class SearchLinks(unittest.TestCase):
    def test_links_from_the_search_tool_and_their_dois_are_not_flagged(self):
        ans = "见 ([ASCO](https://ascopubs.org/doi/abs/10.1200/JCO-26-01479?utm_source=openai))，PMID: 12345678"
        self.assertEqual(audit.unsupported(ans, "PMID: 12345678"), [])

    def test_a_made_up_doi_next_to_them_is_still_flagged(self):
        ans = "([x](https://a.org/doi/10.1/abc?utm_source=openai)) 另见 DOI 10.9999/invented"
        self.assertEqual(audit.unsupported(ans, ""), ["DOI 10.9999/invented"])

    def test_full_width_square_bracket(self):
        self.assertEqual(audit.unsupported("［DOI 10.1056/nejmoa2504835］", "10.1056/nejmoa2504835"), [])

    def test_calculation_questions(self):
        self.assertTrue(audit.looks_like_calculation("体重 70 kg 的受试者，给药 5 mg/kg，药液浓度 10 mg/mL，需要抽取多少毫升"))
        self.assertFalse(audit.looks_like_calculation("BRCA1 基因的主要功能是什么"))
        self.assertFalse(audit.looks_like_calculation("EGFR L858R 突变的靶向药物有哪些"))


class AgentReply(unittest.TestCase):
    def test_plain_prose_after_a_search_becomes_a_solution(self):
        from biomni_ui import chatgpt_api as c

        self.assertEqual(c.as_agent_reply("答案"), "<solution>答案</solution>")
        self.assertEqual(c.as_agent_reply("<solution>x</solution>"), "<solution>x</solution>")
        self.assertEqual(c.as_agent_reply("先查 <execute>print(1)"), "先查 <execute>print(1)")
        self.assertEqual(c.as_agent_reply("  "), "  ")


class BuiltFromIdentifiers(unittest.TestCase):
    def test_a_page_built_from_an_accession_the_tools_returned(self):
        seen = "VCV000017677 NM_007294.4(BRCA1):c.5266dup"
        self.assertEqual(audit.unsupported("[ClinVar](https://www.ncbi.nlm.nih.gov/clinvar/variation/17677/)", seen.replace("VCV000017677", "VCV000017677 17677")), [])
        self.assertEqual(audit.unsupported("https://www.ncbi.nlm.nih.gov/clinvar/variation/99999/", seen), ["ncbi.nlm.nih.gov/clinvar/variation/99999"])


class Ungrounded(unittest.TestCase):
    EVIDENCE = "NDA accepted on 2026-10-26. 98 patients. total 1,234 records. BD111 phase II. updated Oct 28, 2026. 2025年3月5日 启动 https://x.org/a"

    def test_supported_dates_figures_and_codes_pass_in_any_notation(self):
        answer = "2026-10-26 NDA 获受理。登记 1234 条。BD111 进入 II 期。2026年10月28日 纳入优先审评。2025/3/5 启动。"
        self.assertEqual(audit.ungrounded(answer, self.EVIDENCE), [])

    def test_a_date_figure_or_code_with_nothing_behind_it_is_found(self):
        found = audit.ungrounded("2022-06 获 FDA 孤儿药资格。平均随访 25.5 个月。BD999 暂停。", self.EVIDENCE)
        tokens = {t for f in found for t in f["missing"]}
        self.assertEqual(tokens, {"2022-06", "25.5", "BD999"})

    def test_what_the_model_marked_what_is_small_and_what_other_checks_cover_are_left_alone(self):
        answer = ("ASCO LBA9509 的结果未核实。共 3 项试验，其中 2 项招募中。成立于 2019 年。见 PMID 12345678 和 https://nope.org/1。\n"
                  "```python\nx = 987654\n```")
        self.assertEqual(audit.ungrounded(answer, self.EVIDENCE), [])

    def test_a_count_of_ten_or_more_is_checked_like_any_other_figure(self):
        self.assertTrue(audit.ungrounded("共 20 项试验，其中 15 项招募中。", self.EVIDENCE))

    def test_the_note_names_the_sentences_and_what_is_missing(self):
        note = audit.ungrounded_note(audit.ungrounded("平均随访 25.5 个月。", self.EVIDENCE))
        self.assertIn("25.5", note)
        self.assertIn("do not rely on them", note)
        self.assertEqual(audit.ungrounded_note([]), "")


    def test_a_rounded_figure_or_a_percentage_of_the_evidence_is_backed_an_invented_one_is_not(self):
        evidence = '{"score": 0.85570321, "other": 0.7315123, "size": 85277}'
        self.assertEqual(audit.ungrounded("评分 0.8557，另一项 0.73，大小 85,277 字节，约 85.6%。", evidence), [])
        found = audit.ungrounded("评分 0.9123。", evidence)
        self.assertEqual(found[0]["missing"], ["0.9123"])

    def test_an_illustration_and_a_conventional_threshold_are_not_flagged(self):
        self.assertEqual(audit.ungrounded("例如：把这个 VCF 里 MAF 小于 0.01 的位点留下，统计 1500 个基因。", ""), [])
        self.assertEqual(audit.ungrounded("显著性阈值取 0.05。", ""), [])

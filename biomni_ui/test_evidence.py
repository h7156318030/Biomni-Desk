import unittest

from biomni_ui import audit, native_agent


class EvidenceFromEvents(unittest.TestCase):
    def test_a_figure_the_model_typed_into_its_own_query_is_not_evidence(self):
        events = [{"type": "tool", "tool": "web_search", "query": "TP53 tetramerization residues 325 356", "results": []}]
        evidence = audit.evidence_from_events(events)
        self.assertNotIn("325", evidence)
        flags = audit.ungrounded("四聚化区，约 325–356，促进四聚体形成。", evidence)
        self.assertTrue(flags)  # the sentence is listed for checking

    def test_search_results_and_command_output_are_evidence(self):
        events = [
            {"type": "tool", "tool": "web_search", "query": "q", "results": [{"title": "T", "domain": "x.org", "url": "https://x.org/1", "snippet": "DNA binding 94 292"}]},
            {"type": "observation", "text": "entry_protein_locations: start 319, end 357"},
        ]
        evidence = audit.evidence_from_events(events)
        self.assertIn("94 292", evidence)
        self.assertIn("319", evidence)

    def test_event_timestamps_and_sequence_numbers_are_not_evidence(self):
        events = [{"type": "observation", "text": "ok", "seq": 19, "ts": 1793862792.7356684}]
        evidence = audit.evidence_from_events(events)
        self.assertNotIn("7356684", evidence)
        self.assertNotIn("1793862792", evidence)


class CompactDates(unittest.TestCase):
    def test_a_date_written_as_eight_digits_in_a_result_is_the_same_day(self):
        evidence = "陈明 杭州本导生物医药科技有限公司 董事 20230224 否"
        self.assertEqual(audit.ungrounded("陈明自2023年2月24日起担任董事。", evidence), [])

    def test_a_date_that_appears_nowhere_is_still_flagged(self):
        evidence = "陈明 杭州本导生物医药科技有限公司 董事 20230224"
        self.assertTrue(audit.ungrounded("陈明自2023年3月1日起担任董事。", evidence))

    def test_a_long_number_is_not_mistaken_for_a_date(self):
        evidence = "record 2023022412345 with id"
        self.assertTrue(audit.ungrounded("发布于2023年2月24日。", evidence))


class ModelWrittenInput(unittest.TestCase):
    def test_the_models_own_commands_and_queries_are_not_in_its_evidence(self):
        items = [
            {"type": "function_call", "arguments": '{"query": "residues 325 356"}'},
            {"type": "function_call_output", "output": "no domain data"},
            {"type": "web_search_call", "action": {"query": "tetramerization 363"}},
        ]
        text = native_agent.evidence_text(items, "the question")
        self.assertIn("no domain data", text)
        self.assertIn("the question", text)
        self.assertNotIn("325", text)
        self.assertNotIn("363", text)


class SpansAndPercentages(unittest.TestCase):
    def test_a_span_whose_two_ends_are_close_together_in_the_evidence_is_backed(self):
        evidence = '"entry_protein_locations": [{"fragments": [{"start": 319, "end": 357}]}]'
        self.assertEqual(audit.ungrounded("四聚化区，约 319–357。", evidence), [])

    def test_a_span_with_only_one_end_in_the_evidence_is_not_backed(self):
        evidence = "the domain starts at 319 and is described elsewhere"
        self.assertTrue(audit.ungrounded("四聚化区，约 319–357。", evidence))

    def test_a_span_of_residues_the_evidence_does_not_give_is_flagged(self):
        evidence = "DNA binding domain 94 292"
        self.assertEqual(audit.ungrounded("DNA 结合核心域，约 94–292。", evidence), [])  # both ends are in the evidence, next to each other
        self.assertTrue(audit.ungrounded("四聚化区，约 325–356。", evidence))  # neither end is

    def test_a_span_of_years_is_not_checked(self):
        self.assertEqual(audit.ungrounded("研究期间为 2019–2023 年。", ""), [])

    def test_a_percentage_is_checked_whatever_its_size(self):
        self.assertTrue(audit.ungrounded("客观缓解率为 37.1%。", "no rate given here"))
        self.assertEqual(audit.ungrounded("客观缓解率为 37.1%。", "overall response rate 37.1% in the trial"), [])
        self.assertTrue(audit.ungrounded("约 7% 的患者出现不良反应。", "no figure"))


class CleanupAndFilter(unittest.TestCase):
    def test_a_non_numeric_citation_marker_becomes_plain_words(self):
        out = native_agent.clean_answer("见 [@数据库查询，本轮 Open Targets] 的结果。")
        self.assertIn("(数据库查询，本轮 Open Targets)", out)
        self.assertNotIn("[@", out)

class CitationIdentifiers(unittest.TestCase):
    def test_a_doi_no_tool_returned_is_listed_for_checking(self):
        note = audit.footnote(audit.unsupported("CodeBreaK 300 见 10.1056/NEJMoa2308795。", "PMID: 37870968 Sotorasib"))
        self.assertIn("Citation check", note)
        self.assertIn("10.1056", note)

    def test_an_identifier_the_tools_printed_is_not_listed(self):
        self.assertEqual(audit.unsupported("PMID 37870968 见上。", "PMID: 37870968 Sotorasib"), [])


class BoldMarkersAreNotPartOfAnIdentifier(unittest.TestCase):
    def test_a_doi_in_bold_is_the_same_doi(self):
        self.assertEqual(audit.unsupported("参见 **10.1056/NEJMoa2105281**。", "10.1056/NEJMoa2105281 trial"), [])


if __name__ == "__main__":
    unittest.main()

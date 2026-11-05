import unittest

from biomni_ui import evalbench


Q_GNOMAD = {"id": "t1", "category": "数据库", "question": "查 TP53 的 gnomAD 约束指标", "tools": ["gnomad_constraint"],
            "facts": [["0.418"], ["1.000", "1.0"]], "must_source": False}
Q_SOURCE = {"id": "t2", "category": "文献", "question": "sotorasib 何时获批？请给出来源。", "tools": [],
            "facts": [["2021"]], "must_source": True}


class Scoring(unittest.TestCase):
    def test_a_correct_run_scores_full_facts_and_the_expected_tool(self):
        events = [
            {"type": "code", "code": "gnomad_constraint({\"gene\": \"TP53\"})"},
            {"type": "observation", "text": "gnomAD：TP53 pLI=1.000，LOEUF=0.418"},
            {"type": "llm", "seconds": 4.0, "reasoning_tokens": 120},
            {"type": "answer", "text": "TP53 的 LOEUF 为 0.418，pLI 为 1.000。"},
            {"type": "done"},
        ]
        row = evalbench.score(Q_GNOMAD, "done", events)
        self.assertEqual(row["facts_ok"], 2)
        self.assertEqual(row["facts_rate"], 1.0)
        self.assertTrue(row["tool_hit"])
        self.assertEqual(row["errors"], 0)
        self.assertEqual(row["llm_seconds"], 4.0)
        self.assertEqual(row["reasoning_tokens"], 120)

    def test_a_run_that_never_calls_the_expected_tool_and_misses_a_fact_scores_low(self):
        events = [{"type": "answer", "text": "LOEUF 大约是 0.5。"}, {"type": "done"}]
        row = evalbench.score(Q_GNOMAD, "done", events)
        self.assertFalse(row["tool_hit"])
        self.assertEqual(row["facts_ok"], 0)

    def test_a_required_source_is_recognised_by_a_url_pmid_or_doi(self):
        for answer in ("sotorasib 于 2021 年获批。来源：https://example.org/a", "2021 年获批，PMID: 34161704", "2021 年获批，DOI 10.1056/NEJMoa2105281"):
            events = [{"type": "answer", "text": answer}]
            self.assertTrue(evalbench.score(Q_SOURCE, "done", events)["source_ok"], answer)
        events = [{"type": "answer", "text": "2021 年获批。"}]
        self.assertFalse(evalbench.score(Q_SOURCE, "done", events)["source_ok"])

    def test_an_error_event_is_counted_and_the_status_is_kept(self):
        events = [{"type": "error", "message": "boom"}, {"type": "answer", "text": ""}]
        row = evalbench.score(Q_GNOMAD, "error", events)
        self.assertEqual(row["status"], "error")
        self.assertEqual(row["errors"], 1)


class Summary(unittest.TestCase):
    def test_the_summary_averages_only_the_questions_that_apply(self):
        rows = [
            evalbench.score(Q_GNOMAD, "done", [{"type": "code", "code": "gnomad_constraint({})"}, {"type": "answer", "text": "0.418 和 1.000"}, {"type": "done"}]),
            evalbench.score(Q_SOURCE, "done", [{"type": "answer", "text": "2021 年，见 PMID 34161704"}, {"type": "done"}]),
        ]
        s = evalbench.summarise(rows)
        self.assertEqual(s["questions"], 2)
        self.assertEqual(s["finished"], 2)
        self.assertEqual(s["tool_hit_rate"], 1.0)  # only the question that names a tool counts
        self.assertEqual(s["source_rate"], 1.0)  # only the question that needs a source counts
        self.assertEqual(s["facts_rate"], 1.0)


class Questions(unittest.TestCase):
    def test_the_benchmark_has_thirty_unique_questions_with_facts(self):
        qs = evalbench.load_questions()
        self.assertEqual(len(qs), 30)
        self.assertEqual(len({q["id"] for q in qs}), 30)
        for q in qs:
            self.assertTrue(q["facts"], q["id"])
            self.assertIsInstance(q["tools"], list)


if __name__ == "__main__":
    unittest.main()

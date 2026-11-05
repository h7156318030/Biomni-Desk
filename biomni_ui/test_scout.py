import time
import unittest
from types import SimpleNamespace
from unittest import mock

from biomni_ui import scout


class Plan(unittest.TestCase):
    def test_valid_probes_are_kept_and_unknown_or_malformed_ones_dropped(self):
        text = ('{"skip": false, "why": "公司名", "probes": ['
                '{"tool":"web_search","args":{"query":"示例生物"}},'
                '{"tool":"clinical_trials","args":{"condition":"HSV keratitis","intervention":"BD111"}},'
                '{"tool":"rm_rf","args":{"x":1}},'
                '{"tool":"pubmed_search","args":{"nonsense":"x"}},'
                '{"tool":"web_search","args":{"query":"   "}},'
                '{"tool":"web_search","args":{"query":"示例生物"}}]}')
        skip, why, probes = scout.parse_plan(text)
        self.assertFalse(skip)
        self.assertEqual([p["tool"] for p in probes], ["web_search", "clinical_trials"])
        self.assertEqual(why, "公司名")

    def test_at_most_four_probes(self):
        many = ",".join(f'{{"tool":"web_search","args":{{"query":"q{i}"}}}}' for i in range(9))
        self.assertEqual(len(scout.parse_plan('{"probes":[' + many + "]}")[2]), scout.MAX_PROBES)

    def test_skip_and_garbage_mean_no_probes(self):
        self.assertTrue(scout.parse_plan('{"skip": true, "probes": [{"tool":"web_search","args":{"query":"x"}}]}')[0])
        self.assertTrue(scout.parse_plan("not json")[0])
        self.assertTrue(scout.parse_plan('{"probes": []}')[0])


class Run(unittest.TestCase):
    def llm(self, reply):
        return SimpleNamespace(invoke=lambda messages: SimpleNamespace(content=reply))

    def test_probes_run_in_parallel_and_the_digest_is_labelled_and_bounded(self):
        calls = []

        def slow(**kw):
            calls.append(kw)
            time.sleep(0.4)
            return "结果" * 2000

        reply = '{"probes":[{"tool":"web_search","args":{"query":"a"}},{"tool":"pubmed_search","args":{"query":"b"}},{"tool":"geo_search","args":{"query":"c"}}]}'
        events = []
        patched = {k: (slow, v[1]) for k, v in scout.PROBES.items()}
        with mock.patch.dict(scout.PROBES, patched, clear=True):
            t = time.time()
            digest = scout.run(self.llm(reply), "q", "今天", events.append)
        self.assertLess(time.time() - t, 1.0)  # three 0.4 s probes took one 0.4 s, not three
        self.assertIn("web_search(query='a')", digest)
        self.assertLessEqual(len(digest), scout.DIGEST_CHARS + 600)
        self.assertIn("do not give up just because they found nothing", digest)
        self.assertEqual(sum(e["type"] == "code" for e in events), 3)

    def test_a_failing_probe_is_shown_but_not_passed_on(self):
        def boom(**kw):
            raise RuntimeError("down")

        reply = '{"probes":[{"tool":"web_search","args":{"query":"a"}}]}'
        with mock.patch.dict(scout.PROBES, {"web_search": (boom, "x")}, clear=True):
            self.assertEqual(scout.run(self.llm(reply), "q", "今天"), "")

    def test_skip_returns_nothing_and_never_raises(self):
        self.assertEqual(scout.run(self.llm('{"skip": true}'), "1+5", "今天"), "")
        bad = SimpleNamespace(invoke=mock.Mock(side_effect=RuntimeError("model down")))
        self.assertEqual(scout.run(bad, "q", "今天"), "")


if __name__ == "__main__":
    unittest.main()


class PromptHints(unittest.TestCase):
    def test_prompt_asks_for_step_titles_verification_and_file_locations(self):
        from biomni_ui import runner

        t = runner.Task("查询 TP53", "c1")
        self.assertIn("one-line comment", t.agent_prompt)
        self.assertIn("check it in the next step", t.agent_prompt)
        self.assertIn("uploads", runner.workspace_line())

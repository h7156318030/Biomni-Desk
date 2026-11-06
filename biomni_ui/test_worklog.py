import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import worklog


class WorkLog(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        patcher = mock.patch.object(worklog, "STORE", Path(d.name) / "work_log.json")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_finished_task_is_recorded_for_its_project(self):
        worklog.record("p1", "conv-a", "t1", "Look up the UniProt accession of TP53", "P04637, Cellular tumor antigen p53")
        worklog.record("p2", "conv-b", "t2", "Summarise the paper", "The paper reports three cohorts")
        self.assertEqual([i["task_id"] for i in worklog.list_items("p1")], ["t1"])
        self.assertEqual(len(worklog.list_items()), 2)

    def test_an_empty_answer_is_not_kept(self):
        self.assertIsNone(worklog.record("p1", "c", "t", "question", ""))
        self.assertEqual(worklog.list_items(), [])

    def test_a_later_task_in_the_project_gets_the_earlier_work_that_matches(self):
        worklog.record("p1", "old-conv", "t1", "Look up the UniProt accession of TP53", "P04637 for TP53")
        worklog.record("p1", "old-conv", "t2", "Plot the volcano chart of the RNA-seq", "Saved volcano.png")
        text = worklog.block("p1", query="what was the TP53 accession again", exclude_conversation="new-conv")
        self.assertIn("P04637", text)
        self.assertIn("Earlier work in this project", text)

    def test_the_current_conversation_is_not_repeated(self):
        worklog.record("p1", "same-conv", "t1", "Look up the UniProt accession of TP53", "P04637")
        self.assertEqual(worklog.block("p1", query="TP53", exclude_conversation="same-conv"), "")

    def test_other_projects_do_not_leak_in(self):
        worklog.record("p1", "c1", "t1", "Look up TP53", "P04637")
        self.assertEqual(worklog.block("p2", query="TP53", exclude_conversation="c9"), "")

    def test_the_budget_is_respected(self):
        for k in range(20):
            worklog.record("p1", f"c{k}", f"t{k}", f"Question number {k} about gene {k}", "answer " * 60)
        text = worklog.block("p1", query="gene", exclude_conversation="none", budget=800)
        self.assertLessEqual(len(text), 800 + 400)  # the budget, plus the heading
        self.assertGreater(text.count("\n- "), 0)

    def test_memory_switched_off_gives_nothing(self):
        worklog.record("p1", "c1", "t1", "Look up TP53", "P04637")
        self.assertEqual(worklog.block("p1", query="TP53", exclude_conversation="c9", enabled=False), "")

    def test_clearing_one_project_keeps_the_others(self):
        worklog.record("p1", "c1", "t1", "Look up TP53", "P04637")
        worklog.record("p2", "c2", "t2", "Look up BRCA1", "P38398")
        self.assertEqual(worklog.delete("p1"), 1)
        self.assertEqual([i["project_id"] for i in worklog.list_items()], ["p2"])
        self.assertEqual(worklog.delete(None), 1)
        self.assertEqual(worklog.list_items(), [])


if __name__ == "__main__":
    unittest.main()

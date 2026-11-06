import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from biomni_ui import receipts


class FailureHeuristic(unittest.TestCase):
    def test_known_failure_messages_are_failed(self):
        self.assertTrue(receipts.looks_failed("No tool named foo. Look it up with find_tools first."))
        self.assertTrue(receipts.looks_failed("Tool query_x cannot run on this computer (missing package)."))
        self.assertTrue(receipts.looks_failed("Could not load tool bar: ImportError: x"))
        self.assertTrue(receipts.looks_failed("Traceback (most recent call last):\n  File ..."))

    def test_ordinary_output_is_not_failed(self):
        self.assertFalse(receipts.looks_failed('{"results": [{"accession": "P04637"}]}'))
        self.assertFalse(receipts.looks_failed("Tool results: 3 rows returned"))  # starts with "Tool" but no failure phrase
        self.assertFalse(receipts.looks_failed(""))


class RecordAndVerify(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cwd = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_receipt_hashes_the_saved_result_and_verifies(self):
        result = "line one\nline two: 中文结果"
        rec = receipts.record(self.cwd, "call_1", "query_uniprot", {"endpoint": "uniprotkb/search?query=TP53", "max_results": 5}, result, 1.234)
        self.assertEqual(rec["result_sha256"], hashlib.sha256(result.encode("utf-8")).hexdigest())
        self.assertEqual(rec["tool"], "query_uniprot")
        self.assertFalse(rec["failed"])
        self.assertTrue(receipts.verify(self.cwd, rec))
        self.assertIn('"max_results": 5', rec["arguments"])  # arguments are stored with sorted keys

    def test_tampered_result_file_fails_verification(self):
        rec = receipts.record(self.cwd, "c", "run_tool", {}, "original output", 0.1)
        (self.cwd / rec["result_file"]).write_text("changed output", encoding="utf-8")
        self.assertFalse(receipts.verify(self.cwd, rec))

    def test_arguments_are_truncated_and_marked(self):
        big = {"text": "x" * (receipts.ARG_LIMIT + 500)}
        rec = receipts.record(self.cwd, "c", "python", big, "ok", 0.0)
        self.assertLessEqual(len(rec["arguments"]), receipts.ARG_LIMIT)
        self.assertTrue(rec["arguments_truncated"])

    def test_unserialisable_arguments_do_not_raise(self):
        rec = receipts.record(self.cwd, "c", "run_tool", {"path": Path("a/b")}, "ok", 0.0)
        self.assertIn("a", rec["arguments"])

    def test_read_all_keeps_order_and_count_follows(self):
        receipts.record(self.cwd, "1", "a", {}, "ok", 0.0)
        receipts.record(self.cwd, "2", "b", {}, "ok", 0.0)
        rows = receipts.read_all(self.cwd)
        self.assertEqual([r["tool"] for r in rows], ["a", "b"])
        self.assertEqual(receipts.count(self.cwd), 2)

    def test_a_torn_line_is_skipped(self):
        receipts.record(self.cwd, "1", "a", {}, "ok", 0.0)
        with open(self.cwd / "execution_trace" / "receipts.jsonl", "a", encoding="utf-8") as f:
            f.write('{"tool": "trun')  # interrupted write
        self.assertEqual(len(receipts.read_all(self.cwd)), 1)


class QcSummary(unittest.TestCase):
    def rec(self, tool, failed, rid=None):
        return {"id": rid or tool, "tool": tool, "failed": failed, "summary": "No tool named x" if failed else "ok"}

    def test_failure_followed_by_success_of_same_tool_does_not_block(self):
        s = receipts.qc_summary([self.rec("query_uniprot", True), self.rec("query_uniprot", False)])
        self.assertEqual(s["failed_calls"], 1)
        self.assertEqual(s["unresolved_failures"], [])
        self.assertTrue(s["gate_pass"])

    def test_failure_with_no_later_success_blocks(self):
        s = receipts.qc_summary([self.rec("query_pdb", False), self.rec("query_chembl", True)])
        self.assertEqual([x["tool"] for x in s["unresolved_failures"]], ["query_chembl"])
        self.assertFalse(s["gate_pass"])

    def test_unsupported_identifiers_block_the_gate(self):
        s = receipts.qc_summary([self.rec("query_uniprot", False)], unsupported=["PMID 12345678"])
        self.assertFalse(s["gate_pass"])
        self.assertEqual(s["unsupported_identifiers"], ["PMID 12345678"])

    def test_unverified_specifics_are_listed_but_do_not_block(self):
        s = receipts.qc_summary([self.rec("query_uniprot", False)], unverified=["约 325–356"])
        self.assertEqual(s["unverified_specifics"], ["约 325–356"])
        self.assertTrue(s["gate_pass"])

    def test_qc_file_is_written_as_json(self):
        with tempfile.TemporaryDirectory() as d:
            rel = receipts.write_qc(d, receipts.qc_summary([self.rec("a", False)]))
            data = json.loads((Path(d) / rel).read_text(encoding="utf-8"))
            self.assertEqual(data["calls"], 1)
            self.assertTrue(data["gate_pass"])


if __name__ == "__main__":
    unittest.main()

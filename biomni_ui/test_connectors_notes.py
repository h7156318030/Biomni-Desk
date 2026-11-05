import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import connectors, notes


class Connectors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(connectors, "STORE", Path(self.tmp.name) / "connectors.json")
        p.start()
        self.addCleanup(p.stop)

    def test_a_switched_off_connector_is_reported_off_and_can_be_switched_back_on(self):
        self.assertTrue(connectors.enabled("gnomad_constraint"))
        self.assertTrue(connectors.set_enabled("gnomad", False))
        self.assertFalse(connectors.enabled("gnomad_constraint"))
        self.assertIn("gnomAD", connectors.off_message("gnomad_constraint"))
        self.assertFalse(next(g for g in connectors.listing() if g["id"] == "gnomad")["enabled"])
        self.assertTrue(connectors.set_enabled("gnomad", True))
        self.assertTrue(connectors.enabled("gnomad_constraint"))

    def test_an_unknown_connector_is_refused(self):
        self.assertFalse(connectors.set_enabled("no-such-db", False))

    def test_a_tool_that_belongs_to_no_connector_stays_on(self):
        connectors.set_enabled("gnomad", False)
        self.assertTrue(connectors.enabled("query_interpro"))

    def test_the_guard_refuses_the_function_when_off_and_calls_it_when_on(self):
        ns = {"gnomad_constraint": lambda gene: f"constraint of {gene}"}
        connectors.guard(ns)
        self.assertEqual(ns["gnomad_constraint"]("TP53"), "constraint of TP53")
        connectors.set_enabled("gnomad", False)
        self.assertIn("switched off", ns["gnomad_constraint"]("TP53"))
        connectors.guard(ns)  # idempotent: guarding twice does not stack
        self.assertTrue(ns["gnomad_constraint"]._connector_guarded)

    def test_the_tool_list_offered_to_the_model_leaves_out_a_switched_off_database(self):
        from biomni_ui import native_agent

        on = [s["name"] for s in native_agent.direct_specs(None)]
        self.assertIn("gnomad_constraint", on)
        connectors.set_enabled("gnomad", False)
        off = [s["name"] for s in native_agent.direct_specs(None)]
        self.assertNotIn("gnomad_constraint", off)

    def test_run_tool_refuses_a_switched_off_tool_without_running_it(self):
        from biomni_ui import biomni_tools

        connectors.set_enabled("gnomad", False)
        out = biomni_tools.run_tool("gnomad_constraint", {"gene": "TP53"})
        self.assertIn("switched off", out)


class RememberNotes(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(notes, "STORE", Path(self.tmp.name) / "memory_notes.json")
        p.start()
        self.addCleanup(p.stop)

    def test_only_a_pure_remember_message_is_a_note(self):
        self.assertEqual(notes.parse("记住：我的研究对象是小鼠"), "我的研究对象是小鼠")
        self.assertEqual(notes.parse("Remember: my species is mouse"), "my species is mouse")
        self.assertEqual(notes.parse("请记住 只用 PubMed 的结果"), "只用 PubMed 的结果")
        self.assertIsNone(notes.parse("记住这个基因是 TP53，然后查它的 gnomAD 指标？"))
        self.assertIsNone(notes.parse("TP53 的结构域是什么"))
        self.assertIsNone(notes.parse("记住"))

    def test_notes_are_added_listed_deleted_and_not_stored_twice(self):
        a = notes.add("研究对象是小鼠")
        self.assertEqual(notes.add("研究对象是小鼠")["id"], a["id"])
        self.assertEqual(len(notes.list_items()), 1)
        self.assertTrue(notes.delete(a["id"]))
        self.assertEqual(notes.list_items(), [])
        self.assertFalse(notes.delete(a["id"]))

    def test_the_block_goes_into_instructions_and_is_empty_without_notes(self):
        self.assertEqual(notes.block(), "")
        notes.add("只用 PubMed 的结果")
        text = notes.block()
        self.assertIn("Things the user asked to remember", text)
        self.assertIn("- 只用 PubMed 的结果", text)

    def test_only_the_newest_notes_are_kept(self):
        for i in range(notes.MAX_ITEMS + 3):
            notes.add(f"事项 {i}")
        items = notes.list_items()
        self.assertEqual(len(items), notes.MAX_ITEMS)
        self.assertEqual(items[-1]["text"], f"事项 {notes.MAX_ITEMS + 2}")


if __name__ == "__main__":
    unittest.main()

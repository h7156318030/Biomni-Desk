import json
import tempfile
import unittest
from pathlib import Path

from biomni_ui import native_agent, notes


class NotesStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = notes.STORE
        notes.STORE = Path(self._tmp.name) / "memory_notes.json"

    def tearDown(self):
        notes.STORE = self._saved
        self._tmp.cleanup()

    def test_proposed_note_is_not_used_until_approved(self):
        item = notes.propose("Use GRCh38 coordinates", "proj1")
        self.assertEqual(item["status"], notes.PROPOSED)
        self.assertEqual(notes.block("proj1"), "")
        self.assertTrue(notes.approve(item["id"]))
        self.assertIn("Use GRCh38 coordinates", notes.block("proj1"))

    def test_scope_limits_which_project_sees_a_note(self):
        notes.add("Species: mouse", "proj1")
        notes.add("Always cite PMIDs")  # all projects
        self.assertIn("Species: mouse", notes.block("proj1"))
        self.assertNotIn("Species: mouse", notes.block("proj2"))
        self.assertIn("Always cite PMIDs", notes.block("proj2"))
        self.assertIn("Always cite PMIDs", notes.block(None))

    def test_approving_an_existing_proposal_does_not_duplicate_it(self):
        p = notes.propose("Use log2 fold change", None)
        again = notes.add("Use log2 fold change", None)
        self.assertEqual(again["id"], p["id"])
        self.assertEqual(again["status"], notes.APPROVED)
        self.assertEqual(len(notes.list_items()), 1)

    def test_old_notes_without_status_stay_approved_for_every_project(self):
        notes.STORE.write_text(json.dumps({"items": [{"id": "old1", "text": "Old rule", "created": 1.0}]}), encoding="utf-8")
        self.assertIn("Old rule", notes.block("any"))
        self.assertEqual(notes.list_items()[0]["status"], notes.APPROVED)

    def test_delete_and_missing_ids(self):
        item = notes.add("temp")
        self.assertTrue(notes.delete(item["id"]))
        self.assertFalse(notes.delete(item["id"]))
        self.assertFalse(notes.approve("nope"))


def final(text):
    return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}], {}


class AgentProposal(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = notes.STORE
        notes.STORE = Path(self._tmp.name) / "memory_notes.json"

    def tearDown(self):
        notes.STORE = self._saved
        self._tmp.cleanup()

    def test_the_agent_can_only_propose_and_the_proposal_is_scoped_to_the_project(self):
        state = {"n": 0}

        def fake(model, effort, instructions, items, tools, on_text=None):
            state["n"] += 1
            if state["n"] == 1:
                import json as _json

                return [{"type": "function_call", "call_id": "p1", "name": "propose_memory",
                         "arguments": _json.dumps({"title": "remember", "text": "Use hg38 for all genomic work"})}], {}
            return final("Done.")

        with tempfile.TemporaryDirectory() as d:
            native_agent._run_loop(sess="t-notes", model="m", effort="low", question="q", history=[], instructions="sys", emit=lambda e: None,
                                   cancel=lambda: False, cwd=Path(d), call=fake, allow_ask=False, project_id="proj9")
        stored = notes.list_items()
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["status"], notes.PROPOSED)
        self.assertEqual(stored[0]["project_id"], "proj9")
        self.assertNotIn("hg38", notes.block("proj9"))  # not in force until the user approves


class RecallAndSearch(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = notes.STORE
        notes.STORE = Path(self._tmp.name) / "memory_notes.json"

    def tearDown(self):
        notes.STORE = self._saved
        self._tmp.cleanup()

    def test_small_memory_is_used_whole_whatever_the_question(self):
        notes.add("Use GRCh38 coordinates")
        notes.add("Species: mouse", "proj1")
        text = notes.recall("compute a p-value", "proj1")
        self.assertIn("GRCh38", text)
        self.assertIn("mouse", text)

    def test_large_memory_keeps_the_notes_that_match_the_question(self):
        for k in range(30):
            notes.add(f"Unrelated convention number {k} about plotting colours and axis labels {'x' * 40}")
        notes.add("Gene symbols follow HGNC naming for human TP53")
        text = notes.recall("look up TP53 variants", None)
        self.assertIn("HGNC", text)
        self.assertLessEqual(len(text), notes.RECALL_CHARS + 200)  # budget, plus the heading
        self.assertLessEqual(text.count("\n- "), notes.RECALL_COUNT)

    def test_chinese_question_matches_chinese_note(self):
        for k in range(30):
            notes.add(f"无关的约定第{k}条：图表颜色与坐标轴标签的样式说明，填充内容{'字' * 40}")
        notes.add("标准化时统一使用 TPM 作为表达量单位")
        self.assertIn("TPM", notes.recall("这个数据的表达量用哪个单位？", None))

    def test_disabled_memory_recalls_nothing(self):
        notes.add("Always cite PMIDs")
        self.assertEqual(notes.recall("anything", None, enabled=False), "")

    def test_search_matches_text_and_category_and_filters_status(self):
        notes.add("Use hg38 for genomic work", category="Convention")
        notes.propose("Prefer Ensembl IDs", None, category="Preference")
        self.assertEqual([i["text"] for i in notes.search("hg38")], ["Use hg38 for genomic work"])
        self.assertEqual([i["text"] for i in notes.search("convention")], ["Use hg38 for genomic work"])
        self.assertEqual([i["text"] for i in notes.search("", notes.PROPOSED)], ["Prefer Ensembl IDs"])
        self.assertEqual(len(notes.search("")), 2)

    def test_update_changes_only_the_given_fields(self):
        item = notes.add("Old wording", "proj1", category="General")
        edited = notes.update(item["id"], text="New wording")
        self.assertEqual((edited["text"], edited["category"], edited["project_id"]), ("New wording", "General", "proj1"))
        moved = notes.update(item["id"], project_id=None)
        self.assertIsNone(moved["project_id"])
        self.assertIsNone(notes.update("missing", text="x"))
        with self.assertRaises(ValueError):
            notes.update(item["id"], text="   ")


class LearnSuggestions(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._saved = notes.STORE
        notes.STORE = Path(self._tmp.name) / "memory_notes.json"

    def tearDown(self):
        notes.STORE = self._saved
        self._tmp.cleanup()

    LONG = "The TP53 accession is P04637 (reviewed, Swiss-Prot), taken from the UniProt record. " * 3

    def test_lasting_facts_become_proposals_not_active_notes(self):
        reply = '[{"text": "Report gene accessions as UniProt Swiss-Prot entries", "category": "Preference"}]'
        added = notes.learn("Give me the UniProt accession for TP53", self.LONG, "proj1", lambda s, u: reply)
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0]["status"], notes.PROPOSED)
        self.assertEqual(added[0]["source"], "auto")
        self.assertEqual(notes.recall("anything", "proj1"), "")  # not used until approved

    def test_a_fact_already_remembered_is_not_suggested_again(self):
        notes.add("Report gene accessions as UniProt Swiss-Prot entries")  # all projects
        reply = '[{"text": "report gene accessions as UniProt Swiss-Prot entries", "category": "Preference"}]'
        self.assertEqual(notes.learn("q", self.LONG, "proj1", lambda s, u: reply), [])

    def test_short_answers_and_unreadable_replies_give_nothing(self):
        called = []
        self.assertEqual(notes.learn("q", "short", None, lambda s, u: called.append(1) or "[]"), [])
        self.assertEqual(called, [])  # no model call for a short answer
        self.assertEqual(notes.learn("q", self.LONG, None, lambda s, u: "not json at all"), [])

    def test_at_most_three_suggestions_and_junk_is_skipped(self):
        reply = ('[{"text": "Fact number one here"}, {"text": "x"}, "Fact number two here", {"text": "Fact number three here"},'
                 ' {"text": "Fact number four here"}]')
        added = notes.learn("q", self.LONG, None, lambda s, u: reply)
        self.assertEqual(len(added), 3)
        self.assertNotIn("x", [i["text"] for i in notes.list_items()])


if __name__ == "__main__":
    unittest.main()

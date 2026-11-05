import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import audit, workdir
from biomni_ui import native_agent as na


class Folder(unittest.TestCase):
    def test_each_conversation_gets_its_own_folder_under_the_workspace_results(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            with mock.patch("biomni.config.default_config", mock.Mock(path=d)):
                a, b = workdir.conversation_dir("c1"), workdir.conversation_dir("c2")
                self.assertNotEqual(a, b)
                self.assertTrue(a.is_dir() and a.parent == Path(d).resolve() / "results")
                self.assertEqual(workdir.conversation_dir("../x"), Path(d).resolve() / "results" / "___x")  # no way out of the results folder


class Trace(unittest.TestCase):
    def test_steps_notes_references_and_events_are_recorded_as_a_notebook_and_two_ledgers(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            d = Path(d)
            workdir.add_step(d, "python", "求和", "print(1+1)", "2")
            workdir.add_step(d, "bash", "列目录", "ls", "")
            workdir.add_note(d, "**计划**\n\n- [ ] a")
            workdir.add_references(d, "王小明", [{"url": "https://a.org/x", "title": "T", "domain": "a.org"}])
            workdir.add_event(d, {"type": "answer", "text": "好"})
            nb = json.loads((d / "execution_trace" / "trace.ipynb").read_text(encoding="utf-8"))
            self.assertEqual(nb["nbformat"], 4)
            self.assertEqual([c["cell_type"] for c in nb["cells"]], ["code", "code", "markdown"])
            self.assertTrue(nb["cells"][1]["source"][0].startswith("%%bash"))
            self.assertEqual("".join(nb["cells"][0]["outputs"][0]["text"]), "2")
            ref = json.loads((d / "execution_trace" / "references.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual((ref["query"], ref["url"]), ("王小明", "https://a.org/x"))
            self.assertEqual(json.loads((d / "execution_trace" / "transcript.jsonl").read_text(encoding="utf-8").splitlines()[0])["text"], "好")

    def test_the_loop_writes_its_steps_to_the_notebook(self):
        steps = iter([[{"type": "function_call", "name": "python", "call_id": "1", "arguments": json.dumps({"title": "加", "code": "print(6*7)"})}],
                      [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "完成。"}]}]])
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=lambda e: None, cancel=lambda: False, cwd=Path(d),
                   call=lambda *a, **k: (next(steps), {"seconds": 0, "usage": {}}))
            nb = json.loads((Path(d) / "execution_trace" / "trace.ipynb").read_text(encoding="utf-8"))
            self.assertIn("42", "".join(nb["cells"][0]["outputs"][0]["text"]))


class NoToolsNote(unittest.TestCase):
    def test_only_answers_that_cite_something_checkable_are_flagged(self):
        self.assertFalse(audit.has_identifiers("PCR 的退火温度一般比引物的 Tm 低 3–5 °C。"))
        self.assertTrue(audit.has_identifiers("见 PMID: 12345678。"))
        self.assertTrue(audit.has_identifiers("详见 https://a.org/x"))


class Prompt(unittest.TestCase):
    def test_the_prompt_is_a_triage_workflow_not_a_search_first_rule(self):
        text = na.system_prompt("curl", "")
        self.assertIn("Do it directly, with no web search", text)
        self.assertIn("Ambiguous reference", text)
        self.assertNotIn("第一步先用它", text)


if __name__ == "__main__":
    unittest.main()

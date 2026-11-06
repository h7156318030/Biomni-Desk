import json
import tempfile
from pathlib import Path
import unittest
from unittest import mock

from biomni_ui import biomni_tools as bt
from biomni_ui import native_agent as na


class Catalog(unittest.TestCase):
    def test_stock_and_added_tools_are_both_in_the_catalog(self):
        names = {t["name"] for t in bt.catalog()}
        self.assertGreater(len(names), 200)
        self.assertIn("query_uniprot", names)  # stock
        self.assertIn("author_papers", names)  # ours

    def test_keywords_find_the_matching_tool_with_its_parameters(self):
        out = bt.find_tools("clinical trials gene therapy", 4)
        self.assertIn("clinical_trials", out)
        self.assertIn("Required parameters", out)
        self.assertIn("run_tool", out)

    def test_a_query_without_english_words_still_offers_the_quick_tools(self):
        out = bt.find_tools("王小明 论文")
        self.assertIn("English keywords", out)
        self.assertIn("author_papers", out)


class Running(unittest.TestCase):
    def test_unknown_names_and_wrong_arguments_come_back_as_readable_text(self):
        self.assertIn("No tool named", bt.run_tool("no_such_tool", {}))
        out = bt.run_tool("pubmed_search", {"wrong": 1})
        self.assertIn("failed", out)
        self.assertIn("query", out)  # the required parameter is named

    def test_a_tool_is_called_with_its_arguments_and_its_output_is_returned(self):
        class Fake:
            @staticmethod
            def pubmed_search(query, max_results=10):
                print("printed line")
                return f"result for {query} ({max_results})"

        with mock.patch.object(bt.importlib, "import_module", return_value=Fake):
            out = bt.run_tool("pubmed_search", {"query": "BRCA1", "max_results": 2})
        self.assertIn("printed line", out)
        self.assertIn("result for BRCA1 (2)", out)

    def test_a_tool_that_does_not_return_is_given_up_on(self):
        import time

        class Slow:
            @staticmethod
            def pubmed_search(query):
                time.sleep(3)

        with mock.patch.object(bt.importlib, "import_module", return_value=Slow):
            out = bt.run_tool("pubmed_search", {"query": "x"}, timeout=1)
        self.assertIn("did not return", out)


class LoopTools(unittest.TestCase):
    def test_the_loop_has_search_shell_and_the_function_finder_by_default(self):
        names = [t.get("type") if t.get("type") == "web_search" else t.get("name") for t in na.active_tools()]
        self.assertEqual(sorted(names, key=str), sorted(["web_search", "bash", "python", "todo", "find_tools", "run_tool", "use_skill", "find_skills", "ask_user", "delegate_task", "propose_memory"], key=str))  # the Biomni functions are found and called, not guessed
        self.assertIn("biomni.tool", na.system_prompt("curl", ""))

    def test_the_biomni_style_tells_the_model_to_find_functions_first(self):
        text = na.system_prompt("biomni", "")
        self.assertIn("find_tools", text)
        self.assertIn("curl", text)  # curl is the fallback, not the first move

    def test_an_import_of_find_tools_from_a_module_gets_the_hint_that_it_is_preloaded(self):
        from unittest import mock as _m

        events = []
        steps = iter([[{"type": "function_call", "name": "python", "call_id": "1", "arguments": json.dumps({"title": "t", "code": "from biomni_ui.lit import find_tools"})}],
                      [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "好。"}]}]])
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d, _m.patch.object(na.pykernel if hasattr(na, "pykernel") else __import__("biomni_ui.pykernel", fromlist=["x"]).POOL, "close", lambda *a: None),                 _m.patch("biomni_ui.pykernel.run", lambda *a, **k: "Traceback ... ImportError: cannot import name 'find_tools' from 'biomni_ui.lit'"):
            na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d),
                   call=lambda *a, **k: (next(steps), {"seconds": 0, "usage": {}}))
        obs = [e["text"] for e in events if e["type"] == "observation"]
        self.assertIn("no import", obs[0])

    def test_every_model_call_event_says_how_many_calls_the_response_made(self):
        events = []
        steps = iter([[{"type": "function_call", "name": "bash", "call_id": "1", "arguments": json.dumps({"command": "echo a"})},
                       {"type": "function_call", "name": "bash", "call_id": "2", "arguments": json.dumps({"command": "echo b"})}],
                      [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "好。"}]}]])
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d),
                   call=lambda *a, **k: (next(steps), {"seconds": 0, "usage": {}}))
        llm = [e for e in events if e["type"] == "llm"]
        self.assertEqual([e["calls"] for e in llm], [2, 0])

    def test_the_picking_tools_come_back_only_when_asked_for(self):
        with mock.patch.dict("os.environ", {"BIOMNI_UI_EXTRA_TOOLS": "1"}):
            names = {t.get("name") for t in na.active_tools()}
        self.assertTrue({"find_tools", "run_tool", "use_skill", "search_literature"} <= names)


if __name__ == "__main__":
    unittest.main()

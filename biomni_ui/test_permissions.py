import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import connectors, native_agent, permissions


class Isolated(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self._patches = [
            mock.patch.object(permissions, "ANSWERS", root / "answers"),
            mock.patch.object(permissions, "GRANTS", root / "grants.json"),
            mock.patch.object(permissions, "REQUESTS", root / "requests"),
            mock.patch.object(permissions, "DECISIONS", root / "decisions"),
        ]
        for p in self._patches:
            p.start()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()


class StandingGrants(Isolated):
    def test_each_scope_covers_only_its_own_place(self):
        permissions.add("conversation", "uniprot_lookup", "c1", "p1")
        self.assertTrue(permissions.allowed("uniprot_lookup", "c1", "p1"))
        self.assertFalse(permissions.allowed("uniprot_lookup", "c2", "p1"))  # another conversation
        permissions.add("project", "geo_search", None, "p1")
        self.assertTrue(permissions.allowed("geo_search", "c9", "p1"))
        self.assertFalse(permissions.allowed("geo_search", "c9", "p2"))  # another project
        permissions.add("global", "pubmed_search", None, None)
        self.assertTrue(permissions.allowed("pubmed_search", "any", "any"))

    def test_quick_tasks_are_the_project_quick(self):
        permissions.add("project", "reactome_pathways", None, None)  # from the quick-task area
        self.assertTrue(permissions.allowed("reactome_pathways", "c1", None))

    def test_revoke_and_listing(self):
        permissions.add("global", "uniprot_lookup", None, None)
        self.assertEqual(permissions.listing(), [{"scope": "global", "key": "", "tool": "uniprot_lookup"}])
        self.assertTrue(permissions.remove("global", "uniprot_lookup"))
        self.assertFalse(permissions.remove("global", "uniprot_lookup"))
        self.assertFalse(permissions.allowed("uniprot_lookup", "c1", None))

    def test_a_conversation_grant_needs_a_conversation(self):
        with self.assertRaises(ValueError):
            permissions.add("conversation", "uniprot_lookup", None, "p1")


class Deciding(Isolated):
    def run_decide(self, interactive=True, cancel=lambda: False, timeout=5, conversation="c1", project="p1"):
        events = []
        result = permissions.decide("uniprot_lookup", "UniProt proteins", conversation, project, interactive=interactive,
                                    emit=events.append, cancel=cancel, timeout=timeout)
        return result, events

    def answer_soon(self, choice):
        def run():
            time.sleep(0.3)
            request_id = self.request_ids.pop(0)
            permissions.answer(request_id, choice)

        self.request_ids = []
        threading.Thread(target=run, daemon=True).start()

    def test_a_standing_grant_allows_without_asking(self):
        permissions.add("project", "uniprot_lookup", None, "p1")
        result, events = self.run_decide()
        self.assertEqual(result, "allow")
        self.assertEqual(events, [])

    def test_auto_mode_refuses_when_nobody_can_answer(self):
        result, events = self.run_decide(interactive=False)
        self.assertEqual(result, "deny")
        self.assertEqual(events, [])

    def test_once_allows_this_call_only(self):
        self.request_ids = []

        def emit(event):
            if event.get("type") == "permission":
                self.request_ids.append(event["id"])

        threading.Thread(target=lambda: (time.sleep(0.3), permissions.answer(self.request_ids[0], "once")), daemon=True).start()
        result = permissions.decide("uniprot_lookup", "UniProt proteins", "c1", "p1", interactive=True, emit=emit, cancel=lambda: False, timeout=5)
        self.assertEqual(result, "allow")
        self.assertFalse(permissions.allowed("uniprot_lookup", "c1", "p1"))  # nothing stored

    def test_conversation_choice_is_stored_for_that_conversation(self):
        self.request_ids = []

        def emit(event):
            if event.get("type") == "permission":
                self.request_ids.append(event["id"])
                threading.Thread(target=lambda: (time.sleep(0.2), permissions.answer(event["id"], "conversation")), daemon=True).start()

        result = permissions.decide("uniprot_lookup", "UniProt proteins", "c1", "p1", interactive=True, emit=emit, cancel=lambda: False, timeout=5)
        self.assertEqual(result, "allow")
        self.assertTrue(permissions.allowed("uniprot_lookup", "c1", "p1"))
        self.assertFalse(permissions.allowed("uniprot_lookup", "c2", "p1"))

    def test_deny_and_no_answer_both_refuse(self):
        def emit(event):
            if event.get("type") == "permission":
                threading.Thread(target=lambda: (time.sleep(0.2), permissions.answer(event["id"], "deny")), daemon=True).start()

        self.assertEqual(permissions.decide("uniprot_lookup", "x", "c1", "p1", interactive=True, emit=emit, cancel=lambda: False, timeout=5), "deny")
        result, _ = self.run_decide(timeout=0.6)  # nobody answers in time
        self.assertEqual(result, "deny")

    def test_cancelling_the_task_refuses(self):
        result, _ = self.run_decide(cancel=lambda: True)
        self.assertEqual(result, "deny")

    def test_answers_are_validated(self):
        self.assertFalse(permissions.answer("../evil", "once"))
        self.assertFalse(permissions.answer("abc123", "always"))
        self.assertTrue(permissions.answer("abc123", "once"))


class KernelPath(Isolated):
    def serve_in_background(self, session, decide):
        stop = threading.Event()
        threading.Thread(target=permissions.serve, args=(session, decide, stop), daemon=True).start()
        self.addCleanup(stop.set)

    def test_a_kernel_call_is_allowed_when_the_task_allows_it(self):
        self.serve_in_background("conv-a", lambda tool: "allow")
        self.assertTrue(permissions.kernel_check("uniprot_lookup", "UniProt proteins", "conv-a", timeout=5))

    def test_a_kernel_call_is_refused_when_the_task_refuses(self):
        self.serve_in_background("conv-b", lambda tool: "deny")
        self.assertFalse(permissions.kernel_check("uniprot_lookup", "UniProt proteins", "conv-b", timeout=5))

    def test_requests_from_other_sessions_are_not_answered_here(self):
        self.serve_in_background("conv-mine", lambda tool: "allow")
        self.assertFalse(permissions.kernel_check("uniprot_lookup", "UniProt proteins", "conv-other", timeout=1))  # nobody answers: refused

    def test_no_answer_means_refused(self):
        self.assertFalse(permissions.kernel_check("uniprot_lookup", "UniProt proteins", "nobody", timeout=0.8))

    def test_the_guard_asks_inside_a_python_session_only(self):
        from biomni_ui import connectors

        guarded = connectors._guarded("uniprot_lookup", lambda: "CALLED")
        with mock.patch.dict("os.environ", {"BIOMNI_KERNEL_SESSION": "conv-g"}):
            self.serve_in_background("conv-g", lambda tool: "deny")
            self.assertIn("not allowed for this task", guarded())
        self.serve_in_background("conv-h", lambda tool: "allow")
        with mock.patch.dict("os.environ", {"BIOMNI_KERNEL_SESSION": "conv-h"}):
            self.assertEqual(guarded(), "CALLED")
        with mock.patch.dict("os.environ", {"BIOMNI_KERNEL_SESSION": ""}):  # a session without an id is refused
            self.assertIn("not allowed for this task", guarded())
        self.assertEqual(guarded(), "CALLED")  # outside any kernel the guard only checks the switch, as before


def tool_call(name, args, call_id):
    return [{"type": "function_call", "call_id": call_id, "name": name, "arguments": json.dumps(args)}], {}


def final(text):
    return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}], {}


class GatedInTheLoop(Isolated):
    def test_a_refused_connector_is_never_queried_and_the_model_is_told(self):
        state = {"n": 0}

        def fake(model, effort, instructions, items, tools, on_text=None):
            state["n"] += 1
            if state["n"] == 1:
                return tool_call("uniprot_lookup", {"query": "TP53"}, "u1")
            return final("Without UniProt I could not check it.")

        calls = []
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(native_agent, "_fetch_one", side_effect=lambda fc: calls.append(fc) or "RESULT"):
                _, items, _ = native_agent._run_loop(sess="perm-test", model="m", effort="low", question="q", history=[], instructions="sys",
                                                     emit=lambda e: None, cancel=lambda: False, cwd=Path(d), call=fake, allow_ask=False,
                                                     permit=lambda tool, cid: "deny")
        outs = [str(i.get("output")) for i in items if i.get("type") == "function_call_output"]
        self.assertTrue(any("not allowed for this task" in o for o in outs))
        self.assertEqual(calls, [])  # the connector was not called

    def test_an_allowed_connector_runs(self):
        state = {"n": 0}

        def fake(model, effort, instructions, items, tools, on_text=None):
            state["n"] += 1
            if state["n"] == 1:
                return tool_call("uniprot_lookup", {"query": "TP53"}, "u1")
            return final("done")

        calls = []
        with tempfile.TemporaryDirectory() as d:
            with mock.patch.object(native_agent, "_fetch_one", side_effect=lambda fc: calls.append(fc) or "RESULT"):
                native_agent._run_loop(sess="perm-test2", model="m", effort="low", question="q", history=[], instructions="sys",
                                       emit=lambda e: None, cancel=lambda: False, cwd=Path(d), call=fake, allow_ask=False,
                                       permit=lambda tool, cid: "allow")
        self.assertEqual(len(calls), 1)

    def test_only_database_calls_are_gated(self):
        self.assertEqual(native_agent._gated_tool({"name": "uniprot_lookup", "arguments": "{}"}), "uniprot_lookup")
        self.assertEqual(native_agent._gated_tool({"name": "run_tool", "arguments": json.dumps({"name": "query_clinvar"})}), None)  # not a connector
        self.assertEqual(native_agent._gated_tool({"name": "run_tool", "arguments": json.dumps({"name": "pubmed_search"})}), "pubmed_search")
        self.assertIsNone(native_agent._gated_tool({"name": "web_search", "arguments": "{}"}))
        self.assertIsNone(native_agent._gated_tool({"name": "bash", "arguments": "{}"}))
        self.assertIsNotNone(connectors.group_of("uniprot_lookup"))


if __name__ == "__main__":
    unittest.main()

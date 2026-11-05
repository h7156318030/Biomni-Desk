import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import native_agent as na


def msg(text):
    return [{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}]


def fcall(name, call_id, **args):
    import json

    return {"type": "function_call", "name": name, "call_id": call_id, "arguments": json.dumps(args, ensure_ascii=False)}


def scripted(*turns):
    it = iter(turns)
    def call(model, effort, instructions, items, tools, on_text=None):
        if instructions == na.JUDGE_SYSTEM:  # the sufficiency judge asks too; these scripts are about the main loop
            return msg("CONTINUE"), {"seconds": 0, "usage": {}}
        return next(it), {"seconds": 0, "usage": {}}

    return call


class ResultFiles(unittest.TestCase):
    def test_a_step_reports_the_files_it_created_or_rewrote(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            d = Path(d)
            (d / "old.png").write_bytes(b"1")
            before = na.snapshot(d)
            (d / "new.pptx").write_bytes(b"2")
            time.sleep(0.02)
            (d / "old.png").write_bytes(b"33")
            (d / "notes.xyz").write_bytes(b"x")  # not a result type
            changed = na.changed_files(before, na.snapshot(d))
        self.assertEqual({Path(p).name for p in changed}, {"new.pptx", "old.png"})

    def test_python_and_bash_steps_carry_their_new_files_in_the_observation(self):
        events = []
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            code = "open('chart.png','wb').write(b'x')"
            call = scripted([fcall("python", "1", title="画图", code=code)], msg("好了。"))
            na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d), call=call)
            obs = next(e for e in events if e["type"] == "observation")
            self.assertEqual([Path(p).name for p in obs["files"]], ["chart.png"])


class Todo(unittest.TestCase):
    def test_the_models_checklist_becomes_the_pages_plan_and_is_not_a_work_step(self):
        self.assertEqual(na.todo_steps([{"content": "查靶点", "status": "completed"}, {"content": "写结论", "status": "in_progress"}, {"content": "  ", "status": "pending"}]),
                         [{"text": "查靶点", "status": "done"}, {"text": "写结论", "status": "todo"}])
        self.assertEqual(na.todo_steps("nope"), [])
        events = []
        call = scripted([fcall("todo", "1", items=[{"content": "a", "status": "pending"}])], msg("直接回答。"))
        answer, _, steps = na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path.cwd(), call=call)
        self.assertEqual(steps, 0)
        self.assertEqual([e for e in events if e["type"] == "plan"][0]["steps"], [{"text": "a", "status": "todo"}])
        self.assertFalse(any(e["type"] in ("code", "observation") for e in events))

    def test_todo_is_a_default_tool(self):
        self.assertIn("todo", {t.get("name") for t in na.active_tools()})


class Narration(unittest.TestCase):
    def test_leading_announcements_leave_the_answer_but_a_result_sentence_stays(self):
        pre, rest = na.split_preambles("我查一下上海当前天气和未来几天的预报。 上海目前晴，约 23°C。今天最高 25°C、最低 12°C。")
        self.assertTrue(pre.startswith("我查一下"))
        self.assertTrue(rest.startswith("上海目前晴"))
        pre, rest = na.split_preambles("我先检索姓名，确认对应的人物。我再核对校方主页上的简介和研究方向。他是上海交大的研究员，研究基因治疗和编辑递送技术。")
        self.assertIn("我再核对", pre)
        self.assertTrue(rest.startswith("他是上海交大"))
        self.assertEqual(na.split_preambles("我查到上海目前晴，约 23°C，今天最高 25°C。"), ("", "我查到上海目前晴，约 23°C，今天最高 25°C。"))


class OpenEndpoint(unittest.TestCase):
    def test_only_this_computer_may_open_files_and_only_result_files(self):
        from fastapi.testclient import TestClient

        from biomni_ui import server

        c = TestClient(server.app)
        self.assertEqual(c.post("/api/open", json={"path": "x.pptx"}).status_code, 403)  # the test client is not 127.0.0.1
        c2 = TestClient(server.app, client=("127.0.0.1", 50000))
        self.assertEqual(c2.post("/api/open", json={"path": "no_such_file_zz.pptx"}).status_code, 404)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            f = Path(d) / "deck.pptx"
            f.write_bytes(b"x")
            with mock.patch.object(server.manager, "roots", [Path(d)]), mock.patch.object(os, "startfile", create=True) as sf:
                self.assertEqual(c2.post("/api/open", json={"path": str(f)}).status_code, 200)
                sf.assert_called_once()
            with mock.patch.object(server.manager, "roots", [Path(d)]), mock.patch.object(server.subprocess, "Popen") as po:
                self.assertEqual(c2.post("/api/open", json={"path": str(f), "action": "folder"}).status_code, 200)
                self.assertIn("/select,", po.call_args[0][0][1])


if __name__ == "__main__":
    unittest.main()


class HistoryAfterRestart(unittest.TestCase):
    def test_a_conversation_keeps_its_context_when_the_process_has_forgotten_it(self):
        from biomni_ui.runner import Manager

        class FakeStore:
            def get_conversation(self, cid):
                return {"tasks": [{"prompt": "查 PCSK9 药物", "events": [{"type": "answer", "text": "有 5 种。"}]}, {"prompt": "它的机制", "events": []}]}

        m = Manager.__new__(Manager)
        m._native = na.Conversations()
        m.store = FakeStore()
        history = m._native_history("c1")
        self.assertEqual([h["role"] for h in history], ["user", "assistant"])  # the question that has no answer yet is not history
        self.assertEqual(history[1]["content"][0]["text"], "有 5 种。")
        m._native.put("c1", [{"type": "message", "role": "user", "content": []}])
        self.assertEqual(len(m._native_history("c1")), 1)  # memory wins when it has something


class SidePanels(unittest.TestCase):
    def test_the_tools_and_knowledge_panels_are_filled_from_what_the_task_used(self):
        events = []
        code = "print('using query_uniprot and author_papers here')"
        call = scripted([fcall("python", "1", title="x", code=code)], [{"type": "function_call", "name": "use_skill", "call_id": "2", "arguments": '{"name": "variant-interpretation"}'}], msg("完成。"))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d), call=call,
                   load_skill=lambda sid: "手册")
        reports = [e for e in events if e["type"] == "tools"]
        self.assertTrue(reports)
        last = reports[-1]
        self.assertTrue({"python", "use_skill", "query_uniprot", "author_papers"} <= set(last["tools"]))
        self.assertTrue(any(k.startswith("query_uniprot: ") for k in last["know_how"]))
        self.assertIn("Skill: variant-interpretation", last["know_how"])
        self.assertEqual((last["libraries"], last["data_lake"]), ([], []))
        self.assertEqual(len({__import__("json").dumps(r, sort_keys=True) for r in reports}), len(reports))  # only reported when something changed

    def test_a_task_that_used_nothing_still_ends_with_a_report(self):
        events = []
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d), call=scripted(msg("你好！")))
        self.assertEqual([e for e in events if e["type"] == "tools"][-1]["tools"], [])


class SidePanelsSources(unittest.TestCase):
    def test_the_databases_and_pages_a_step_reached_are_listed_as_knowledge_consulted(self):
        events = []
        cmd = "curl -s -m 20 'https://api.platform.opentargets.org/api/v4/graphql' && curl https://rest.uniprot.org/uniprotkb/P04637"
        call = scripted([fcall("bash", "1", title="x", command="echo " + cmd)], msg("好。"))
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d), call=call)
        know = [e for e in events if e["type"] == "tools"][-1]["know_how"]
        self.assertIn("Data source / web page: api.platform.opentargets.org", know)
        self.assertIn("Data source / web page: rest.uniprot.org", know)


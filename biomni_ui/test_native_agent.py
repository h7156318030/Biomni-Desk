import sys
import tempfile
import unittest
from pathlib import Path

from biomni_ui import native_agent as na


def fc(_tool, **args):
    import json

    return {"type": "function_call", "name": _tool, "call_id": f"c{len(args)}{_tool}", "arguments": json.dumps(args, ensure_ascii=False)}


def msg(text):
    return {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": text}]}


def scripted(*outputs):
    it = iter(outputs)

    def call(model, effort, instructions, items, tools, on_text=None):
        call.efforts.append(effort)
        call.seen.append(list(items))
        return next(it), {"seconds": 0.1, "usage": {}}

    call.efforts, call.seen = [], []
    return call


class Loop(unittest.TestCase):
    def run_loop(self, call, **kw):
        events = []
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            out = na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d), call=call, **kw)
        return out, events

    def test_a_shell_step_then_an_answer(self):
        call = scripted([msg("先看看。"), fc("bash", title="打印", command="echo hello")], [msg("输出是 hello")])
        (answer, items, steps), events = self.run_loop(call)
        self.assertEqual(answer, "输出是 hello")
        self.assertEqual(steps, 1)
        types = [e["type"] for e in events]
        self.assertEqual(types, ["llm", "reasoning", "code", "observation", "tools", "llm"])  # after each batch of steps the loop reports what it has used
        code = next(e for e in events if e["type"] == "code")
        self.assertTrue(code["code"].startswith("# 打印\n"))
        obs = next(e for e in events if e["type"] == "observation")
        self.assertIn("hello", obs["text"])
        # the tool's output goes back to the model next to its call
        self.assertEqual(call.seen[1][-1]["type"], "function_call_output")

    def test_native_search_cards_count_as_steps(self):
        search = {"type": "web_search_call", "action": {"type": "search", "queries": ["JS001"], "sources": [{"url": "https://www.junshipharma.com/"}]}}
        (answer, _, steps), events = self.run_loop(scripted([search, msg("是特瑞普利单抗")]))
        self.assertEqual(steps, 1)
        self.assertEqual(next(e for e in events if e["type"] == "tool")["results"][0]["domain"], "www.junshipharma.com")

    def test_ask_user_ends_the_turn_with_the_options_and_runs_nothing_else(self):
        ask = fc("ask_user", title="选择对象", question="“示例生物”指哪一家？", options=["上海示例生物", "杭州本导生物"])
        shell = fc("bash", title="x", command="echo should-not-run")
        (answer, items, steps), events = self.run_loop(scripted([msg("有两个候选。"), ask, shell]))
        self.assertIn("示例生物”指哪一家", answer)
        self.assertTrue(answer.startswith("有两个候选。"))
        ev = next(e for e in events if e["type"] == "ask")
        self.assertEqual(ev["options"], ["上海示例生物", "杭州本导生物"])
        self.assertFalse(any(e["type"] == "code" for e in events))  # the shell call in the same turn did not run
        outputs = [i for i in items if i.get("type") == "function_call_output"]
        self.assertEqual(len(outputs), 2)  # every call of the turn gets an output, so the history stays valid

    def test_ask_user_is_offered_by_default(self):
        names = [t.get("name") for t in na.active_tools()]
        self.assertIn("ask_user", names)
        self.assertIn("ask_user", [t.get("name") for t in na.chat_tools_list()])

    def test_the_model_sees_recent_results_in_full_and_old_ones_cut_short(self):
        old_turn = [{"type": "reasoning", "encrypted_content": "x" * 5000},
                    {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "前一个问题"}]}]
        turn = [{"type": "message", "role": "user", "content": [{"type": "input_text", "text": "现在的问题"}]}, {"type": "reasoning", "encrypted_content": "y" * 50}]
        outs = [{"type": "function_call_output", "call_id": str(n), "output": str(n) * 3000} for n in range(9)]
        view = na.shrink_view(old_turn + turn + outs)
        self.assertFalse(any(i.get("type") == "reasoning" and i["encrypted_content"].startswith("x") for i in view))  # an earlier turn's reasoning is not sent again
        self.assertTrue(any(i.get("type") == "reasoning" and i["encrypted_content"].startswith("y") for i in view))  # this turn's reasoning stays
        kept = [i for i in view if i.get("type") == "function_call_output"]
        self.assertEqual(len(kept[-1]["output"]), 3000)  # the latest result is whole
        self.assertLess(len(kept[0]["output"]), 1200)  # the oldest is cut short
        self.assertIn("earlier results omitted", kept[0]["output"])
        self.assertEqual(len(outs[0]["output"]), 3000)  # the stored item itself is untouched

    def test_a_long_result_is_cut_before_it_is_kept_in_the_history(self):
        conv = na.Conversations()
        big = {"type": "function_call_output", "call_id": "1", "output": "z" * 9000}
        conv.put("c", [big, {"type": "message", "role": "user", "content": []}])
        kept = conv.get("c")
        self.assertLess(len(kept[0]["output"]), 1200)

    def test_giving_up_early_is_sent_back_once_at_the_full_effort(self):
        call = scripted([msg("没有查到。")], [fc("bash", title="再试", command="echo https://a.org/1 https://a.org/2")], [msg("找到了 https://a.org/1 和 https://a.org/2")])
        calls = []

        def nudge(answer, steps):
            calls.append((answer, steps))
            return ("请继续", "智能体只试了 0 种办法") if "没有查到" in answer else None

        (answer, _, _), events = self.run_loop(call, nudge=nudge, escalate_to="high")
        self.assertIn("找到了", answer)
        self.assertEqual(call.efforts, ["low", "high", "high"])
        self.assertEqual([e["type"] for e in events].count("notice"), 1)

    def test_unknown_tool_and_empty_answer(self):
        (answer, _, _), _ = self.run_loop(scripted([fc("nope", title="x")], [msg("好")]))
        self.assertEqual(answer, "好")
        (answer, _, _), _ = self.run_loop(scripted([]))
        self.assertEqual(answer, "")

    def test_cancel_stops_before_the_next_call(self):
        events = []
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            out = na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: True, cwd=Path(d), call=scripted())
        self.assertEqual(out[0], "")


class Bash(unittest.TestCase):
    def test_runs_and_reports_exit_codes(self):
        if na.bash_path() is None:
            self.skipTest("no bash")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            self.assertIn("a b", na.run_bash("echo a b", Path(d)))
            self.assertIn("exit code 3", na.run_bash("exit 3", Path(d)))
            self.assertIn(sys.version.split()[0], na.run_bash("python --version", Path(d)))

    def test_timeout_and_blocked_commands(self):
        if na.bash_path() is None:
            self.skipTest("no bash")
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            self.assertIn("stopped", na.run_bash("sleep 5", Path(d), timeout=1))
            self.assertIn("Refused:", na.run_bash("rm -rf /", Path(d)))

    def test_long_output_is_cut_in_the_middle(self):
        text = na.truncate("x" * 20000)
        self.assertLess(len(text), 7000)
        self.assertIn("characters omitted", text)


class Memory(unittest.TestCase):
    def test_a_conversation_keeps_a_bounded_history(self):
        c = na.Conversations()
        c.put("a", [{"type": "message", "role": "user", "content": []} if n % 3 == 0 else {"i": n} for n in range(200)])
        kept = c.get("a")
        self.assertTrue(0 < len(kept) <= na.HISTORY_ITEMS)  # bounded, and it starts at a question (never in the middle of a tool exchange)
        self.assertEqual(kept[0].get("role"), "user")
        self.assertEqual(c.get("b"), [])


class WorkerDrafts(unittest.TestCase):
    def test_a_worker_sends_drafts_already_marked_as_the_answer(self):
        from biomni_ui.runner import Task

        t = Task("q", "c1")
        t.draft_as_answer = True
        self.assertTrue(t.shown_draft("正在写的答案").startswith("<solution>"))
        self.assertEqual(t.shown_draft("<execute>x"), "<execute>x")
        # the worker's task class must route its drafts through the same function
        import inspect

        import biomni_ui.worker as w

        self.assertIn("shown_draft", inspect.getsource(w))


class Preamble(unittest.TestCase):
    def test_the_leading_announcement_is_dropped_but_never_the_whole_answer(self):
        self.assertEqual(na.strip_preamble("我先查询上海今天的实时天气预报，再用中文简要汇报。\n上海今天多云，约 15°C，查询日期 2026-10-29。"), "上海今天多云，约 15°C，查询日期 2026-10-29。")
        self.assertEqual(na.strip_preamble("我会先说结论：A 是对的，理由如下。\n"), "我会先说结论：A 是对的，理由如下。\n")
        self.assertEqual(na.strip_preamble("TP53 位于 17 号染色体。"), "TP53 位于 17 号染色体。")


class PreambleSplit(unittest.TestCase):
    def test_the_announcement_is_split_off_even_without_a_line_break(self):
        pre, rest = na.split_preamble("我先核对“示例生物”对应的公司主体，再查它的业务与公开登记信息，避免同名误认。**“示例生物”指上海示例生物股份有限公司**，是一家专注细胞疗法的公司。")
        self.assertTrue(pre.startswith("我先核对") and pre.endswith("误认。"))
        self.assertTrue(rest.startswith("**“示例生物”指"))
        self.assertEqual(na.split_preamble("TP53 位于 17 号染色体。"), ("", "TP53 位于 17 号染色体。"))
        self.assertEqual(na.split_preamble("我会先说结论：A 是对的。"), ("", "我会先说结论：A 是对的。"))  # nothing left after it

    def test_run_shows_it_as_a_step(self):
        events = []
        call = scripted([msg("我先查一下 JS001 是什么药，再给出来源。**JS001 是特瑞普利单抗**，君实生物研发的 PD-1 抗体。")])
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            answer, _, _ = na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False, cwd=Path(d), call=call)
        self.assertTrue(answer.startswith("**JS001"))
        self.assertTrue(any(e["type"] == "reasoning" and e["text"].startswith("我先查一下") for e in events))


class CleanAnswer(unittest.TestCase):
    def test_pictures_that_point_at_nothing_and_citation_markers_are_removed(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            (Path(d) / "chart.png").write_bytes(b"x")
            text = ("好。![上海天气原图](turn0forecast0)\n![图](chart.png)\n![网](https://a.org/x.png)\n![无](missing.png)\n"
                    "事实。\ue200cite\ue202turn0search0\ue201")
            out = na.clean_answer(text, Path(d))
        self.assertNotIn("turn0forecast0", out)
        self.assertNotIn("missing.png", out)
        self.assertIn(f"![图]({(Path(d) / 'chart.png').resolve().as_posix()})", out)  # a relative name becomes the full path: one name, one file
        self.assertIn("https://a.org/x.png", out)
        self.assertNotIn("\ue200", out)
        self.assertIn("事实。", out)

    def test_the_search_tools_tracking_tail_is_removed_from_links(self):
        out = na.clean_answer("见([a.cn](https://a.cn/x.html?utm_source=openai))和 https://b.cn/y?id=1&utm_source=openai&z=2 与 https://c.cn/?utm_source=openai&k=1")
        self.assertNotIn("utm_source", out)
        self.assertIn("https://a.cn/x.html)", out)
        self.assertIn("https://b.cn/y?id=1&z=2", out)
        self.assertIn("https://c.cn/?k=1", out)

    def test_the_shell_can_write_chinese_in_charts(self):
        if na.bash_path() is None:
            self.skipTest("no bash")
        code = "python -c \"import matplotlib.pyplot as plt; plt.title('上海气温'); plt.savefig('zz_font_check.png'); print('done')\""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            out = na.run_bash(code, Path(d))
        self.assertIn("done", out)
        self.assertNotIn("missing from font", out)


class WiredIn(unittest.TestCase):
    def test_a_model_without_chat_tools_gets_an_error_event(self):
        from types import SimpleNamespace

        from biomni_ui.runner import Manager, Task

        t = Task("x", "c1")
        Manager(lambda: None, None)._drive(SimpleNamespace(llm=SimpleNamespace()), t)  # not a model on a chat-completions endpoint: the native loop cannot run it
        self.assertEqual(t.events[-1]["type"], "error")
        self.assertIn("function calls", t.events[-1]["message"])


class Styles(unittest.TestCase):
    def test_both_styles_fill_the_placeholder(self):
        for style in ("curl", "python"):
            text = na.system_prompt(style)
            self.assertNotIn("{STYLE}", text)
        self.assertIn("curl -s", na.system_prompt("curl"))
        self.assertIn("heredoc", na.system_prompt("python"))


class SkillsInTheLoop(unittest.TestCase):
    def test_use_skill_returns_the_manual_and_the_catalog_is_in_the_prompt(self):
        events = []
        call = scripted([fc("use_skill", name="api-variant-databases")], [msg("好的")])
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            answer, _, steps = na.run(model="m", effort="low", question="q", history=[], instructions="i", emit=events.append, cancel=lambda: False,
                                      cwd=Path(d), load_skill=lambda sid: f"手册:{sid}", call=call)
        self.assertEqual(answer, "好的")
        out = next(e for e in events if e["type"] == "observation")
        self.assertEqual(out["text"], "手册:api-variant-databases")
        text = na.system_prompt("curl", "- a：说明")
        self.assertIn("Skill catalogue", text)
        self.assertIn("- a：说明", text)

    def test_the_real_store_gives_a_catalog_with_the_new_recipes(self):
        from types import SimpleNamespace

        from biomni_ui import skills
        from biomni_ui.runner import Manager

        import tempfile as tf

        with tf.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            store = skills.SkillStore(Path(d) / "mine", Path(d) / "state.json")
            m = Manager(lambda: None, None)
            m.skill_store = store
            catalog, load = m._skill_catalog()
        self.assertIn("api-variant-databases", catalog)
        self.assertIn("17-43057062-T-TG", load("api-variant-databases"))
        self.assertEqual(load("no-such-skill"), "")


class LaneOrder(unittest.TestCase):
    def test_the_tuned_lanes_see_a_question_before_the_general_loop(self):
        from types import SimpleNamespace

        from biomni_ui.runner import Manager, Task

        m = Manager(lambda: None, None)
        seen = []
        for name in ("_clinical_lane", "_research_lane", "_native_lane"):
            setattr(m, name, (lambda n: lambda agent, task: seen.append(n) or n == "_native_lane")(name))
        task = Task("查王小明论文", "c1")
        m._drive(SimpleNamespace(), task)
        self.assertEqual(seen, ["_native_lane"])  # one path: every question goes to the general loop


class DraftAsAnswer(unittest.TestCase):
    def test_plain_prose_drafts_are_shown_as_the_answer_only_when_asked(self):
        from biomni_ui.runner import Task

        t = Task("q", "c1")
        t.emit_draft("先查一下。")
        self.assertEqual(t.draft, "先查一下。")
        t.draft_as_answer = True
        long = "这是一段正在撰写的答案，" * 12
        t.emit_draft(long)
        self.assertTrue(t.draft.startswith("<solution>"))
        t.emit_draft('{"kind": "company", "aliases": []}' + " " * 90)
        self.assertFalse(t.draft.startswith("<solution>"))  # JSON of a helper call is not the answer
        t.emit_draft("<execute>" + long)
        self.assertFalse(t.draft.startswith("<solution>"))


class DraftWindow(unittest.TestCase):
    def test_a_long_answer_keeps_its_marker_in_the_stream(self):
        import threading

        from biomni_ui.runner import Task

        t = Task("q", "c1")
        t.draft_as_answer = True
        gen = t.stream()
        threading.Timer(0.2, lambda: t.emit_draft("答案" * 4000)).start()  # 8000 characters, written while someone watches
        first = next(gen)
        self.assertEqual(first["type"], "draft")
        self.assertTrue(first["text"].startswith("<solution>"))
        t.emit({"type": "done"})


class SandboxLinks(unittest.TestCase):
    def test_a_sandbox_link_becomes_the_file_path_and_a_deck_is_listed_as_a_result(self):
        from biomni_ui.events import extract_files

        out = na.clean_answer("[下载](sandbox:/C:/work/biomni-lite/药物_2026.pptx)")
        self.assertEqual(out, "[下载](C:/work/biomni-lite/药物_2026.pptx)")
        self.assertEqual(extract_files(r"Saved: C:\work\biomni-lite\药物_2026.pptx | size: 3"), [r"C:\work\biomni-lite\药物_2026.pptx"])


if __name__ == "__main__":
    unittest.main()

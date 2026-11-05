"""Every built-in skill must be well-formed, and the code it tells the agent to run must be able to run.

A skill that names a function with a wrong argument would send the agent into a failed step on every use, so each fenced
Python block is parsed and every call to one of our own helpers is checked against the real signature.
"""

import ast
import importlib
import inspect
import re
import unittest

from biomni_ui import skills

HELPER_MODULES = ["biomni_ui.analysis", "biomni_ui.dbtools", "biomni_ui.lit", "biomni_ui.web", "biomni_ui.report"]
REQUIRED = ("title", "description", "category", "when_to_use", "avoid", "uses")


def all_skills():
    for path in sorted(skills.BUILTIN_DIR.glob("*.md")):
        meta, body = skills.parse(path.read_text(encoding="utf-8"))
        yield path.stem, meta, body


class Form(unittest.TestCase):
    def test_front_matter_and_size(self):
        found = 0
        for sid, meta, body in all_skills():
            found += 1
            self.assertRegex(sid, skills.ID_RE, sid)
            for k in REQUIRED:
                self.assertTrue(meta.get(k), f"{sid}: missing {k}")
            self.assertLess(len(body), 6000, f"{sid}: too long for a prompt")
            self.assertIn("## ", body, sid)
        self.assertGreaterEqual(found, 20)

    def test_every_skill_says_what_it_does_not_do(self):
        for sid, meta, body in all_skills():
            self.assertGreater(len(meta["avoid"]), 15, sid)


class Code(unittest.TestCase):
    def modules(self):
        return {name: importlib.import_module(name) for name in HELPER_MODULES}

    def test_code_blocks_parse_and_helper_calls_match_signatures(self):
        mods = self.modules()
        checked = 0
        for sid, _meta, body in all_skills():
            for block in re.findall(r"```python\n(.*?)```", body, flags=re.S):
                tree = ast.parse(block)  # SyntaxError fails the test with the skill's name in the traceback
                imported: dict[str, object] = {}
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom) and node.module in mods:
                        for a in node.names:
                            self.assertTrue(hasattr(mods[node.module], a.name), f"{sid}: {node.module} has no {a.name}")
                            imported[a.asname or a.name] = getattr(mods[node.module], a.name)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in imported and callable(imported[node.func.id]):
                        sig = inspect.signature(imported[node.func.id])
                        try:
                            sig.bind(*[None] * len(node.args), **{k.arg: None for k in node.keywords if k.arg})
                        except TypeError as e:
                            self.fail(f"{sid}: {node.func.id}(...) does not match its signature: {e}")
                        checked += 1
        self.assertGreater(checked, 25)

    def test_uses_field_names_real_functions(self):
        mods = self.modules()
        for sid, meta, _body in all_skills():
            for item in [u.strip() for u in meta["uses"].split(",") if u.strip()]:
                if "." in item and item.rsplit(".", 1)[0] in mods:
                    mod, fn = item.rsplit(".", 1)
                    self.assertTrue(hasattr(mods[mod], fn), f"{sid}: uses {item}")


if __name__ == "__main__":
    unittest.main()

import importlib
import unittest
from types import SimpleNamespace

from biomni.tool.tool_registry import ToolRegistry
from biomni_ui import fast_tools, lit


def fake_agent():
    base = {"biomni.tool.literature": [{"name": "query_pubmed", "description": "d", "required_parameters": [], "optional_parameters": []}]}
    agent = SimpleNamespace(module2api={k: [dict(t) for t in v] for k, v in base.items()}, configured=0)
    agent.tool_registry = ToolRegistry(agent.module2api)
    agent.configure = lambda: setattr(agent, "configured", agent.configured + 1)
    return agent


class Register(unittest.TestCase):
    def test_every_schema_points_at_a_real_function(self):
        for s in fast_tools.SCHEMAS:
            self.assertTrue(callable(getattr(importlib.import_module(s.get("module", fast_tools.MODULE)), s["name"])), s["name"])
            self.assertIn("required_parameters", s)
            self.assertIn("optional_parameters", s)

    def test_parameters_match_the_function_signatures(self):
        import inspect

        for s in fast_tools.SCHEMAS:
            sig = inspect.signature(getattr(importlib.import_module(s.get("module", fast_tools.MODULE)), s["name"]))
            declared = [p["name"] for p in s["required_parameters"] + s["optional_parameters"]]
            self.assertEqual(declared, list(sig.parameters), s["name"])

    def test_register_adds_tools_once_and_rebuilds_the_prompt(self):
        agent = fake_agent()
        before = len(agent.tool_registry.tools)
        names = fast_tools.register(agent)
        self.assertEqual(len(agent.tool_registry.tools), before + len(names))
        self.assertEqual(sum(len(v) for k, v in agent.module2api.items() if k.startswith("biomni_ui.")), len(names))
        self.assertIn("author_papers", agent._custom_tools)
        self.assertIs(agent._custom_functions["author_papers"], lit.author_papers)
        self.assertEqual(len(agent.tool_registry.document_df), before + len(names))
        fast_tools.register(agent)  # a second call must not duplicate anything
        self.assertEqual(len(agent.tool_registry.tools), before + len(names))
        self.assertEqual(sum(len(v) for k, v in agent.module2api.items() if k.startswith("biomni_ui.")), len(names))


if __name__ == "__main__":
    unittest.main()

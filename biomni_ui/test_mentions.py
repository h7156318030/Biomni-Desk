import tempfile
import unittest
from pathlib import Path

from biomni_ui import mentions
from biomni_ui.skills import SkillStore

TOOLS = [
    {"name": "query_pubmed", "description": "Search PubMed literature"},
    {"name": "query_uniprot", "description": "UniProt protein records"},
]
LAKE = {"gwas_catalog.pkl": "GWAS hits", "depmap.csv": "Cancer dependency map"}


class MentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "ws"
        self.root.mkdir()
        (self.root / "results.csv").write_text("a,b")
        (self.root / "plot.png").write_bytes(b"x")
        (self.root / "script.exe").write_bytes(b"x")
        (self.root / ".venv").mkdir()
        (self.root / ".venv" / "hidden.csv").write_text("x")
        self.skills = SkillStore(Path(self.tmp.name) / "mine", Path(self.tmp.name) / "s.json")

    def search(self, q):
        return mentions.search(q, skills=self.skills, tools=TOOLS, data_lake=LAKE, roots=[self.root])

    def test_search_all_kinds(self):
        kinds = {m["kind"] for m in self.search("")}
        self.assertEqual(kinds, {"skill", "tool", "data", "file"})

    def test_search_filters_and_orders(self):
        res = self.search("pubmed")
        kinds = [m["kind"] for m in res]
        self.assertIn("query_pubmed", [m["id"] for m in res])
        self.assertNotIn("query_uniprot", [m["id"] for m in res])  # filtered out
        self.assertLess(kinds.index("skill"), kinds.index("tool"))  # skills are listed before tools

    def test_files_are_limited_to_allowed_types_and_skip_hidden_dirs(self):
        names = [m["label"] for m in self.search("") if m["kind"] == "file"]
        self.assertIn("results.csv", names)
        self.assertNotIn("script.exe", names)
        self.assertNotIn("hidden.csv", names)

    def test_disabled_skill_is_not_offered(self):
        self.skills.set_enabled("literature-review", False)
        ids = [m["id"] for m in self.search("") if m["kind"] == "skill"]
        self.assertNotIn("literature-review", ids)

    def test_to_prompt(self):
        picked = [
            {"kind": "skill", "id": "literature-review"},
            {"kind": "tool", "id": "query_pubmed"},
            {"kind": "data", "id": "depmap.csv"},
            {"kind": "file", "id": str((self.root / "results.csv").resolve())},
        ]
        txt = mentions.to_prompt(picked, skills=self.skills, tool_names={"query_pubmed"},
                                 data_names=set(LAKE), roots=[self.root])
        self.assertIn("Literature search and key-point summary", txt)
        self.assertIn("`query_pubmed`", txt)
        self.assertIn("`depmap.csv`", txt)
        self.assertIn("results.csv", txt)

    def test_to_prompt_ignores_unknown_and_unsafe(self):
        outside = Path(self.tmp.name) / "secret.csv"
        outside.write_text("x")
        picked = [
            {"kind": "tool", "id": "rm_rf"},
            {"kind": "data", "id": "nothing"},
            {"kind": "skill", "id": "../../x"},
            {"kind": "file", "id": str(outside)},
            {"kind": "bogus", "id": "x"},
        ]
        txt = mentions.to_prompt(picked, skills=self.skills, tool_names={"query_pubmed"},
                                 data_names=set(LAKE), roots=[self.root])
        self.assertEqual(txt, "")


if __name__ == "__main__":
    unittest.main()

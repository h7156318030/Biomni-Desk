import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import relevant


CATALOG = [
    {"name": "query_gnomad", "import": "biomni.tool.database", "description": "Query gnomAD population frequency and constraint for a gene.",
     "required": "[('gene', 'str')]", "status": "available"},
    {"name": "old_gnomad_tool", "import": "biomni.tool.database", "description": "gnomAD gene constraint (old).", "required": "[('gene', 'str')]", "status": "restricted"},
    {"name": "analyze_protein_conservation", "import": "biomni.tool.genomics", "description": "Conservation of a protein sequence across species.",
     "required": "[('sequence', 'str'), ('species', 'list')]", "status": "conditional"},
    {"name": "unrelated_helper", "import": "biomni.tool.physiology", "description": "Heart rate variability from ECG traces.",
     "required": "[('ecg', 'list')]", "status": "available"},
]
SKILLS = [
    {"id": "variant-pathogenicity", "title": "变异致病性速查", "when_to_use": "ClinVar 临床意义和 gnomAD 人群频率", "enabled": True},
    {"id": "off-skill", "title": "gnomAD 其他", "when_to_use": "gnomAD", "enabled": False},
]


class Functions(unittest.TestCase):
    def test_a_usable_function_that_shares_the_question_words_is_offered_with_its_import(self):
        names = [f["name"] for f in relevant.functions_for("查 TP53 基因的 gnomAD 人群约束", CATALOG)]
        self.assertIn("query_gnomad", names)
        self.assertNotIn("old_gnomad_tool", names)  # a restricted function is not offered

    def test_one_shared_word_in_a_description_is_not_enough(self):
        self.assertNotIn("unrelated_helper", [f["name"] for f in relevant.functions_for("ECG 的 protein 功能", CATALOG)])

    def test_a_question_with_no_matching_words_gives_nothing(self):
        self.assertEqual(relevant.functions_for("你好", CATALOG), [])


class Block(unittest.TestCase):
    def test_the_block_lists_the_import_line_and_the_required_parameters(self):
        text = relevant.block("查 TP53 基因的 gnomAD 人群约束", CATALOG, SKILLS)
        self.assertIn("from biomni.tool.database import query_gnomad", text)
        self.assertIn("required parameters: gene", text)
        self.assertIn("variant-pathogenicity", text)
        self.assertNotIn("off-skill", text)  # a disabled skill is not offered

    def test_nothing_is_added_when_nothing_matches(self):
        self.assertEqual(relevant.block("你好", CATALOG, SKILLS), "")

    def test_the_switch_file_turns_it_off_without_a_restart(self):
        with tempfile.TemporaryDirectory() as d:
            switch = Path(d) / "relevant_switch.txt"
            switch.write_text("0", encoding="utf-8")
            with mock.patch.object(relevant, "SWITCH", switch), mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("BIOMNI_UI_RELEVANT", None)
                self.assertFalse(relevant.enabled())
                switch.write_text("1", encoding="utf-8")
                self.assertTrue(relevant.enabled())


RNA_ONLY = {"name": "analyze_rna_secondary_structure_features", "import": "biomni.tool.biochemistry",
            "description": "Calculate numeric values for structural features of an RNA secondary structure.", "required": "[('dot_bracket_structure', 'str')]",
            "status": "available"}
TRACTABILITY = {"name": "target_tractability", "import": "biomni_ui.dbtools",
                "description": "Open Targets tractability flags for a human gene (small molecule, antibody).", "required": "[('gene', 'str')]", "status": "available"}


class TwoSharedWords(unittest.TestCase):
    def test_one_shared_word_in_a_name_is_not_enough(self):
        names = [f["name"] for f in relevant.functions_for("单细胞 RNA 数据的细胞类型注释", CATALOG + [RNA_ONLY])]
        self.assertNotIn("analyze_rna_secondary_structure_features", names)

    def test_two_shared_words_are_offered(self):
        names = [f["name"] for f in relevant.functions_for("评估靶点的成药性", CATALOG + [TRACTABILITY])]
        self.assertIn("target_tractability", names)

    def test_a_word_shared_by_most_functions_does_not_count(self):
        many = [{"name": f"helper_{i}", "import": "biomni.tool.x", "description": "gene expression helper", "required": "", "status": "available"}
                for i in range(12)]
        self.assertEqual(relevant.functions_for("gene expression", many), [])


if __name__ == "__main__":
    unittest.main()

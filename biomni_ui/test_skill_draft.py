import unittest
from types import SimpleNamespace

from biomni_ui import assist

GOOD = """Here is the draft:
```json
{"title": "Look up a gene's UniProt accession", "description": "Finds the reviewed UniProt entry for a human gene.",
 "category": "protein", "when_to_use": "A gene name is given and a UniProt ID is needed.", "avoid": "Non-human genes.",
 "body": "1. Call uniprot_lookup with the gene symbol.\\n2. Check the gene name matches."}
```"""


class Parse(unittest.TestCase):
    def test_a_fenced_reply_gives_a_clean_draft(self):
        d = assist.parse_skill(GOOD)
        self.assertEqual(d["title"], "look-up-a-gene-s-uniprot-accession"[:48])
        self.assertIn("uniprot_lookup", d["body"])
        self.assertEqual(set(d), set(assist.SKILL_KEYS))

    def test_a_reply_without_steps_is_refused(self):
        with self.assertRaises(ValueError):
            assist.parse_skill('{"title": "x", "description": "y", "body": ""}')

    def test_a_reply_without_json_is_refused(self):
        with self.assertRaises(ValueError):
            assist.parse_skill("Sorry, I cannot do that.")

    def test_the_title_is_made_a_safe_id(self):
        d = assist.parse_skill('{"title": "RNA-seq: QC & counts!", "description": "d", "body": "1. step"}')
        self.assertEqual(d["title"], "rna-seq-qc-counts")


class Draft(unittest.TestCase):
    def test_the_draft_is_built_from_the_task_its_code_and_its_answer(self):
        seen = {}

        class Fake:
            def invoke(self, messages):
                seen["user"] = messages[1].content
                return SimpleNamespace(content=GOOD)

        d = assist.draft_skill(Fake(), "Look up the UniProt accession of TP53", ["print(lookup('TP53'))"], "P04637")
        self.assertIn("TP53", seen["user"])
        self.assertIn("print(lookup('TP53'))", seen["user"])
        self.assertIn("P04637", seen["user"])
        self.assertTrue(d["body"])


if __name__ == "__main__":
    unittest.main()

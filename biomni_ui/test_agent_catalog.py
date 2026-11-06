import os
import tempfile
import unittest
from pathlib import Path

from biomni_ui import agent_catalog


class FakeAgent:
    def __init__(self, path, datasets):
        self.path = path
        self.data_lake_dict = datasets

    def _generate_system_prompt(self, tool_desc, data_lake_content, library_content_list, **kwargs):
        return "OFFICIAL PROMPT"


class CatalogBlock(unittest.TestCase):
    def test_every_dataset_is_listed_and_the_local_ones_are_marked(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "gwas_catalog.pkl").write_bytes(b"x")
            text = agent_catalog.catalog_block({"gwas_catalog.pkl": "GWAS associations.", "BindingDB_All_202409.tsv": "Binding data."}, d)
        self.assertIn("- gwas_catalog.pkl [available locally]", text)
        self.assertIn("- BindingDB_All_202409.tsv [download needed]", text)
        self.assertIn("download_data_lake_file('<filename>'", text)
        self.assertIn(agent_catalog.ZENODO_URL, text)

    def test_the_real_catalogue_has_all_the_datasets(self):
        from biomni.env_desc import data_lake_dict

        with tempfile.TemporaryDirectory() as d:
            text = agent_catalog.catalog_block(data_lake_dict, d)
        import re

        dataset_lines = [line for line in text.splitlines() if line.startswith("- ")]
        self.assertEqual(len(dataset_lines), len(data_lake_dict))
        self.assertTrue(all(re.search(r" \[(available locally|download needed)\]$", line) for line in dataset_lines))  # every line ends with its status


class Attach(unittest.TestCase):
    def test_the_official_prompt_is_kept_and_the_catalogue_follows_it(self):
        with tempfile.TemporaryDirectory() as d:
            agent = FakeAgent(d, {"a.pkl": "A data set."})
            agent_catalog.attach(agent)
            prompt = agent._generate_system_prompt("tools", [], [])
        self.assertTrue(prompt.startswith("OFFICIAL PROMPT"))
        self.assertIn("## Dataset catalogue (Biomni-Desk)", prompt)
        self.assertIn("- a.pkl [download needed]", prompt)

    def test_attaching_twice_does_not_add_the_catalogue_twice(self):
        with tempfile.TemporaryDirectory() as d:
            agent = FakeAgent(d, {"a.pkl": "A data set."})
            agent_catalog.attach(agent)
            agent_catalog.attach(agent)
            prompt = agent._generate_system_prompt("tools", [], [])
        self.assertEqual(prompt.count("## Dataset catalogue"), 1)

    def test_a_dataset_added_later_appears_in_the_next_prompt(self):
        with tempfile.TemporaryDirectory() as d:
            agent = FakeAgent(d, {})
            agent_catalog.attach(agent)
            self.assertEqual(agent._generate_system_prompt("t", [], []), "OFFICIAL PROMPT")  # nothing to list: the prompt is unchanged
            agent.data_lake_dict["new.tsv"] = "Added by the user."
            self.assertIn("- new.tsv [download needed]", agent._generate_system_prompt("t", [], []))


class DatasetInfo(unittest.TestCase):
    def test_dataset_info_gives_the_description_and_the_state_and_flags_unknown_names(self):
        with tempfile.TemporaryDirectory() as d:
            agent = FakeAgent(d, {"a.pkl": "A data set.", "b.tsv": "Another one."})
            (Path(d) / "data_lake").mkdir()
            (Path(d) / "data_lake" / "a.pkl").write_bytes(b"x")
            agent_catalog.attach(agent)
            info = agent._custom_functions["dataset_info"]
            self.assertEqual(info("a.pkl"), "a.pkl: A data set. [available locally]")
            self.assertEqual(info("b.tsv"), "b.tsv: Another one. [download needed]")
            self.assertIn("Not in the catalogue", info("zzz"))
            from biomni_ui import agent_catalog as ac  # noqa: F401
            import builtins
            self.assertIs(builtins._biomni_custom_functions["dataset_info"], info)


class RealAgent(unittest.TestCase):
    def test_the_official_agent_gets_the_catalogue_in_its_system_prompt(self):
        from biomni.agent import A1

        with tempfile.TemporaryDirectory() as d:
            agent = A1(path=d, expected_data_lake_files=[])
            agent_catalog.attach(agent)
            agent.configure()
            self.assertIn("## Dataset catalogue (Biomni-Desk)", agent.system_prompt)
            self.assertIn("- gwas_catalog.pkl [", agent.system_prompt)  # a name from the real catalogue, with its state
            self.assertFalse(os.path.exists(os.path.join(agent.path, "data_lake", "gwas_catalog.pkl")))  # and nothing was downloaded


if __name__ == "__main__":
    unittest.main()

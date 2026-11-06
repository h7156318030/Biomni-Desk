import unittest
from unittest import mock

from biomni_ui import connectors, dbtools, fast_tools, native_agent

NEW = ("ensembl_gene", "pdb_structures", "alphafold_structure", "pubchem_compound", "openalex_works")


class Registry(unittest.TestCase):
    def test_every_new_database_tool_is_defined_listed_offered_and_switchable(self):
        for name in NEW:
            with self.subTest(tool=name):
                self.assertTrue(callable(getattr(dbtools, name)))
                self.assertIn(name, fast_tools.DB_TOOLS)
                self.assertIn(name, native_agent.DIRECT_NAMES)
                self.assertIsNotNone(connectors.group_of(name))

    def test_schemas_are_generated_for_the_new_tools(self):
        names = {s["name"] for s in fast_tools._db_schemas()}
        self.assertTrue(set(NEW) <= names)

    def test_species_keeps_its_meaning_for_the_string_tool(self):
        schema = {s["name"]: s for s in fast_tools._db_schemas()}
        species = [p for p in schema["string_interactions"]["optional_parameters"] if p["name"] == "species"]
        self.assertTrue(species and "taxon" in species[0]["description"].lower())


class Parsing(unittest.TestCase):
    def test_ensembl_gene_line(self):
        fake = {"id": "ENSG00000141510", "display_name": "TP53", "biotype": "protein_coding", "seq_region_name": "17", "start": 7661779,
                "end": 7687546, "strand": -1, "canonical_transcript": "ENST00000269305.9", "description": "tumor protein p53"}
        with mock.patch.object(dbtools.lit, "_json", return_value=fake):
            out = dbtools.ensembl_gene("TP53")
        self.assertIn("ENSG00000141510 | TP53 | protein_coding | chr17:7661779-7687546 (-)", out)

    def test_alphafold_line_gives_confidence_and_file(self):
        fake = [{"modelEntityId": "AF-P04637-F1", "globalMetricValue": 75.06, "modelCreatedDate": "2025-08-01T00:00:00Z",
                 "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-P04637-F1-model_v6.pdb"}]
        with mock.patch.object(dbtools.lit, "_json", return_value=fake):
            out = dbtools.alphafold_structure("P04637")
        self.assertIn("AF-P04637-F1 | mean pLDDT 75.06 | created 2025-08-01", out)
        self.assertIn("model_v6.pdb", out)

    def test_pubchem_line(self):
        fake = {"PropertyTable": {"Properties": [{"CID": 2244, "MolecularFormula": "C9H8O4", "MolecularWeight": "180.16",
                                                   "IUPACName": "2-acetyloxybenzoic acid", "ConnectivitySMILES": "CC(=O)OC1=CC=CC=C1C(=O)O"}]}}
        with mock.patch.object(dbtools.lit, "_json", return_value=fake):
            out = dbtools.pubchem_compound("aspirin")
        self.assertTrue(out.startswith("2244 | C9H8O4 | 180.16 | 2-acetyloxybenzoic acid"))

    def test_openalex_lines(self):
        fake = {"results": [{"display_name": "A structural study of p53", "publication_year": 2024, "doi": "https://doi.org/10.1/x",
                             "primary_location": {"source": {"display_name": "Nature"}}}]}
        with mock.patch.object(dbtools.lit, "_json", return_value=fake):
            out = dbtools.openalex_works("p53 structure")
        self.assertEqual(out, "2024 | A structural study of p53 | https://doi.org/10.1/x | Nature")

    def test_pdb_lines_join_search_and_entry_details(self):
        search = {"result_set": [{"identifier": "9CKJ"}]}
        entry = {"struct": {"title": "Co-crystal structure of 53BP1"}, "exptl": [{"method": "X-RAY DIFFRACTION"}],
                 "rcsb_entry_info": {"resolution_combined": [2.25]}}
        with mock.patch.object(dbtools, "_post", return_value=search), mock.patch.object(dbtools.lit, "_json", return_value=entry):
            out = dbtools.pdb_structures("TP53")
        self.assertEqual(out, "9CKJ | Co-crystal structure of 53BP1 | X-RAY DIFFRACTION | 2.25")


class NotFound(unittest.TestCase):
    def test_a_missing_compound_says_so_instead_of_failing(self):
        with mock.patch.object(dbtools.lit, "_json", side_effect=Exception("404 Client Error: Not Found")):
            self.assertIn("found no compound", dbtools.pubchem_compound("nonexistentxyz"))

    def test_a_missing_alphafold_prediction_says_so(self):
        with mock.patch.object(dbtools.lit, "_json", side_effect=Exception("404 Client Error")):
            self.assertIn("no prediction", dbtools.alphafold_structure("Q0000"))

    def test_a_network_failure_is_reported_in_one_line(self):
        with mock.patch.object(dbtools.lit, "_json", side_effect=OSError("timed out")):
            self.assertIn("Ensembl", dbtools.ensembl_gene("TP53"))


if __name__ == "__main__":
    unittest.main()

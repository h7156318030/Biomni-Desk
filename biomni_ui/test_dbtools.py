import unittest
from unittest import mock

from biomni_ui import dbtools as d, fast_tools


def resp(payload):
    return mock.Mock(json=lambda: payload)


class Formatting(unittest.TestCase):
    def test_clinical_trials_rows(self):
        payload = {"totalCount": 1, "studies": [{"protocolSection": {"identificationModule": {"nctId": "NCT1", "briefTitle": "A trial"},
                   "statusModule": {"overallStatus": "RECRUITING", "startDateStruct": {"date": "2026-01"}},
                   "designModule": {"phases": ["PHASE1", "PHASE2"], "enrollmentInfo": {"count": 9}},
                   "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Acme"}}}}]}
        with mock.patch.object(d.lit, "_json", return_value=payload):
            out = d.clinical_trials("x")
        self.assertIn("NCT1 | A trial | PHASE1/PHASE2 | RECRUITING | Acme | 2026-01 | enrolled 9", out)

    def test_gnomad_verdict_uses_loeuf(self):
        body = {"data": {"gene": {"symbol": "G", "gnomad_constraint": {"pli": 1.0, "oe_lof": 0.1, "oe_lof_upper": 0.2, "mis_z": 3.0, "lof_z": 5.0, "exp_lof": 40.0, "obs_lof": 4}}}}
        with mock.patch.object(d, "_post", return_value=body):
            self.assertIn("strong constraint", d.gnomad_constraint("G"))
        body["data"]["gene"]["gnomad_constraint"]["oe_lof_upper"] = 0.9
        with mock.patch.object(d, "_post", return_value=body):
            self.assertIn("weak constraint", d.gnomad_constraint("G"))

    def test_chembl_drops_unit_errors_and_duplicates(self):
        acts = [{"molecule_chembl_id": "C1", "standard_value": "0.000001", "assay_type": "B", "canonical_smiles": "C"},
                {"molecule_chembl_id": "C2", "standard_value": "0.5", "assay_type": "B", "canonical_smiles": "CC", "molecule_pref_name": "DRUG"},
                {"molecule_chembl_id": "C2", "standard_value": "0.6", "assay_type": "B", "canonical_smiles": "CC"}]
        calls = [{"targets": [{"target_type": "SINGLE PROTEIN", "organism": "Homo sapiens", "target_chembl_id": "T1", "pref_name": "EGFR"}]}, {"activities": acts}]
        with mock.patch.object(d.lit, "_json", side_effect=calls):
            out = d.chembl_target_compounds("EGFR")
        self.assertIn("DRUG (C2)", out)
        self.assertNotIn("C1", out.split(":", 1)[1])
        self.assertEqual(out.count("C2"), 1)

    def test_failures_are_reported_not_raised(self):
        with mock.patch.object(d.lit, "_json", side_effect=RuntimeError("boom")):
            for fn, arg in ((d.clinical_trials, "x"), (d.geo_search, "x"), (d.string_interactions, "TP53"), (d.uniprot_lookup, "x"), (d.fda_adverse_events, "x")):
                self.assertIn("query failed", fn(arg))


class Schemas(unittest.TestCase):
    def test_every_db_tool_has_a_schema_that_matches_its_signature(self):
        names = {s["name"] for s in fast_tools.SCHEMAS}
        self.assertTrue(set(fast_tools.DB_TOOLS) <= names)
        for s in fast_tools._db_schemas():
            self.assertTrue(s["description"].startswith("Database tool"))
            self.assertTrue(len(s["description"]) > 40, s["name"])


if __name__ == "__main__":
    unittest.main()

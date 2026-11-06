import tempfile
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import connectors, permissions


class AutoModeGrants(unittest.TestCase):
    def setUp(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = mock.patch.object(permissions, "GRANTS", Path(d.name) / "grants.json")
        p.start()
        self.addCleanup(p.stop)

    def test_automatic_tasks_are_refused_until_the_database_is_allowed_in_settings(self):
        self.assertEqual(permissions.decide("ensembl_gene", "Ensembl", "c1", None, interactive=False, emit=lambda e: None, cancel=lambda: False), "deny")
        self.assertTrue(connectors.set_always("ensembl", True))
        self.assertEqual(permissions.decide("ensembl_gene", "Ensembl", "c1", None, interactive=False, emit=lambda e: None, cancel=lambda: False), "allow")

    def test_the_listing_shows_which_databases_are_allowed_everywhere(self):
        connectors.set_always("pdb", True)
        rows = {r["id"]: r for r in connectors.listing()}
        self.assertTrue(rows["pdb"]["always"])
        self.assertFalse(rows["pubchem"]["always"])

    def test_allowing_can_be_taken_back(self):
        connectors.set_always("openalex", True)
        connectors.set_always("openalex", False)
        self.assertFalse(next(r for r in connectors.listing() if r["id"] == "openalex")["always"])

    def test_an_unknown_database_is_reported(self):
        self.assertFalse(connectors.set_always("no-such-database", True))

    def test_the_refusal_names_the_way_to_allow_it_and_forbids_a_back_door(self):
        msg = connectors.refusal_message("Ensembl gene records")
        self.assertIn("Settings → Databases", msg)
        self.assertIn("Do not reach the same service another way", msg)


if __name__ == "__main__":
    unittest.main()

import pickle
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "biomni" / "tool" / "database.py"
SCHEMAS = ROOT / "biomni" / "tool" / "schema_db"


class SchemaFiles(unittest.TestCase):
    def test_every_file_the_query_tools_open_exists_and_is_usable(self):
        wanted = sorted(set(re.findall(r'schema_db",\s*"([\w.\-]+\.pkl)"', DB.read_text(encoding="utf-8"))))
        self.assertGreater(len(wanted), 25)
        missing = [w for w in wanted if not (SCHEMAS / w).exists()]
        self.assertEqual(missing, [], "run: python -m biomni_ui.build_schema_db")
        for w in wanted:
            obj = pickle.loads((SCHEMAS / w).read_bytes())
            self.assertTrue(isinstance(obj, dict) and obj, w)
            self.assertTrue(obj.get("endpoints") or obj.get("search_services"), w)
            self.assertTrue(obj.get("description"), w)

    def test_the_two_tools_with_upstream_bugs_are_replaced(self):
        import biomni.tool.database as db
        from biomni_ui import query_fixes

        query_fixes.install()
        self.assertIs(db.query_geo, query_fixes.query_geo)
        self.assertIs(db.query_gnomad, query_fixes.query_gnomad)

    def test_fixed_tools_report_errors_instead_of_raising(self):
        from biomni_ui import query_fixes

        self.assertIn("error", query_fixes.query_geo())
        self.assertIn("error", query_fixes.query_gnomad())


if __name__ == "__main__":
    unittest.main()

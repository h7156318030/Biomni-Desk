import unittest

from biomni_ui import cache, tooluniverse_gateway as tug


class TtlCache(unittest.TestCase):
    def test_a_repeat_inside_the_window_is_answered_from_memory_and_an_error_is_not_cached(self):
        calls = []

        @cache.ttl_cache(ttl=60)
        def f(x):
            calls.append(x)
            if x == "boom":
                raise RuntimeError("no")
            return x * 2

        self.assertEqual(f(2), 4)
        self.assertEqual(f(2), 4)
        self.assertEqual(calls, [2])  # the second call did not run the function
        with self.assertRaises(RuntimeError):
            f("boom")
        with self.assertRaises(RuntimeError):
            f("boom")
        self.assertEqual(calls.count("boom"), 2)  # an exception is never stored


class ToolUniverseGateway(unittest.TestCase):
    def test_search_finds_chembl_tools_and_names_the_required_arguments(self):
        text = tug.tooluniverse_search("chembl target", 3)
        self.assertIn("ToolUniverse", text)
        self.assertIn("OpenTargets", text)

    def test_an_empty_query_asks_for_keywords(self):
        self.assertIn("keyword", tug.tooluniverse_search("  "))

    def test_run_without_a_name_asks_for_one(self):
        self.assertIn("tool name", tug.tooluniverse_run(""))


class Registration(unittest.TestCase):
    def test_the_new_tools_are_in_the_catalog_and_the_registration_visualization_has_a_function(self):
        from biomni_ui import biomni_tools as bt

        names = {t["name"]: t["status"] for t in bt.catalog()}
        for n in ("civic_gene_variants", "ena_run_table", "tooluniverse_search", "tooluniverse_run"):
            self.assertIn(n, names)
        from biomni.tool import bioimaging
        self.assertTrue(callable(bioimaging.create_registration_visualization))


if __name__ == "__main__":
    unittest.main()

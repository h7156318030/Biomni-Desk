import unittest
from unittest import mock

from biomni_ui import environment


class ProbePython(unittest.TestCase):
    def test_installed_and_missing_packages_are_told_apart(self):
        def fake_spec(name):
            return object() if name == "scanpy" else None

        with mock.patch("importlib.util.find_spec", side_effect=fake_spec):
            have, missing = environment.probe_python(("scanpy", "squidpy"))
        self.assertEqual(have, ["scanpy"])
        self.assertEqual(missing, ["squidpy"])

    def test_a_broken_spec_counts_as_missing_not_as_an_error(self):
        with mock.patch("importlib.util.find_spec", side_effect=ValueError("bad")):
            have, missing = environment.probe_python(("x",))
        self.assertEqual((have, missing), ([], ["x"]))


class ProbeR(unittest.TestCase):
    def test_no_rscript_means_no_r_packages(self):
        with mock.patch("shutil.which", return_value=None):
            r = environment.probe_r(("Seurat",))
        self.assertEqual(r, {"available": False, "have": [], "missing": ["Seurat"]})

    def test_the_packages_R_reports_are_the_installed_ones(self):
        out = mock.Mock(stdout="DESeq2\nSeurat\n")
        with mock.patch("shutil.which", return_value="/usr/bin/Rscript"), mock.patch("subprocess.run", return_value=out):
            r = environment.probe_r(("Seurat", "DESeq2", "edgeR"))
        self.assertTrue(r["available"])
        self.assertEqual(r["have"], ["DESeq2", "Seurat"])
        self.assertEqual(r["missing"], ["edgeR"])


class LineText(unittest.TestCase):
    def setUp(self):
        with environment._lock:
            self._saved = dict(environment._state)
            environment._state.update({"python": None, "r": None})
        self.addCleanup(self._restore)

    def _restore(self):
        with environment._lock:
            environment._state.clear()
            environment._state.update(self._saved)

    def test_nothing_is_said_before_the_probe_has_finished(self):
        self.assertEqual(environment.line(), "")

    def test_the_line_lists_what_is_installed_and_what_is_not(self):
        with environment._lock:
            environment._state.update({"python": (["scanpy"], ["squidpy"]), "r": {"available": False, "have": [], "missing": ["Seurat"]}})
        text = environment.line()
        self.assertIn("installed scanpy", text)
        self.assertIn("not installed squidpy", text)
        self.assertIn("Rscript is not installed on this computer", text)

    def test_r_packages_are_listed_when_R_is_there(self):
        with environment._lock:
            environment._state.update({"python": (["scanpy"], []), "r": {"available": True, "have": ["DESeq2"], "missing": ["Seurat"]}})
        text = environment.line()
        self.assertIn("R packages installed DESeq2", text)
        self.assertIn("not installed Seurat", text)


if __name__ == "__main__":
    unittest.main()

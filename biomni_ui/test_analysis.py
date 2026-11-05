import os
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from biomni_ui import analysis


class InTemp(unittest.TestCase):
    def setUp(self):
        self.old = os.getcwd()
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        os.chdir(self.tmp.name)

    def tearDown(self):
        os.chdir(self.old)
        self.tmp.cleanup()


class Deseq(InTemp):
    def make(self, integer=True):
        rng = np.random.default_rng(0)
        genes = [f"G{i}" for i in range(120)]
        base = rng.integers(20, 500, size=len(genes)).astype(float)
        cols = {}
        for i in range(3):
            cols[f"c{i}"] = rng.poisson(base)
        for i in range(3):
            fc = np.ones(len(genes))
            fc[:10] = 8.0  # ten clearly up-regulated genes
            cols[f"t{i}"] = rng.poisson(base * fc)
        counts = pd.DataFrame(cols, index=genes)
        if not integer:
            counts = counts + 0.37
        counts.to_csv("counts.csv")
        pd.DataFrame({"condition": ["ctrl"] * 3 + ["treat"] * 3}, index=list(cols)).to_csv("meta.csv")

    def test_known_up_genes_are_found(self):
        self.make()
        out = analysis.de_deseq2("counts.csv", "meta.csv", "condition", "treat", "ctrl")
        self.assertIn("deseq2_results.csv", out)
        res = pd.read_csv("deseq2_results.csv", index_col=0)
        hits = set(res[(res["padj"] < 0.05) & (res["log2FoldChange"] > 1)].index)
        self.assertGreaterEqual(len(hits & {f"G{i}" for i in range(10)}), 8)
        self.assertTrue(Path("deseq2_volcano.png").exists())

    def test_non_integer_input_is_refused(self):
        self.make(integer=False)
        self.assertIn("raw integer counts", analysis.de_deseq2("counts.csv", "meta.csv", "condition", "treat", "ctrl"))

    def test_bad_group_and_replicates_are_explained(self):
        self.make()
        self.assertIn("has no level nope", analysis.de_deseq2("counts.csv", "meta.csv", "condition", "nope", "ctrl"))
        md = pd.read_csv("meta.csv", index_col=0)
        md.iloc[1:3, 0] = "treat"
        md.to_csv("meta2.csv")
        self.assertIn("at least 2 replicates", analysis.de_deseq2("counts.csv", "meta2.csv", "condition", "treat", "ctrl"))


class Survival(InTemp):
    def test_two_groups_km_and_cox(self):
        rng = np.random.default_rng(1)
        n = 120
        grp = np.array(["A", "B"] * (n // 2))
        t = rng.exponential(np.where(grp == "A", 20, 8))
        pd.DataFrame({"t": t, "e": rng.random(n) < 0.8, "grp": grp, "age": rng.normal(60, 8, n)}).assign(e=lambda d: d.e.astype(int)).to_csv("s.csv", index=False)
        out = analysis.survival_km_cox("s.csv", "t", "e", "grp", ["age"])
        self.assertIn("log-rank P", out)
        self.assertIn("HR", out.replace("风险", "HR"))
        self.assertTrue(Path("survival_km.png").exists() and Path("survival_cox.csv").exists())

    def test_event_column_must_be_binary(self):
        pd.DataFrame({"t": [1, 2, 3], "e": [1, 2, 0]}).to_csv("s.csv", index=False)
        self.assertIn("0/1", analysis.survival_km_cox("s.csv", "t", "e"))


class Small(InTemp):
    def test_molecule_properties(self):
        out = analysis.molecule_properties(["CC(=O)Oc1ccccc1C(=O)O", "not-a-smiles"])
        df = pd.read_csv("molecules.csv")
        self.assertEqual(int(df["valid"].sum()), 1)
        aspirin = df[df["valid"]].iloc[0]
        self.assertAlmostEqual(aspirin["MW"], 180.2, delta=0.2)
        self.assertEqual(aspirin["Lipinski violations"], 0)
        self.assertIn("not ADMET predictions", out)

    def test_primers_for_a_random_template(self):
        rng = np.random.default_rng(3)
        seq = "".join(rng.choice(list("ACGT"), 500))
        out = analysis.design_primers(seq, 200, 50, 150, 350)
        self.assertTrue("pair 1:" in out or "No acceptable primer pair" in out)
        self.assertIn("too short", analysis.design_primers("ACGT" * 5))

    def test_power_known_values(self):
        self.assertIn("at least 64 per group", analysis.power_sample_size("ttest", 0.5))
        self.assertIn("247 events", analysis.power_sample_size("survival", 0.7))
        self.assertIn("at least", analysis.power_sample_size("proportion", 0.5, p0=0.3))

    def test_meta_analysis_matches_hand_computation(self):
        pd.DataFrame({"study": list("abc"), "effect": [0.2, 0.4, 0.3], "se": [0.1, 0.1, 0.1]}).to_csv("m.csv", index=False)
        out = analysis.meta_analysis("m.csv")
        self.assertIn("Fixed effect: 0.3 ", out)
        self.assertIn("I²=0%", out)
        self.assertTrue(Path("meta_forest.png").exists())

    def test_plate_layout_keeps_edges_empty_and_is_reproducible(self):
        out = analysis.plate_layout(["s1", "s2", "s3"], 3)
        df = pd.read_csv("plate.csv", index_col=0).fillna("")
        self.assertTrue((df.iloc[0] == "").all() and (df.iloc[-1] == "").all() and (df.iloc[:, 0] == "").all())
        self.assertEqual(int((df != "").sum().sum()), 15)  # 3 samples + 2 controls, 3 replicates each
        first = df.copy()
        analysis.plate_layout(["s1", "s2", "s3"], 3)
        self.assertTrue(first.equals(pd.read_csv("plate.csv", index_col=0).fillna("")))
        self.assertIn("only", analysis.plate_layout([f"s{i}" for i in range(40)], 3))

    def test_enrich_refuses_a_tiny_gene_list(self):
        self.assertIn("at least 5", analysis.enrich_genes(["TP53", "EGFR"]))


class SingleCell(InTemp):
    def test_scanpy_pipeline_on_three_synthetic_populations(self):
        import anndata as ad

        rng = np.random.default_rng(0)
        n_genes, per = 300, 150
        mats = []
        for k in range(3):
            lam = np.full(n_genes, 0.3)
            lam[k * 20:(k + 1) * 20] = 6.0  # 20 marker genes per population
            mats.append(rng.poisson(lam, size=(per, n_genes)))
        X = np.vstack(mats).astype(np.float32)
        a = ad.AnnData(X, var=pd.DataFrame(index=[f"Gene{i}" for i in range(n_genes)]), obs=pd.DataFrame(index=[f"c{i}" for i in range(X.shape[0])]))
        a.write_h5ad("toy.h5ad")
        out = analysis.scrna_basic("toy.h5ad", min_genes=20, min_cells=3)
        self.assertIn("clusters", out)
        self.assertTrue(Path("scrna_umap.png").exists() and Path("scrna_markers.csv").exists())
        n_clusters = int(out.split(" genes, ")[1].split(" clusters")[0])
        self.assertGreaterEqual(n_clusters, 3)


if __name__ == "__main__":
    unittest.main()

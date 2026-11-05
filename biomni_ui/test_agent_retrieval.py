import unittest

from biomni_ui import agent_retrieval as ar


TOOLS = [{"name": f"tool_{i}", "description": f"Generic helper number {i} for something unrelated."} for i in range(60)]
TOOLS += [
    {"name": "gnomad_constraint", "description": "gnomAD v4 loss-of-function constraint: pLI, LOEUF for a gene."},
    {"name": "clinical_trials", "description": "Registered trials from ClinicalTrials.gov for a condition."},
    {"name": "pubmed_search", "description": "Search PubMed for papers and reviews."},
    {"name": "uniprot_lookup", "description": "UniProtKB protein entries for a gene."},
    {"name": "gwas_catalog", "description": "GWAS Catalog associations for a trait."},
]


class Prefilter(unittest.TestCase):
    def test_the_tools_that_share_words_with_the_question_are_kept(self):
        kept = [t["name"] for t in ar.prefilter("查 TP53 基因的 gnomAD 人群约束指标 pLI", TOOLS)]
        self.assertIn("gnomad_constraint", kept)
        self.assertLessEqual(len(kept), ar.TOP_K)

    def test_a_question_with_too_few_matches_passes_the_whole_list(self):
        self.assertIs(ar.prefilter("你好", TOOLS), TOOLS)
        self.assertIs(ar.prefilter("zzqx unknown", TOOLS), TOOLS)

    def test_the_list_is_cut_to_the_best_matches(self):
        many = [{"name": f"enzyme_{i}", "description": "enzyme kinase study"} for i in range(100)]
        self.assertEqual(len(ar.prefilter("enzyme kinase study", many, top_k=20)), 20)


class Attach(unittest.TestCase):
    def test_the_retriever_is_given_the_narrowed_tools_and_attaching_twice_is_harmless(self):
        seen = {}

        class Retriever:
            def prompt_based_retrieval(self, query, resources, llm=None):
                seen["tools"] = [t["name"] for t in resources["tools"]]
                return {"tools": [], "data_lake": [], "libraries": [], "know_how": []}

        class Agent:
            retriever = Retriever()

        agent = Agent()
        ar.attach(agent)
        ar.attach(agent)
        agent.retriever.prompt_based_retrieval("查 TP53 基因的 gnomAD 人群约束指标", {"tools": TOOLS, "data_lake": [], "libraries": []})
        self.assertIn("gnomad_constraint", seen["tools"])
        self.assertLess(len(seen["tools"]), len(TOOLS))


if __name__ == "__main__":
    unittest.main()

import unittest

from biomni_ui import skill_find


ITEMS = [
    {"id": "cell-cell-communication", "title": "细胞间通讯", "description": "配体受体，单细胞", "enabled": True},
    {"id": "cell-surface-antigen", "title": "细胞表面抗原", "description": "cell surface antigens", "enabled": True},
    {"id": "cell-therapy-car", "title": "CAR-T 细胞治疗", "description": "cell therapy design", "enabled": True},
    {"id": "scrnaseq-scanpy-core", "title": "单细胞 RNA-seq 基础分析（Scanpy）", "description": "单细胞数据质控与聚类", "enabled": True},
    {"id": "bulk-rnaseq-de", "title": "bulk RNA-seq 差异分析", "description": "bulk counts", "enabled": True},
    {"id": "old-single-cell", "title": "单细胞 旧版", "description": "", "enabled": False},
]


def ids(query, items=ITEMS):
    return [i["id"] for _, i in skill_find.scored(query, items)]


class Terms(unittest.TestCase):
    def test_a_hyphenated_term_is_one_word(self):
        self.assertIn("rnaseq", skill_find.terms("RNA-seq analysis"))
        self.assertNotIn("rna", skill_find.terms("RNA-seq analysis"))  # not counted again as rna and seq

    def test_english_terms_expand_to_the_chinese_words_in_titles(self):
        self.assertIn("单细胞", skill_find.terms("scRNA workflow"))
        self.assertIn("单细胞", skill_find.terms("single-cell atlas"))

    def test_words_that_most_skills_share_are_not_terms(self):
        self.assertEqual(skill_find.terms("cell data workflow"), set())

    def test_an_empty_query_has_no_terms(self):
        self.assertEqual(skill_find.terms(""), set())


class Ranking(unittest.TestCase):
    def test_the_single_cell_skill_ranks_first_for_a_single_cell_query(self):
        self.assertEqual(ids("single-cell RNA-seq analysis")[0], "scrnaseq-scanpy-core")

    def test_a_chinese_query_finds_the_chinese_title(self):
        self.assertEqual(ids("单细胞 分析")[0], "scrnaseq-scanpy-core")

    def test_a_disabled_skill_is_never_offered(self):
        self.assertNotIn("old-single-cell", ids("单细胞"))

    def test_a_query_with_no_shared_word_gives_nothing(self):
        self.assertEqual(ids("蛋白质 结构预测"), [])

    def test_a_skill_that_shares_only_generic_words_is_not_found(self):
        self.assertEqual(ids("cell type"), [])

    def test_empty_items_give_nothing(self):
        self.assertEqual(skill_find.scored("单细胞", []), [])


if __name__ == "__main__":
    unittest.main()

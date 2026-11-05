import unittest

from biomni_ui import audit


EVIDENCE = ("Example Biotech Co., Ltd | Jiangsu University; Qiqihar University; Example Biotech Co., Ltd\n"
            "PMID: 38759653 | Modified lentiviral globin gene therapy | DOI 10.1016/j.stem.2024.04.021")


class ChineseOrganisationNames(unittest.TestCase):
    def test_a_company_name_that_no_output_contains_is_listed(self):
        items = audit.ungrounded("这位作者的经历包括上海邦耀生物科技。", EVIDENCE)
        self.assertEqual(len(items), 1)
        self.assertTrue(any("上海邦耀生物科技" in m for m in items[0]["missing"]))
        self.assertFalse(any(m.startswith("经历") for m in items[0]["missing"]))  # the lead-in words are not part of the name

    def test_the_note_names_the_organisation_for_checking(self):
        items = audit.ungrounded("相关机构是上海邦耀生物科技。", EVIDENCE)
        note = audit.ungrounded_note(items)
        self.assertIn("上海邦耀生物科技", note)
        self.assertIn("Unverified", note)

    def test_an_answer_that_only_uses_the_outputs_names_is_not_flagged(self):
        self.assertEqual(audit.ungrounded("作者单位是 Example Biotech Co., Ltd，PMID 38759653。", EVIDENCE), [])

    def test_identifiers_are_left_to_the_citation_check(self):
        items = audit.ungrounded("该论文 PMID 99999999 发表于 2024 年。", EVIDENCE)
        self.assertFalse(any("99999999" in m for i in items for m in i["missing"]))  # the citation check (audit.unsupported) owns identifiers



class OrcidDates(unittest.TestCase):
    def test_a_date_written_as_year_month_day_fields_counts_as_found(self):
        ev = "{'year': {'value': '2021'}, 'month': {'value': '06'}, 'day': {'value': '20'}} {'year': {'value': '2024'}, 'month': {'value': '10'}, 'day': {'value': '15'}}"
        self.assertEqual(audit.ungrounded("任职时间为 2021-06-20 至 2024-10-15。", ev), [])
        self.assertTrue(audit.ungrounded("任职时间为 2022-06-20。", ev))  # a date that is not there is still flagged

if __name__ == "__main__":
    unittest.main()

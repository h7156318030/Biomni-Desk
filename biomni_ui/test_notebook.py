import unittest

from biomni_ui import notebook


class Build(unittest.TestCase):
    def conversation(self):
        return {"tasks": [
            {"id": "t1", "prompt": "Count the rows", "events": [
                {"type": "code", "language": "python", "code": "print(3)", "elapsed": 0.4, "seq": 1},
                {"type": "observation", "text": "3", "files": ["/w/rows.csv"], "seq": 2},
                {"type": "tool", "tool": "uniprot_lookup", "query": "TP53", "seq": 3},
                {"type": "answer", "text": "There are 3 rows.", "seq": 4},
            ]},
            {"id": "t2", "prompt": "Next question", "events": [
                {"type": "code", "language": "bash", "code": "ls", "seq": 1},
                {"type": "answer", "text": "Listed.", "seq": 2},
            ]},
        ]}

    def test_cells_follow_the_order_of_the_session(self):
        kinds = [c["kind"] for c in notebook.build(self.conversation())]
        self.assertEqual(kinds, ["question", "code", "tool", "answer", "question", "code", "answer"])

    def test_a_code_cell_takes_the_output_that_follows_it(self):
        code = notebook.build(self.conversation())[1]
        self.assertEqual(code["code"], "print(3)")
        self.assertEqual(code["output"], "3")
        self.assertEqual(code["files"], ["/w/rows.csv"])
        self.assertEqual(code["elapsed"], 0.4)

    def test_a_code_cell_without_output_stays_empty(self):
        code = notebook.build(self.conversation())[5]
        self.assertEqual(code["output"], "")

    def test_long_output_is_cut_but_not_lost_entirely(self):
        conv = {"tasks": [{"id": "t", "prompt": "q", "events": [
            {"type": "code", "language": "python", "code": "x", "seq": 1},
            {"type": "observation", "text": "y" * 9000, "seq": 2},
        ]}]}
        code = notebook.build(conv)[1]
        self.assertEqual(len(code["output"]), notebook.OUTPUT_CHARS)

    def test_empty_session(self):
        self.assertEqual(notebook.build({"tasks": []}), [])
        self.assertEqual(notebook.build({}), [])

    def test_environment_has_python_and_platform(self):
        env = notebook.environment()
        self.assertTrue(env["python"])
        self.assertTrue(env["platform"])


if __name__ == "__main__":
    unittest.main()

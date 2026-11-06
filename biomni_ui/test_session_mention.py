import tempfile
import unittest
from pathlib import Path

from biomni_ui import server as srv
from biomni_ui.store import Store


class SessionDigest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.store = Store(Path(self._tmp.name) / "t.db")
        self.addCleanup(self.store.close)
        saved = srv.store
        srv.store = self.store
        self.addCleanup(setattr, srv, "store", saved)
        self.store.create_task("t1", "c-past", "What is the EGFP length?")
        self.store.add_event("t1", {"seq": 1, "type": "answer", "text": "EGFP has 239 amino acids."})
        self.store.create_task("t2", "c-past", "And its gene map?")
        self.store.add_event("t2", {"seq": 1, "type": "answer", "text": "pEGFP-N1 map attached."})

    def test_the_digest_holds_the_recent_questions_and_answers(self):
        text = srv._session_digest("c-past")
        self.assertIn("What is the EGFP length?", text)
        self.assertIn("EGFP has 239 amino acids.", text)
        self.assertIn("pEGFP-N1 map attached.", text)
        self.assertIn("do not repeat", text)

    def test_the_digest_is_capped(self):
        long = "x" * 5000
        self.store.create_task("t3", "c-long", "long question")
        self.store.add_event("t3", {"seq": 1, "type": "answer", "text": long})
        self.assertLessEqual(len(srv._session_digest("c-long")), srv.SESSION_CONTEXT_CHARS + 600)

    def test_an_unknown_or_empty_session_gives_nothing(self):
        self.assertEqual(srv._session_digest("no-such-session"), "")
        self.assertEqual(srv._session_digest(""), "")


if __name__ == "__main__":
    unittest.main()

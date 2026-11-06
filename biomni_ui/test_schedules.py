import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from biomni_ui import schedules, skill_import, skills


class Task:
    def __init__(self, tid, conv):
        self.id = tid
        self.conversation_id = conv


class ValidateAndNext(unittest.TestCase):
    def test_interval_bounds(self):
        self.assertEqual(schedules.validate("every", 60, None), {"kind": "every", "minutes": 60})
        with self.assertRaises(ValueError):
            schedules.validate("every", 4, None)
        with self.assertRaises(ValueError):
            schedules.validate("every", None, None)

    def test_daily_time_format(self):
        self.assertEqual(schedules.validate("daily", None, "08:30"), {"kind": "daily", "time": "08:30"})
        for bad in ("8:30", "24:00", "12:60", ""):
            with self.assertRaises(ValueError):
                schedules.validate("daily", None, bad)

    def test_every_adds_minutes(self):
        self.assertEqual(schedules.next_after({"kind": "every", "minutes": 10}, 1000.0), 1600.0)

    def test_daily_is_later_today_or_tomorrow(self):
        now = time.mktime((2026, 11, 6, 9, 0, 0, 0, 0, -1))
        nxt = schedules.next_after({"kind": "daily", "time": "08:30"}, now)
        self.assertAlmostEqual(nxt - now, 23.5 * 3600, delta=1)  # 08:30 has passed, so tomorrow
        later = schedules.next_after({"kind": "daily", "time": "18:00"}, now)
        self.assertAlmostEqual(later - now, 9 * 3600, delta=1)


class StoreAndRun(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.store = schedules.ScheduleStore(Path(self._tmp.name) / "schedules.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_create_list_update_delete(self):
        job = self.store.create("Daily TP53", "check TP53 news", "quick", {"kind": "every", "minutes": 30}, now=1000.0)
        self.assertEqual(job["next_run"], 1000.0 + 1800)
        self.assertEqual(len(self.store.list()), 1)
        job2 = self.store.update(job["id"], "renamed", "new prompt", "quick", {"kind": "every", "minutes": 60}, enabled=False, now=2000.0)
        self.assertIsNone(job2["next_run"])
        self.assertEqual(job2["name"], "renamed")
        self.assertTrue(self.store.delete(job["id"]))
        self.assertFalse(self.store.delete(job["id"]))

    def test_due_job_starts_and_moves_forward(self):
        job = self.store.create("j", "q", None, {"kind": "every", "minutes": 5}, now=0.0)
        calls = []
        started = schedules.run_due(self.store, lambda j: (calls.append(j["id"]), Task("t1", "c1"))[1], lambda: True, now=job["next_run"] + 1)
        self.assertEqual(started, [job["id"]])
        after = self.store.get(job["id"])
        self.assertEqual(after["last_status"], "started")
        self.assertEqual(after["last_task_id"], "t1")
        self.assertEqual(after["last_conversation_id"], "c1")
        self.assertGreater(after["next_run"], job["next_run"])

    def test_busy_agent_skips_and_retries_soon(self):
        job = self.store.create("j", "q", None, {"kind": "every", "minutes": 5}, now=0.0)
        now = job["next_run"] + 1

        def busy(_j):
            raise schedules.SkipRun("a task is running")

        schedules.run_due(self.store, busy, lambda: True, now=now)
        after = self.store.get(job["id"])
        self.assertTrue(after["last_status"].startswith("skipped"))
        self.assertEqual(after["next_run"], now + schedules.RETRY_SECONDS)

    def test_not_ready_agent_starts_nothing(self):
        job = self.store.create("j", "q", None, {"kind": "every", "minutes": 5}, now=0.0)
        self.assertEqual(schedules.run_due(self.store, lambda j: Task("x", "y"), lambda: False, now=job["next_run"] + 1), [])
        self.assertIsNone(self.store.get(job["id"])["last_run"])

    def test_disabled_job_never_runs(self):
        self.store.create("j", "q", None, {"kind": "every", "minutes": 5}, enabled=False, now=0.0)
        self.assertEqual(schedules.run_due(self.store, lambda j: Task("x", "y"), lambda: True, now=10**10), [])

    def test_one_failing_job_does_not_stop_the_others(self):
        bad = self.store.create("bad", "q1", None, {"kind": "every", "minutes": 5}, now=0.0)
        good = self.store.create("good", "q2", None, {"kind": "every", "minutes": 5}, now=0.0)
        now = bad["next_run"] + 1

        def start(job):
            if job["id"] == bad["id"]:
                raise RuntimeError("boom")
            return Task("t", "c")

        started = schedules.run_due(self.store, start, lambda: True, now=now)
        self.assertEqual(started, [good["id"]])
        self.assertIn("failed", self.store.get(bad["id"])["last_status"])

    def test_loop_stops_when_asked(self):
        stop = threading.Event()
        stop.set()
        schedules.loop(self.store, lambda j: Task("x", "y"), lambda: True, stop, interval=0.01)  # returns at once


class SkillImport(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.store = skills.SkillStore(root / "skills", root / "state.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_github_file_page_becomes_raw_address(self):
        self.assertEqual(
            skill_import.raw_address("https://github.com/owner/repo/blob/main/skills/kinase.md"),
            "https://raw.githubusercontent.com/owner/repo/main/skills/kinase.md",
        )
        self.assertEqual(skill_import.raw_address("https://example.org/x.md"), "https://example.org/x.md")

    def test_only_https_is_accepted(self):
        with self.assertRaises(ValueError):
            skill_import.raw_address("http://example.org/x.md")
        with self.assertRaises(ValueError):
            skill_import.raw_address("file:///C:/secret.md")

    def test_import_saves_a_user_skill_with_source(self):
        text = "---\ntitle: Kinase panel check\ndescription: Check a kinase panel\nwhen_to_use: Panel questions\n---\nStep one. Step two."
        from biomni_ui import github_skills

        with tempfile.TemporaryDirectory() as d, mock.patch.object(github_skills, "SOURCES", Path(d) / "sources.json"):
            skill = skill_import.import_skill(self.store, "https://github.com/o/r/blob/main/k.md", fetcher=lambda raw: text,
                                              commit_lookup=lambda *a: "abc123")
            self.assertEqual(github_skills.sources()["kinase-panel-check"]["commit"], "abc123")
        self.assertEqual(skill["id"], "kinase-panel-check")
        self.assertEqual(skill["source"], "mine")  # the store's label for the user's own skills
        self.assertIn("Imported from https://github.com/o/r/blob/main/k.md", skill["body"])

    def test_missing_title_or_body_is_refused(self):
        with self.assertRaises(ValueError):
            skill_import.import_skill(self.store, "https://example.org/a.md", fetcher=lambda raw: "no front matter here")
        with self.assertRaises(ValueError):
            skill_import.import_skill(self.store, "https://example.org/a.md", fetcher=lambda raw: "---\ntitle: X\n---\n")

    def test_existing_name_is_refused(self):
        text = "---\ntitle: Same name\n---\nbody"
        skill_import.import_skill(self.store, "https://example.org/a.md", fetcher=lambda raw: text)
        with self.assertRaises(FileExistsError):
            skill_import.import_skill(self.store, "https://example.org/b.md", fetcher=lambda raw: text)

    def test_slug_fallback(self):
        self.assertEqual(skill_import.slug("!!!"), "imported-skill")
        self.assertEqual(skill_import.slug("CRISPR Guide Design"), "crispr-guide-design")


if __name__ == "__main__":
    unittest.main()

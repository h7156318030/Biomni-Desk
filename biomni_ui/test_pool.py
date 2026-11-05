import unittest

from biomni_ui.runner import Manager


class FakeSlot:
    alive = True

    def __init__(self, name):
        self.name, self.busy, self.ran, self.cancelled, self.cmds = name, False, [], [], []

    def available(self):
        return self.alive and not self.busy

    def run(self, task):
        self.busy = True
        self.ran.append(task)

    def cancel(self, task_id):
        self.cancelled.append(task_id)

    def command(self, name):
        self.cmds.append(name)

    def finish(self, task, manager):
        self.busy = False
        task.emit({"type": "done"})
        manager._dispatch()


def manager_with(n_workers=2):
    m = Manager(lambda: None, None)
    m._local = FakeSlot("local")
    m._procs = [FakeSlot(f"w{i}") for i in range(n_workers)]
    return m


class Scheduling(unittest.TestCase):
    def test_tasks_in_different_conversations_run_at_once(self):
        m = manager_with()
        a, b, c = m.start("a", "c1"), m.start("b", "c2"), m.start("c", "c3")
        self.assertEqual([len(s.ran) for s in m._slots()], [1, 1, 1])
        self.assertTrue(m.busy)
        d = m.start("d", "c4")  # nothing free: waits and says so
        self.assertEqual([e for e in d.events if e["type"] == "status"][0]["state"], "queued")
        m._local.finish(a, m)
        self.assertEqual(m._local.ran, [a, d])
        for s, t in ((m._local, d), (m._procs[0], b), (m._procs[1], c)):
            s.finish(t, m)
        self.assertFalse(m.busy)

    def test_a_conversation_goes_back_to_the_slot_that_holds_its_memory(self):
        m = manager_with()
        a = m.start("a", "c1")
        m._local.finish(a, m)
        m.start("long", "c2")  # takes the local slot
        again = m.start("follow-up", "c1")  # c1 lives in local, which is busy: wait even though workers are free
        self.assertEqual([len(s.ran) for s in m._procs], [0, 0])
        self.assertEqual(again.events[0]["state"], "queued")

    def test_dead_worker_loses_its_conversations(self):
        m = manager_with(1)
        w = m._procs[0]
        m._local.busy = True
        a = m.start("a", "c1")
        self.assertEqual(w.ran, [a])
        w.finish(a, m)
        w.alive = False
        m._local.busy = False
        b = m.start("again", "c1")
        self.assertEqual(m._local.ran, [b])

    def test_cancel_of_a_waiting_task_ends_it_at_once(self):
        m = manager_with(1)
        m._local.busy = m._procs[0].busy = True
        t = m.start("x", "c1")
        self.assertTrue(m.cancel(t.id))
        self.assertTrue(t.finished)
        self.assertEqual(t.events[-1]["type"], "cancelled")
        self.assertEqual(m._pending, [])

    def test_cancel_reaches_the_workers(self):
        m = manager_with(1)
        m._local.busy = True
        t = m.start("x", "c1")
        m.cancel(t.id)
        self.assertEqual(m._procs[0].cancelled, [t.id])

    def test_running_in_and_reset(self):
        m = manager_with(1)
        t = m.start("x", "c1")
        self.assertTrue(m.running_in("c1"))
        self.assertFalse(m.running_in("c2"))
        m.reset_agent()
        self.assertEqual(m._procs[0].cmds, ["reset"])
        m._local.finish(t, m)
        self.assertFalse(m.running_in("c1"))


if __name__ == "__main__":
    unittest.main()

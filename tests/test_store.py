import tempfile
import unittest
from pathlib import Path

from ai_desk.store import TaskStore


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = TaskStore(Path(self.temp.name) / "test.sqlite3")

    def tearDown(self):
        self.temp.cleanup()

    def create(self, key="same-key"):
        return self.store.create_task(
            instruction="Check the test project",
            target_device_id="mac-studio",
            adapter="dry-run",
            working_directory_id="demo",
            idempotency_key=key,
        )

    def test_create_task_and_event(self):
        task, created = self.create()
        self.assertTrue(created)
        self.assertEqual(task["status"], "queued")
        self.assertEqual(len(self.store.list_events(task["id"])), 1)

    def test_idempotency_key_does_not_duplicate_task(self):
        first, created_first = self.create("idempotent")
        second, created_second = self.create("idempotent")
        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(len(self.store.list_tasks()), 1)

    def test_status_transition_is_recorded(self):
        task, _ = self.create()
        updated = self.store.set_status(task["id"], "succeeded", summary="dry-run ok")
        self.assertEqual(updated["status"], "succeeded")
        self.assertEqual(self.store.list_events(task["id"])[-1]["event_type"], "task.succeeded")


if __name__ == "__main__":
    unittest.main()

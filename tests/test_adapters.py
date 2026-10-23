import unittest

from ai_desk.adapters import AdapterError, run_adapter, run_dry_run


class AdapterTests(unittest.TestCase):
    def test_dry_run_returns_explicit_non_execution_warning(self):
        result = run_dry_run({
            "instruction": "Inspect project status",
            "target_device_id": "mac-studio",
        })
        self.assertEqual(result["status"], "succeeded")
        self.assertTrue(any("no application or command was executed" in w for w in result["warnings"]))

    def test_unknown_adapter_is_rejected(self):
        with self.assertRaises(AdapterError):
            run_adapter("shell", {"instruction": "do anything"})

    def test_empty_instruction_is_rejected(self):
        with self.assertRaises(AdapterError):
            run_dry_run({"instruction": " ", "target_device_id": "mac-studio"})


if __name__ == "__main__":
    unittest.main()

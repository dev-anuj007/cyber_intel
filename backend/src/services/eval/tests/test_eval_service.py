"""Unit tests for EvalService."""

import unittest
from src.services.eval.eval_service import EvalService


class TestEvalService(unittest.TestCase):
    def setUp(self):
        self.service = EvalService()

    def test_eval_service_list_prompts(self):
        prompts = self.service.list_prompts()
        self.assertGreaterEqual(len(prompts), 1)
        versions = [p["version"] for p in prompts]
        self.assertTrue(any("v2.0" in v or "v1.0" in v for v in versions))

    def test_eval_service_history_and_benchmark_dry_run(self):
        history = self.service.list_history()
        self.assertIsInstance(history, list)

        result = self.service.run_eval(prompt_version="v2.0", dry_run=True)
        self.assertTrue(result["success"])
        self.assertIn("results", result)
        self.assertEqual(result["results"]["tier_accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()

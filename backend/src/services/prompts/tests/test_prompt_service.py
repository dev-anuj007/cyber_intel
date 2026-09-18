import unittest
from src.services.prompts.prompt_service import PromptService
from src.services.prompts.repositories.reader import LocalPromptRepository


class TestPromptService(unittest.TestCase):
    def setUp(self):
        self.repo = LocalPromptRepository()
        self.service = PromptService(repository=self.repo)

    def test_list_prompts(self):
        prompts = self.service.list_prompts()
        self.assertGreaterEqual(len(prompts), 3)
        versions = [p["version"] for p in prompts]
        self.assertIn("v2.0", versions)
        self.assertIn("v1.0", versions)

    def test_get_template(self):
        t2 = self.service.get_template("v2.0")
        self.assertIn("{account_context}", t2)
        self.assertIn("tier_1_critical", t2)

        t1 = self.service.get_template("v1.0")
        self.assertIn("{account_context}", t1)

    def test_register_prompt(self):
        registered = self.service.register_prompt(
            name="account_scoring",
            version="v3.0-custom",
            template="Custom prompt: {account_context}",
            prompt_type="scoring",
        )
        self.assertEqual(registered["version"], "v3.0-custom")
        fetched = self.service.get_prompt("account_scoring", "v3.0-custom")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["template"], "Custom prompt: {account_context}")


if __name__ == "__main__":
    unittest.main()

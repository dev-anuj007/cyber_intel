"""Unit tests for ScorerService."""

import unittest
import tempfile
import shutil
from pathlib import Path

from src.services.database import init_database
from src.services.scorer.scorer_service import ScorerService
from src.services.accounts.types import Account, Asset, SecuritySignal, SignalSeverity


class TestScorerService(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_scorer.db"
        init_database(db_path=self.db_path)
        self.scorer = ScorerService(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_scorer_format_context_and_cost(self):
        account = Account(
            account_key="domain:cloudcorp.io",
            domains=["cloudcorp.io"],
            assets=[Asset(ip="1.2.3.4", port=443, hostname="app.cloudcorp.io")],
            ips=["1.2.3.4"],
            hostnames=["app.cloudcorp.io"],
            ports=[443],
            products=["Nginx 1.20"],
            cloud_providers=["GCP"],
            signals=[
                SecuritySignal(
                    name="high_severity_vulnerability",
                    severity=SignalSeverity.HIGH,
                    category="vulnerability",
                    evidence="CVSS 8.5 on exposed service",
                )
            ],
        )

        ctx = self.scorer.format_account_context(account)
        self.assertIn("domain:cloudcorp.io", ctx)
        self.assertIn("high_severity_vulnerability", ctx)

        cost = self.scorer.calculate_cost(input_tokens=1000, output_tokens=500)
        self.assertGreater(cost, 0)
        self.assertIsInstance(cost, float)

    def test_scorer_custom_prompt_template(self):
        account = Account(
            account_key="domain:test.com",
            domains=["test.com"],
            assets=[],
            ips=[],
            hostnames=[],
            ports=[],
            products=[],
            cloud_providers=[],
            signals=[],
        )

        prompt = self.scorer.get_prompt(
            account,
            custom_prompt_template="Custom Evaluation System:\n{account_context}\nScore now."
        )
        self.assertIn("Custom Evaluation System:", prompt)
        self.assertIn("domain:test.com", prompt)


if __name__ == "__main__":
    unittest.main()

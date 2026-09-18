"""Unit tests for AccountsService."""

import unittest
import tempfile
import shutil
from pathlib import Path

from src.services.database import init_database
from src.services.accounts.accounts_service import AccountsService
from src.services.accounts.types import Account, Asset, SecuritySignal, SignalSeverity


class TestAccountsService(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = Path(self.test_dir) / "test_accounts.db"
        init_database(db_path=self.db_path)
        self.service = AccountsService(db_path=self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_save_and_retrieve_account(self):
        account = Account(
            account_key="domain:testdomain.com",
            domains=["testdomain.com"],
            assets=[Asset(ip="192.168.1.1", port=443, hostname="vpn.testdomain.com")],
            ips=["192.168.1.1"],
            hostnames=["vpn.testdomain.com"],
            ports=[443],
            products=["Nginx"],
            cloud_providers=["GCP"],
            signals=[
                SecuritySignal(
                    name="kev_vulnerability",
                    severity=SignalSeverity.CRITICAL,
                    category="vulnerability",
                    evidence="CVE in KEV catalog",
                )
            ],
        )

        acc_id = self.service.save_account(account)
        self.assertGreater(acc_id, 0)

        retrieved = self.service.get_account("domain:testdomain.com")
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.account_key, "domain:testdomain.com")
        self.assertEqual(len(retrieved.signals), 1)

        stats = self.service.get_summary_stats()
        self.assertEqual(stats["total_accounts"], 1)
        self.assertEqual(stats["critical_count"], 1)

        search_results = self.service.search_accounts("testdomain")
        self.assertEqual(len(search_results), 1)


if __name__ == "__main__":
    unittest.main()

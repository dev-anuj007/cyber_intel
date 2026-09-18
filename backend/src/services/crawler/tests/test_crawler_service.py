"""Unit tests for CrawlerService, ScannerFactory, and Account Versioning."""

import unittest
from unittest.mock import patch, MagicMock
from src.services.crawler.crawler_service import CrawlerService
from src.services.crawler.scanners import (
    ScannerFactory,
    StandardCrawlerScanner,
    OwaspZapScanner,
    ProjectDiscoveryScanner,
    CisaKevScanner,
)
from src.services.accounts.types import Account


class TestCrawlerAndScanners(unittest.TestCase):
    def setUp(self):
        self.crawler = CrawlerService(timeout=1.0, ports=[80, 443])

    def test_scanner_factory_list(self):
        scanners = ScannerFactory.list_available_scanners()
        scanner_ids = [s["id"] for s in scanners]
        self.assertIn("all", scanner_ids)
        self.assertIn("standard", scanner_ids)
        self.assertIn("owasp_zap", scanner_ids)
        self.assertIn("projectdiscovery", scanner_ids)
        self.assertIn("cisa_kev", scanner_ids)

    def test_standard_scanner(self):
        scanner = ScannerFactory.get_scanner("standard")
        self.assertIsInstance(scanner, StandardCrawlerScanner)
        with patch.object(scanner, "resolve_ip", return_value="93.184.216.34"):
            with patch.object(scanner, "check_port_open", return_value=True):
                res = scanner.scan("example.com", {"enable_subdomains": False})
                self.assertEqual(res.domain, "example.com")
                self.assertEqual(res.scanner_type, "standard")
                self.assertGreaterEqual(len(res.assets), 1)

    def test_owasp_zap_scanner(self):
        scanner = ScannerFactory.get_scanner("owasp_zap")
        self.assertIsInstance(scanner, OwaspZapScanner)
        with patch("socket.gethostbyname", return_value="1.2.3.4"):
            res = scanner.scan("example.com")
            self.assertEqual(res.scanner_type, "owasp_zap")
            # Should have audited CSP, HSTS, XFO, etc.
            self.assertGreaterEqual(len(res.signals), 1)

    def test_projectdiscovery_scanner(self):
        scanner = ScannerFactory.get_scanner("projectdiscovery")
        self.assertIsInstance(scanner, ProjectDiscoveryScanner)
        with patch("socket.gethostbyname", return_value="1.2.3.4"):
            res = scanner.scan("example.com")
            self.assertEqual(res.scanner_type, "projectdiscovery")
            self.assertEqual(res.domain, "example.com")

    def test_cisa_kev_scanner(self):
        scanner = ScannerFactory.get_scanner("cisa_kev")
        self.assertIsInstance(scanner, CisaKevScanner)
        with patch("socket.gethostbyname", return_value="1.2.3.4"):
            res = scanner.scan("example.com")
            self.assertEqual(res.scanner_type, "cisa_kev")
            self.assertEqual(res.domain, "example.com")

    def test_composite_all_scanners(self):
        with patch("socket.gethostbyname", return_value="1.2.3.4"):
            with patch.object(StandardCrawlerScanner, "resolve_ip", return_value="1.2.3.4"):
                res = ScannerFactory.run_scan("example.com", "all", {"enable_subdomains": False})
                self.assertEqual(res.scanner_type, "all")
                self.assertGreaterEqual(len(res.assets), 1)

    def test_account_versioning_without_merge(self):
        """Verify that multiple crawls create v1, v2, v3 instead of merging."""
        mock_accounts_service = MagicMock()
        self.crawler.set_accounts_service(mock_accounts_service)

        # 1st crawl: No existing account
        mock_accounts_service.get_account.return_value = None
        k1, v1 = self.crawler._calculate_next_account_version("target.com")
        self.assertEqual(k1, "domain:target.com")
        self.assertEqual(v1, "v1")

        # 2nd crawl: v1 exists in DB
        def mock_get_acc(key):
            if key == "domain:target.com":
                return Account(account_key="domain:target.com", domain="target.com")
            return None

        mock_accounts_service.get_account.side_effect = mock_get_acc
        k2, v2 = self.crawler._calculate_next_account_version("target.com")
        self.assertEqual(k2, "domain:target.com:v2")
        self.assertEqual(v2, "v2")

        # 3rd crawl: v1 and v2 exist in DB
        def mock_get_acc_3(key):
            if key in ("domain:target.com", "domain:target.com:v2"):
                return Account(account_key=key, domain="target.com")
            return None

        mock_accounts_service.get_account.side_effect = mock_get_acc_3
        k3, v3 = self.crawler._calculate_next_account_version("target.com")
        self.assertEqual(k3, "domain:target.com:v3")
        self.assertEqual(v3, "v3")


if __name__ == "__main__":
    unittest.main()

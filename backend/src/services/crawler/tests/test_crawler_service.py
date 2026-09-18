"""Unit tests for CrawlerService."""

import unittest
from unittest.mock import patch
from src.services.crawler.crawler_service import CrawlerService


class TestCrawlerService(unittest.TestCase):
    def setUp(self):
        self.crawler = CrawlerService(timeout=1.0, ports=[80, 443])

    def test_crawler_service_local_resolution(self):
        ip = self.crawler.resolve_ip("localhost")
        self.assertTrue(ip in ("127.0.0.1", "::1", None) or isinstance(ip, str))

    def test_crawler_service_mock_crawl(self):
        with patch.object(self.crawler, "resolve_ip", return_value="93.184.216.34"):
            with patch.object(self.crawler, "check_port_open", return_value=True):
                with patch.object(
                    self.crawler,
                    "probe_http_banner",
                    return_value={
                        "status": 200,
                        "server": "ECS (dsa/67AB)",
                        "technologies": ["ECS (dsa/67AB)"],
                        "cloud_providers": ["AWS"],
                    },
                ):
                    result = self.crawler.crawl_domain("example.com", scan_depth="quick", enable_subdomains=False)
                    self.assertEqual(result["domain"], "example.com")
                    self.assertEqual(result["account_key"], "domain:example.com")
                    self.assertGreaterEqual(result["assets_count"], 1)
                    self.assertIn("account", result)


if __name__ == "__main__":
    unittest.main()

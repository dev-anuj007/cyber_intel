"""Unit tests for AggregatorService."""

import unittest
from src.services.aggregator.aggregator_service import (
    AggregatorService,
    normalize_domain,
    is_dynamic_ip_ptr,
    is_infrastructure_transit_domain,
)


class TestAggregatorService(unittest.TestCase):
    def setUp(self):
        self.service = AggregatorService()

    def test_domain_normalization(self):
        self.assertEqual(normalize_domain(" EXAMPLE.COM. "), "example.com")
        self.assertEqual(normalize_domain("sub.domain.org"), "sub.domain.org")

    def test_dynamic_ip_ptr_detection(self):
        self.assertTrue(is_dynamic_ip_ptr("107.154.80.208.ip.incapdns.net"))
        self.assertTrue(is_dynamic_ip_ptr("ec2-54-12-34-56.compute-1.amazonaws.com"))
        self.assertTrue(is_dynamic_ip_ptr("static-123-45-67-89.t-ipconnect.de"))
        self.assertFalse(is_dynamic_ip_ptr("vpn.acmecorp.com"))
        self.assertFalse(is_dynamic_ip_ptr("api.stripe.com"))

    def test_aggregator_signal_detection(self):
        features = {
            "ip": "1.2.3.4",
            "port": 8443,
            "kev_count": 2,
            "max_cvss": 9.8,
            "ransomware_count": 1,
            "max_epss": 0.85,
            "tags": ["eol-product"],
            "vulnerability_count": 6,
        }

        signals = self.service.detect_signals(features)
        sig_names = [s.name for s in signals]

        self.assertIn("kev_vulnerability", sig_names)
        self.assertIn("high_severity_vulnerability", sig_names)
        self.assertIn("ransomware_associated_vulnerability", sig_names)
        self.assertIn("high_exploitation_probability", sig_names)
        self.assertIn("eol_product", sig_names)
        self.assertIn("multiple_vulnerabilities", sig_names)
        self.assertIn("non_standard_exposed_port", sig_names)


if __name__ == "__main__":
    unittest.main()

"""Comprehensive Pytest Test Suite for Aggregator Service."""

import pytest

from src.services.aggregator.aggregator_service import (
    AggregatorService,
    extract_root_domain_match,
    is_dynamic_ip_ptr,
    is_infrastructure_transit_domain,
    is_valid_account_domain,
    normalize_domain,
)


@pytest.fixture
def aggregator_service():
    return AggregatorService()


def test_domain_normalization():
    assert normalize_domain(" EXAMPLE.COM. ") == "example.com"
    assert normalize_domain("sub.domain.org") == "sub.domain.org"
    assert normalize_domain("") == ""
    assert normalize_domain(None) == ""


def test_valid_account_domain():
    assert is_valid_account_domain("example.com") is True
    assert is_valid_account_domain("") is False
    assert is_valid_account_domain("invalid/path") is False
    assert is_valid_account_domain("1.2.3.4.in-addr.arpa") is False
    assert is_valid_account_domain("nodotdomain") is False


def test_dynamic_ip_ptr_detection():
    assert is_dynamic_ip_ptr("107.154.80.208.ip.incapdns.net") is True
    assert is_dynamic_ip_ptr("ec2-54-12-34-56.compute-1.amazonaws.com") is True
    assert is_dynamic_ip_ptr("static-123-45-67-89.t-ipconnect.de") is True
    assert is_dynamic_ip_ptr("vpn.acmecorp.com") is False
    assert is_dynamic_ip_ptr("api.stripe.com") is False
    assert is_dynamic_ip_ptr("") is False


def test_infrastructure_transit_detection():
    assert is_infrastructure_transit_domain("cloudflare.net") is True
    assert is_infrastructure_transit_domain("ec2-54-12-34-56.compute-1.amazonaws.com") is True
    assert is_infrastructure_transit_domain("mycompany.com") is False


def test_extract_root_domain_match():
    matches = extract_root_domain_match("api.acme.corp", ["acme.corp", "other.com"])
    assert "domain:acme.corp" in matches
    assert len(matches) == 1


def test_aggregator_features_and_signals(aggregator_service):
    raw_record = {
        "ip": 3232235777,  # 192.168.1.1
        "port": 8443,
        "domains": ["acme.com"],
        "hostnames": ["portal.acme.com"],
        "product": "Nginx",
        "tags": ["eol-product"],
        "vulns": {
            "CVE-2023-1001": {"cvss": 9.8, "epss": 0.95, "kev": True, "ransomware_campaign": "LockBit"},
        },
    }

    features = aggregator_service.extract_features(raw_record)
    assert features["ip"] == "192.168.1.1"
    assert features["vulnerability_count"] == 1
    assert features["kev_count"] == 1
    assert features["ransomware_count"] == 1
    assert features["max_cvss"] == 9.8

    signals = aggregator_service.detect_signals(features)
    sig_names = [s.name for s in signals]
    assert "kev_vulnerability" in sig_names
    assert "high_severity_vulnerability" in sig_names
    assert "ransomware_associated_vulnerability" in sig_names
    assert "high_exploitation_probability" in sig_names
    assert "eol_product" in sig_names

    # Test resolve_account_keys
    keys = aggregator_service.resolve_account_keys(raw_record)
    assert "domain:acme.com" in keys

    # Test process_record
    account_keys, asset_id, detected_sigs = aggregator_service.process_record(raw_record)
    assert "domain:acme.com" in account_keys
    assert asset_id is not None
    assert len(detected_sigs) >= 1


def test_aggregator_aggregate_records(aggregator_service):
    records = [
        {
            "ip": "10.0.0.1",
            "port": 443,
            "domains": ["company.com"],
            "hostnames": ["vpn.company.com"],
            "product": "Apache",
            "cloud": {"provider": "AWS"},
            "tags": [],
            "vulns": {},
        },
        {
            "ip": "10.0.0.2",
            "port": 80,
            "domains": ["company.com"],
            "hostnames": ["web.company.com"],
            "product": "Nginx",
            "cloud": {"provider": "AWS"},
            "tags": [],
            "vulns": {},
        },
    ]

    accounts = aggregator_service.aggregate(records)
    assert len(accounts) >= 1
    acc = accounts[0]
    assert acc.account_key == "domain:company.com"
    assert len(acc.assets) == 2
    assert "Apache" in acc.products
    assert "Nginx" in acc.products

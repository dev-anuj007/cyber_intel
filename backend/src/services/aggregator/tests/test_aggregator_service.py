"""Comprehensive Pytest Test Suite for Aggregator Service."""

import pytest

from src.services.aggregator.dependencies import (
    create_aggregator_service,
    default_aggregator_service,
    get_aggregator_dependency_context,
)
from src.services.aggregator.internals.builder import AccountBuilder
from src.services.aggregator.internals.constants import TRANSIT_DOMAINS
from src.services.aggregator.internals.domain_utils import (
    extract_root_domain_match,
    is_dynamic_ip_ptr,
    is_infrastructure_transit_domain,
    is_valid_account_domain,
    normalize_domain,
)
from src.services.aggregator.internals.parsers import FeatureExtractor
from src.services.aggregator.internals.repositories.reader import JsonlReader
from src.services.aggregator.internals.resolvers import AccountKeyResolver
from src.services.aggregator.internals.signals import SignalDetector
from src.services.aggregator.types import (
    AddRecordCommand,
    AggregateRecordsQuery,
    LoadAccountsRequest,
    ProcessRecordQuery,
    RecordFeatures,
)


@pytest.fixture
def aggregator_service():
    context = get_aggregator_dependency_context()
    return create_aggregator_service(context=context)


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
    assert (
        is_infrastructure_transit_domain("ec2-54-12-34-56.compute-1.amazonaws.com")
        is True
    )
    assert is_infrastructure_transit_domain("mycompany.com") is False
    assert "cloudflare.net" in TRANSIT_DOMAINS
    assert "amazonaws.com" in TRANSIT_DOMAINS


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
            "CVE-2023-1001": {
                "cvss": 9.8,
                "epss": 0.95,
                "kev": True,
                "ransomware_campaign": "LockBit",
            },
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

    # Test process_record with to_tuple()
    account_keys, asset_id, detected_sigs = aggregator_service.process_record(
        raw_record
    ).to_tuple()
    assert "domain:acme.com" in account_keys
    assert asset_id is not None
    assert len(detected_sigs) >= 1

    # Test process_record with ProcessRecordQuery DTO
    result_dto = aggregator_service.process_record(
        ProcessRecordQuery(record=raw_record)
    )
    assert result_dto.account_keys == ["domain:acme.com"]
    assert result_dto.asset_id == ("192.168.1.1", 8443, "portal.acme.com")
    assert len(result_dto.signals) >= 1


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

    # Test aggregate with AggregateRecordsQuery DTO
    accounts_dto = aggregator_service.aggregate(AggregateRecordsQuery(records=records))
    assert len(accounts_dto) >= 1


def test_feature_extractor_ip_formatting():
    extractor = FeatureExtractor()
    assert extractor.format_ip(3232235777) == "192.168.1.1"
    assert extractor.format_ip("192.168.1.1") == "192.168.1.1"
    assert extractor.format_ip(None) is None


def test_signal_detector_rules():
    detector = SignalDetector()
    signals = detector.detect_signals({"max_cvss": 9.5, "kev_count": 2, "port": 8080})
    names = [s.name for s in signals]
    assert "high_severity_vulnerability" in names
    assert "kev_vulnerability" in names
    assert "non_standard_exposed_port" in names


def test_jsonl_reader(tmp_path):
    reader = JsonlReader()
    file = tmp_path / "test.jsonl"
    file.write_text('{"ip": "1.1.1.1"}\n{"ip": "8.8.8.8"}\n', encoding="utf-8")

    records = reader.read(str(file))
    assert len(records) == 2
    assert records[0]["ip"] == "1.1.1.1"


def test_load_accounts_from_jsonl(tmp_path, aggregator_service):
    file = tmp_path / "stream.jsonl"
    file.write_text(
        '{"ip": "1.1.1.1", "port": 443, "domains": ["stream.com"]}\n',
        encoding="utf-8",
    )

    accounts = aggregator_service.load_accounts_from_jsonl(
        LoadAccountsRequest(jsonl_path=str(file), limit=10)
    )
    assert "domain:stream.com" in accounts


def test_account_key_resolver():
    resolver = AccountKeyResolver()
    keys = resolver.resolve(
        {
            "domains": ["example.com", "cloudflare.net"],
            "hostnames": ["api.example.com"],
        }
    )
    assert keys == ["domain:example.com"]


def test_account_builder_with_command():
    builder = AccountBuilder()
    builder.add_record(
        command=AddRecordCommand(
            account_key="domain:test.com",
            asset_id=("1.2.3.4", 443, "app.test.com"),
            features=RecordFeatures(
                ip="1.2.3.4",
                hostname="app.test.com",
                port=443,
                product="Nginx",
            ),
            signals=[],
        )
    )
    accounts = builder.build()
    assert "domain:test.com" in accounts
    acc = accounts["domain:test.com"]
    assert acc.domains == ["test.com"]
    assert len(acc.assets) == 1
    assert acc.assets[0].ip == "1.2.3.4"
    assert acc.products == ["Nginx"]


def test_lazy_singleton_proxy():
    assert default_aggregator_service is not None
    keys = default_aggregator_service.resolve_account_keys(
        {"domains": ["singleton.org"]}
    )
    assert keys == ["domain:singleton.org"]

"""Comprehensive Pytest Test Suite for Accounts Service, Repositories, and API."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.services.accounts.accounts_service import AccountsService
from src.services.accounts.api import get_accounts_service
from src.services.accounts.repositories.reader import AccountReader
from src.services.accounts.repositories.writer import AccountWriter
from src.services.accounts.types import Account, Asset, SecuritySignal, SignalSeverity
from src.services.database.database_service import DatabaseService


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test_accounts_comp.db")
    db_service = DatabaseService(db_path=db_path)
    db_service.init_database()
    return db_path


@pytest.fixture
def accounts_service(test_db):
    reader = AccountReader()
    writer = AccountWriter()
    return AccountsService(reader=reader, writer=writer, db_path=test_db)


@pytest.fixture
def sample_account():
    return Account(
        account_key="domain:acme.corp",
        domains=["acme.corp", "portal.acme.corp"],
        assets=[
            Asset(ip="10.0.0.1", port=443, hostname="portal.acme.corp"),
            Asset(ip="10.0.0.2", port=22, hostname="ssh.acme.corp"),
        ],
        ips=["10.0.0.1", "10.0.0.2"],
        hostnames=["portal.acme.corp", "ssh.acme.corp"],
        ports=[443, 22],
        products=["Nginx", "OpenSSH"],
        cloud_providers=["AWS", "GCP"],
        signals=[
            SecuritySignal(
                name="kev_vulnerability",
                severity=SignalSeverity.CRITICAL,
                category="vulnerability",
                evidence="CVE-2023-1234",
            ),
            SecuritySignal(
                name="high_severity_vuln",
                severity=SignalSeverity.HIGH,
                category="vulnerability",
                evidence="CVE-2023-5678",
            ),
            SecuritySignal(
                name="exposed_service",
                severity=SignalSeverity.MEDIUM,
                category="network",
                evidence="SSH exposed",
            ),
            SecuritySignal(
                name="info_disclosure",
                severity=SignalSeverity.LOW,
                category="info",
                evidence="Version banner",
            ),
        ],
    )


def test_accounts_crud_and_queries(accounts_service, sample_account, test_db):
    # 1. Save account
    acc_id = accounts_service.save_account(sample_account)
    assert acc_id is not None

    # 2. Get account
    fetched = accounts_service.get_account("domain:acme.corp")
    assert fetched is not None
    assert fetched.account_key == "domain:acme.corp"
    assert "acme.corp" in fetched.domains
    assert fetched.total_signals_count == 4
    assert fetched.critical_signals_count == 1
    assert fetched.high_signals_count == 1
    assert fetched.medium_signals_count == 1
    assert fetched.low_signals_count == 1
    assert len(fetched.assets) == 2
    assert "Nginx" in fetched.products
    assert "AWS" in fetched.cloud_providers

    # 3. Non-existent account
    assert accounts_service.get_account("nonexistent.com") is None

    # 4. Search accounts by domain
    search_results = accounts_service.search_accounts("acme")
    assert len(search_results) >= 1
    assert search_results[0]["account_key"] == "domain:acme.corp"

    # Search with empty results
    assert accounts_service.search_accounts("nonexistent") == []

    # 5. List accounts by tier
    items, total = accounts_service.list_accounts(priority_tier="tier_1_critical")
    assert total >= 1
    assert len(items) >= 1

    # List with critical signals filter
    items_crit, total_crit = accounts_service.list_accounts(has_critical_signals=True)
    assert total_crit >= 1

    # List all accounts
    items_all, total_all = accounts_service.list_accounts()
    assert total_all >= 1

    # 6. Get accounts by signal
    sig_items, sig_total = accounts_service.get_accounts_by_signal("kev_vulnerability")
    assert sig_total >= 1
    assert len(sig_items) >= 1

    # 7. Summary stats
    stats = accounts_service.get_summary_stats(force_refresh=True)
    assert stats["total_accounts"] >= 1
    assert stats["critical_count"] >= 1
    # Cached summary stats
    stats_cached = accounts_service.get_summary_stats(force_refresh=False)
    assert stats_cached["total_accounts"] == stats["total_accounts"]

    # 8. Delete account
    assert accounts_service.delete_account("domain:acme.corp") is True
    assert accounts_service.get_account("domain:acme.corp") is None


def test_reader_writer_methods(test_db, sample_account):
    reader = AccountReader()
    writer = AccountWriter()
    db_svc = DatabaseService(db_path=test_db)
    with db_svc.get_connection() as conn:
        # Insert
        acc_id = writer.insert_account(conn, sample_account, "tier_1_critical")
        assert acc_id is not None

        # Update priority tier
        writer.update_priority_tier(conn, "domain:acme.corp", "tier_2_high")

        # Load batch dict
        batch_dict = reader.load_accounts_batch(conn, ["domain:acme.corp"], as_dict=True)
        assert len(batch_dict) == 1
        assert batch_dict[0]["account_key"] == "domain:acme.corp"

        # Load batch object
        batch_obj = reader.load_accounts_batch(conn, ["domain:acme.corp"], as_dict=False)
        assert len(batch_obj) == 1
        assert batch_obj[0].account_key == "domain:acme.corp"

        # Load empty batch
        assert reader.load_accounts_batch(conn, []) == []
        assert reader.load_accounts_summary_batch(conn, []) == []

        # Tiers testing
        for tier in ["tier_1_critical", "tier_2_high", "tier_3_medium", "tier_4_low", "invalid_tier"]:
            keys, cnt = reader.get_accounts_by_priority_tier(conn, tier)
            assert isinstance(keys, list)

        # Critical signals
        crit_keys, crit_cnt = reader.get_accounts_with_critical_signals(conn)
        assert isinstance(crit_keys, list)

        # Delete
        writer.delete_account(conn, "domain:acme.corp")


def test_accounts_api_endpoints(test_db, sample_account):
    service = AccountsService(reader=AccountReader(), writer=AccountWriter(), db_path=test_db)
    service.save_account(sample_account)

    from fastapi import FastAPI

    from src.services.accounts.api import router

    api_app = FastAPI()
    api_app.include_router(router)

    api_app.dependency_overrides[get_accounts_service] = lambda: service
    client = TestClient(api_app)

    # Health
    r = client.get("/api/accounts/health")
    if r.status_code == 404:
        r = client.get("/api/accounts")
    assert r.status_code == 200

    # List
    r = client.get("/api/accounts")
    assert r.status_code == 200
    assert "items" in r.json()

    # Summary stats
    r = client.get("/api/accounts/summary")
    assert r.status_code == 200

    # Get single
    r = client.get("/api/accounts/domain:acme.corp")
    assert r.status_code == 200
    assert r.json()["account_key"] == "domain:acme.corp"

    # Get non-existent
    r = client.get("/api/accounts/nonexistent")
    assert r.status_code == 404

    # Search domain
    r = client.get("/api/accounts/search/domain?q=acme")
    assert r.status_code == 200

    # By signal
    r = client.get("/api/accounts/signal/kev_vulnerability")
    assert r.status_code == 200

    # Delete
    r = client.delete("/api/accounts/domain:acme.corp")
    assert r.status_code == 200

    api_app.dependency_overrides.clear()


def test_account_multi_version_sync_and_resolution(test_db):
    service = AccountsService(reader=AccountReader(), writer=AccountWriter(), db_path=test_db)

    # 1. Insert v1
    v1_account = Account(
        account_key="domain:testcorp.com",
        version="v1",
        domain="testcorp.com",
        domains=["testcorp.com"],
        signals=[
            SecuritySignal(
                name="open_port_22", severity=SignalSeverity.MEDIUM, category="network", evidence="Port 22 open"
            )
        ],
        ports=[22],
    )
    service.save_account(v1_account)

    # 2. Insert v2 (re-crawl with more findings)
    v2_account = Account(
        account_key="domain:testcorp.com:v2",
        version="v2",
        domain="testcorp.com",
        domains=["testcorp.com"],
        signals=[
            SecuritySignal(
                name="open_port_22", severity=SignalSeverity.MEDIUM, category="network", evidence="Port 22 open"
            ),
            SecuritySignal(
                name="critical_cve",
                severity=SignalSeverity.CRITICAL,
                category="vulnerability",
                evidence="CVE-2024-1234",
            ),
        ],
        ports=[22, 443],
    )
    service.save_account(v2_account)

    # 3. Test get_account_versions
    versions = service.get_account_versions("testcorp.com")
    assert len(versions) == 2
    assert versions[0].version == "v2"
    assert versions[1].version == "v1"

    # 4. Default query without version should return latest snapshot (v2)
    latest_acc = service.get_account("domain:testcorp.com")
    assert latest_acc is not None
    assert latest_acc.version == "v2"
    assert len(latest_acc.signals) == 2
    assert len(latest_acc.available_versions) == 2

    # 5. Query specifically for v1
    v1_loaded = service.get_account("testcorp.com", version="v1")
    assert v1_loaded is not None
    assert v1_loaded.version == "v1"
    assert len(v1_loaded.signals) == 1

    # 6. Score v2 and verify listing reflects score for the domain
    from datetime import datetime

    from src.services.scorer.repositories.writer import ScoreWriter
    from src.services.scorer.types import AccountScore, PriorityTier

    score_writer = ScoreWriter()
    with DatabaseService(db_path=test_db).get_connection() as conn:
        score_writer.save_score(
            conn,
            AccountScore(
                account_key="domain:testcorp.com:v2",
                account=v2_account,
                score=92,
                priority_tier=PriorityTier.TIER_1_CRITICAL,
                score_rationale="Critical vulnerability detected in v2",
                key_risks=["CVE-2024-1234"],
                model_version="gemini-3.1-flash-lite",
                timestamp=datetime.now(),
            ),
        )

    # Verify score resolved on domain query
    resolved_acc = service.get_account("testcorp.com")
    assert resolved_acc is not None
    assert resolved_acc.ai_score == 92

    # Verify summary batch contains AI score
    with DatabaseService(db_path=test_db).get_connection() as conn:
        summaries = service.reader.load_accounts_summary_batch(conn, ["domain:testcorp.com"])
        assert len(summaries) == 1
        assert summaries[0]["ai_score"] == 92

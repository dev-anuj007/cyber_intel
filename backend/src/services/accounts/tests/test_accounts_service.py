from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from src.services.accounts.accounts_service import AccountsService
from src.services.accounts.dependencies import (
    AccountsServiceDependencyContext,
    create_accounts_service,
    default_accounts_service,
    get_accounts_dependency_context,
    get_accounts_service,
)
from src.services.accounts.internals.repositories.reader import AccountReader
from src.services.accounts.internals.repositories.writer import AccountWriter
from src.services.accounts.types import (
    Account,
    AccountsBatchQuery,
    AccountsBySignalQuery,
    Asset,
    InsertAccountCommand,
    ListAccountsQuery,
    PriorityTier,
    SecuritySignal,
    SignalSeverity,
)
from src.services.database.database_service import DatabaseService
from src.services.scorer.internals.repositories.writer import ScoreWriter
from src.services.scorer.types import AccountScore, PriorityTier as ScorerPriorityTier


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test_accounts_comp.db")
    db_service = DatabaseService(db_path=db_path)
    db_service.init_database()
    return db_path


@pytest.fixture
def accounts_service(test_db):
    return create_accounts_service(db_path=test_db)


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
    save_res = accounts_service.save_account(sample_account)
    assert save_res.account_id is not None
    assert save_res.account_key == "domain:acme.corp"

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
    assert search_results.total >= 1
    assert len(search_results.results) >= 1
    assert search_results.results[0]["account_key"] == "domain:acme.corp"

    # Search with empty results
    assert accounts_service.search_accounts("nonexistent").results == []

    # 5. List accounts by tier
    res_tier = accounts_service.list_accounts(
        ListAccountsQuery(priority_tier="tier_1_critical")
    )
    assert res_tier.total >= 1
    assert len(res_tier.items) >= 1

    # List with critical signals filter
    res_crit = accounts_service.list_accounts(
        ListAccountsQuery(has_critical_signals=True)
    )
    assert res_crit.total >= 1

    # List all accounts
    res_all = accounts_service.list_accounts()
    assert res_all.total >= 1

    # 6. Get accounts by signal
    sig_res = accounts_service.get_accounts_by_signal(
        AccountsBySignalQuery(signal_name="kev_vulnerability")
    )
    assert sig_res.total >= 1
    assert len(sig_res.items) >= 1

    # 7. Summary stats
    stats = accounts_service.get_summary_stats()
    assert stats.total_accounts >= 1
    assert stats.critical_count >= 1

    # 8. Delete account
    del_res = accounts_service.delete_account("domain:acme.corp")
    assert del_res.success is True
    assert del_res.account_key == "domain:acme.corp"
    assert accounts_service.get_account("domain:acme.corp") is None


def test_reader_writer_methods(test_db, sample_account):
    reader = AccountReader()
    writer = AccountWriter()
    db_svc = DatabaseService(db_path=test_db)
    with db_svc.get_connection() as conn:
        # Insert
        acc_id = writer.insert_account(conn, sample_account, "tier_1_critical")
        assert acc_id is not None

        # Load batch dict
        batch_dict = reader.load_accounts_batch(
            conn, ["domain:acme.corp"], as_dict=True
        )
        assert len(batch_dict) == 1
        assert batch_dict[0]["account_key"] == "domain:acme.corp"

        # Load batch object
        batch_obj = reader.load_accounts_batch(
            conn, ["domain:acme.corp"], as_dict=False
        )
        assert len(batch_obj) == 1
        assert batch_obj[0].account_key == "domain:acme.corp"

        # Load empty batch
        assert reader.load_accounts_batch(conn, []) == []
        assert reader.load_accounts_summary_batch(conn, []) == []

        # Tiers testing
        for tier in [
            "tier_1_critical",
            "tier_2_high",
            "tier_3_medium",
            "tier_4_low",
            "invalid_tier",
        ]:
            keys, cnt = reader.get_accounts_by_priority_tier(conn, tier)
            assert isinstance(keys, list)

        # Critical signals
        crit_keys, crit_cnt = reader.get_accounts_with_critical_signals(conn)
        assert isinstance(crit_keys, list)

        # Delete
        assert writer.delete_account(conn, "domain:acme.corp") is True
        assert writer.delete_account(conn, "nonexistent.corp") is False


def test_accounts_api_endpoints(test_db, sample_account):
    service = create_accounts_service(db_path=test_db)
    service.save_account(sample_account)

    from fastapi import FastAPI

    from src.services.accounts.api import router

    api_app = FastAPI()
    api_app.include_router(router)

    api_app.dependency_overrides[get_accounts_service] = lambda: service
    client = TestClient(api_app)

    # Health
    r = client.get("/api/accounts/health")
    assert r.status_code == 200
    assert r.json()["service"] == "accounts"

    # List
    r = client.get("/api/accounts")
    assert r.status_code == 200
    assert "items" in r.json()

    # Summary stats
    r = client.get("/api/accounts/summary")
    assert r.status_code == 200
    assert r.json()["total_accounts"] >= 1

    # Get single
    r = client.get("/api/accounts/domain:acme.corp")
    assert r.status_code == 200
    assert r.json()["account_key"] == "domain:acme.corp"

    # Get non-existent
    r = client.get("/api/accounts/nonexistent")
    assert r.status_code == 404

    # Search domain
    r = client.get("/api/accounts/search?q=acme")
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    # By signal
    r = client.get("/api/accounts/signal/kev_vulnerability")
    assert r.status_code == 200
    assert r.json()["total"] >= 1

    # Versions
    r = client.get("/api/accounts/domain:acme.corp/versions")
    assert r.status_code == 200
    assert "versions" in r.json()

    # Score history
    r = client.get("/api/accounts/domain:acme.corp/score-history")
    assert r.status_code == 200
    assert "history" in r.json()

    # Delete
    r = client.delete("/api/accounts/domain:acme.corp")
    assert r.status_code == 200

    api_app.dependency_overrides.clear()


def test_account_multi_version_sync_and_resolution(test_db):
    service = create_accounts_service(db_path=test_db)

    # 1. Insert v1
    v1_account = Account(
        account_key="domain:testcorp.com",
        version="v1",
        domain="testcorp.com",
        domains=["testcorp.com"],
        signals=[
            SecuritySignal(
                name="open_port_22",
                severity=SignalSeverity.MEDIUM,
                category="network",
                evidence="Port 22 open",
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
                name="open_port_22",
                severity=SignalSeverity.MEDIUM,
                category="network",
                evidence="Port 22 open",
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
    versions_res = service.get_account_versions("testcorp.com")
    assert versions_res.total_versions == 2
    assert len(versions_res.versions) == 2
    assert versions_res.versions[0].version == "v2"
    assert versions_res.versions[1].version == "v1"

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
    score_writer = ScoreWriter()
    with DatabaseService(db_path=test_db).get_connection() as conn:
        score_writer.save_score(
            conn,
            AccountScore(
                account_key="domain:testcorp.com:v2",
                account=v2_account,
                score=92,
                priority_tier=ScorerPriorityTier.TIER_1_CRITICAL,
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
    reader = AccountReader()
    with DatabaseService(db_path=test_db).get_connection() as conn:
        summaries = reader.load_accounts_summary_batch(conn, ["domain:testcorp.com"])
        assert len(summaries) == 1
        assert summaries[0]["ai_score"] == 92


def test_priority_tier_computation(accounts_service):
    # Tier 1 Critical: Any critical signal
    acc_crit = Account(
        account_key="test:crit",
        signals=[
            SecuritySignal(
                name="cve",
                severity=SignalSeverity.CRITICAL,
                category="vuln",
                evidence="crit",
            ),
        ],
    )
    assert (
        accounts_service.compute_priority_tier(acc_crit) == PriorityTier.TIER_1_CRITICAL
    )

    # Tier 2 High: High severity and >= 2 signals
    acc_high_multi = Account(
        account_key="test:high_multi",
        signals=[
            SecuritySignal(
                name="h1", severity=SignalSeverity.HIGH, category="vuln", evidence="e1"
            ),
            SecuritySignal(
                name="m1",
                severity=SignalSeverity.MEDIUM,
                category="vuln",
                evidence="e2",
            ),
        ],
    )
    assert (
        accounts_service.compute_priority_tier(acc_high_multi)
        == PriorityTier.TIER_2_HIGH
    )

    # Tier 3 Medium: High severity but only 1 signal
    acc_high_single = Account(
        account_key="test:high_single",
        signals=[
            SecuritySignal(
                name="h1", severity=SignalSeverity.HIGH, category="vuln", evidence="e1"
            ),
        ],
    )
    assert (
        accounts_service.compute_priority_tier(acc_high_single)
        == PriorityTier.TIER_3_MEDIUM
    )

    # Tier 3 Medium: Medium or low signals (> 0 signals)
    acc_med = Account(
        account_key="test:med",
        signals=[
            SecuritySignal(
                name="m1",
                severity=SignalSeverity.MEDIUM,
                category="vuln",
                evidence="e1",
            ),
        ],
    )
    assert accounts_service.compute_priority_tier(acc_med) == PriorityTier.TIER_3_MEDIUM

    # Tier 4 Low: No signals
    acc_empty = Account(account_key="test:empty", signals=[])
    assert accounts_service.compute_priority_tier(acc_empty) == PriorityTier.TIER_4_LOW


def test_command_and_query_objects(accounts_service, sample_account):
    # Insert via InsertAccountCommand
    cmd = InsertAccountCommand(account=sample_account, priority_tier="tier_2_high")
    save_res = accounts_service.save_account(cmd)
    assert save_res.account_id is not None
    assert save_res.priority_tier == "tier_2_high"

    # Batch Query via AccountsBatchQuery
    batch_q = AccountsBatchQuery(account_keys=["domain:acme.corp"], as_dict=True)
    batch_res = accounts_service.get_accounts_batch(batch_q)
    assert len(batch_res) == 1
    assert isinstance(batch_res[0], dict)

    # List Query via ListAccountsQuery
    list_q = ListAccountsQuery(skip=0, limit=10, priority_tier="tier_2_high")
    list_res = accounts_service.list_accounts(list_q)
    assert list_res.total >= 1
    assert len(list_res.items) >= 1


def test_clear_all(accounts_service, sample_account):
    accounts_service.save_account(sample_account)
    stats_before = accounts_service.get_summary_stats()
    assert stats_before.total_accounts >= 1

    # Clear all
    clear_res = accounts_service.clear_all()
    assert clear_res.success is True
    stats_after = accounts_service.get_summary_stats()
    assert stats_after.total_accounts == 0


def test_dependency_injection_context(test_db):
    ctx = get_accounts_dependency_context(db_path=test_db)
    assert isinstance(ctx, AccountsServiceDependencyContext)
    assert ctx.reader is not None
    assert ctx.writer is not None

    svc = create_accounts_service(context=ctx)
    assert isinstance(svc, AccountsService)

    # Test default proxy
    assert hasattr(default_accounts_service, "get_account")


def test_empty_search_and_edge_cases(accounts_service):
    assert accounts_service.search_accounts("").results == []
    assert accounts_service.search_accounts("   ").results == []
    assert accounts_service.get_account("") is None
    assert accounts_service.get_account_versions("").versions == []


def test_lambda_handler_health():
    from src.services.accounts.lambda_handler import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "accounts-microservice"


def test_empty_accounts_summary_endpoint(test_db):
    service = create_accounts_service(db_path=test_db)
    service.clear_all()

    from fastapi import FastAPI

    from src.services.accounts.api import router

    api_app = FastAPI()
    api_app.include_router(router)
    api_app.dependency_overrides[get_accounts_service] = lambda: service
    client = TestClient(api_app)

    # Empty summary should return 503 external service error
    r = client.get("/api/accounts/summary")
    assert r.status_code == 503
    api_app.dependency_overrides.clear()

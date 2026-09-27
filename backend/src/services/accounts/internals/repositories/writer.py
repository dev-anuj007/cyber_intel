from typing import Any, Optional, Set, Tuple

from sqlmodel import Session, col, delete, select

from src.services.accounts.internals.repositories.models.account import AccountTable
from src.services.accounts.internals.repositories.models.asset import AssetTable
from src.services.accounts.internals.repositories.models.cloud_provider import (
    CloudProviderTable,
)
from src.services.accounts.internals.repositories.models.domain import DomainTable
from src.services.accounts.internals.repositories.models.hostname import HostnameTable
from src.services.accounts.internals.repositories.models.ip import IpTable
from src.services.accounts.internals.repositories.models.port import PortTable
from src.services.accounts.internals.repositories.models.product import ProductTable
from src.services.accounts.internals.repositories.models.signal import SignalTable
from src.services.accounts.protocols import IAccountWriter
from src.services.accounts.types import Account
from src.services.database.dependencies import get_db_session


def _get_session(conn: Any) -> Session:
    return get_db_session(conn=conn)


class AccountWriter(IAccountWriter):
    def _clear_entities_in_session(self, session: Session, account_id: int) -> None:
        session.exec(
            delete(SignalTable).where(col(SignalTable.account_id) == account_id)
        )
        session.exec(
            delete(CloudProviderTable).where(
                col(CloudProviderTable.account_id) == account_id
            )
        )
        session.exec(
            delete(ProductTable).where(col(ProductTable.account_id) == account_id)
        )
        session.exec(delete(PortTable).where(col(PortTable.account_id) == account_id))
        session.exec(
            delete(HostnameTable).where(col(HostnameTable.account_id) == account_id)
        )
        session.exec(delete(IpTable).where(col(IpTable.account_id) == account_id))
        session.exec(delete(AssetTable).where(col(AssetTable.account_id) == account_id))
        session.exec(
            delete(DomainTable).where(col(DomainTable.account_id) == account_id)
        )

    def _upsert_account_record(
        self, session: Session, account: Account, priority_tier: str
    ) -> int:
        signal_count = len(account.signals)
        acc = session.exec(
            select(AccountTable).where(
                col(AccountTable.account_key) == account.account_key
            )
        ).first()
        if acc:
            acc.signal_count = signal_count
            acc.priority_tier = priority_tier
            session.add(acc)
            session.flush()
            session.refresh(acc)
        else:
            acc = AccountTable(
                account_key=account.account_key,
                signal_count=signal_count,
                priority_tier=priority_tier,
            )
            session.add(acc)
            session.flush()
            session.refresh(acc)

        if acc.id is None:
            raise ValueError("Failed to obtain generated account ID")
        return acc.id

    def _insert_account_child_entities(
        self, session: Session, account_id: int, account: Account
    ) -> None:
        if account.domains:
            for d in dict.fromkeys(account.domains):
                session.add(DomainTable(account_id=account_id, domain=d))

        if account.assets:
            seen_assets: Set[Tuple[Optional[str], Optional[int], Optional[str]]] = set()
            for a in account.assets:
                tup = (a.ip, a.port, a.hostname)
                if tup not in seen_assets:
                    seen_assets.add(tup)
                    session.add(
                        AssetTable(
                            account_id=account_id,
                            ip=a.ip,
                            port=a.port,
                            hostname=a.hostname,
                        )
                    )

        if account.ips:
            for ip in dict.fromkeys(account.ips):
                session.add(IpTable(account_id=account_id, ip=ip))

        if account.hostnames:
            for h in dict.fromkeys(account.hostnames):
                session.add(HostnameTable(account_id=account_id, hostname=h))

        if account.ports:
            for p in sorted(set(account.ports)):
                session.add(PortTable(account_id=account_id, port=p))

        if account.products:
            for prod in dict.fromkeys(account.products):
                session.add(ProductTable(account_id=account_id, product=prod))

        if account.cloud_providers:
            for prov in dict.fromkeys(account.cloud_providers):
                session.add(CloudProviderTable(account_id=account_id, provider=prov))

        if account.signals:
            seen_signals: Set[Tuple[str, str, str, str]] = set()
            for s in account.signals:
                s_sev = (
                    s.severity.value
                    if hasattr(s.severity, "value")
                    else str(s.severity)
                )
                tup = (s.name, s_sev, getattr(s, "category", ""), s.evidence)
                if tup not in seen_signals:
                    seen_signals.add(tup)
                    session.add(
                        SignalTable(
                            account_id=account_id,
                            name=s.name,
                            severity=s_sev,
                            category=getattr(s, "category", ""),
                            evidence=s.evidence,
                        )
                    )

    def insert_account(self, conn: Any, account: Account, priority_tier: str) -> int:
        with _get_session(conn) as session:
            account_id = self._upsert_account_record(session, account, priority_tier)
            self._clear_entities_in_session(session, account_id)
            self._insert_account_child_entities(session, account_id, account)
            session.commit()
            return account_id

    def clear_account_entities_by_id(self, conn: Any, account_id: int) -> None:
        with _get_session(conn) as session:
            self._clear_entities_in_session(session, account_id)
            session.commit()

    def update_priority_tier(self, conn: Any, account_key: str, tier: str) -> bool:
        with _get_session(conn) as session:
            acc = session.exec(
                select(AccountTable).where(
                    (col(AccountTable.account_key) == account_key)
                    | (
                        col(AccountTable.account_key)
                        == account_key.replace("domain:", "")
                    )
                    | (col(AccountTable.account_key) == f"domain:{account_key}")
                )
            ).first()
            if acc:
                acc.priority_tier = tier
                session.add(acc)
                session.commit()
                return True
            return False

    def delete_account(self, conn: Any, account_key: str) -> bool:
        with _get_session(conn) as session:
            acc = session.exec(
                select(AccountTable).where(
                    (col(AccountTable.account_key) == account_key)
                    | (
                        col(AccountTable.account_key)
                        == account_key.replace("domain:", "")
                    )
                    | (col(AccountTable.account_key) == f"domain:{account_key}")
                )
            ).first()
            if acc:
                if acc.id is not None:
                    self._clear_entities_in_session(session, acc.id)
                    session.exec(
                        delete(AccountTable).where(col(AccountTable.id) == acc.id)
                    )
                session.commit()
                return True
            return False

    def clear_accounts(self, conn: Any) -> None:
        with _get_session(conn) as session:
            session.exec(delete(SignalTable))
            session.exec(delete(CloudProviderTable))
            session.exec(delete(ProductTable))
            session.exec(delete(PortTable))
            session.exec(delete(HostnameTable))
            session.exec(delete(IpTable))
            session.exec(delete(AssetTable))
            session.exec(delete(DomainTable))
            session.exec(delete(AccountTable))
            session.commit()

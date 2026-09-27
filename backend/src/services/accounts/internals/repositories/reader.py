import json
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, func, or_, select

from src.services.accounts.internals.repositories.models.account import AccountTable
from src.services.accounts.internals.repositories.models.ai_score import AIScoreTable
from src.services.accounts.internals.repositories.models.domain import DomainTable
from src.services.accounts.internals.repositories.models.signal import SignalTable
from src.services.accounts.protocols import IAccountReader
from src.services.accounts.types import (
    Account,
    AccountVersionSummary,
    Asset,
    SecuritySignal,
    SignalSeverity,
)
from src.services.database.dependencies import get_db_session


def _to_signal_severity(severity: str) -> SignalSeverity:
    try:
        return SignalSeverity(severity.lower())
    except Exception:
        return SignalSeverity.LOW


def _get_ph(cursor: Any, items_or_count: Union[int, List[Any], Set[Any]]) -> str:
    count = items_or_count if isinstance(items_or_count, int) else len(items_or_count)
    if count == 0:
        return ""
    is_psycopg = (
        hasattr(cursor, "pgresult")
        or hasattr(cursor, "_query")
        or type(cursor).__module__.startswith("psycopg")
    )
    ph = "%s" if is_psycopg else "?"
    return ",".join(ph for _ in range(count))


def _extract_raw_conn(conn: Any) -> Any:
    if hasattr(conn, "_conn"):
        return conn._conn
    if hasattr(conn, "raw_connection"):
        return conn.raw_connection
    return conn


def _get_session(conn: Any) -> Session:
    return get_db_session(conn=conn)


def _extract_base_domain(account_key: str) -> str:
    clean = (account_key or "").strip()
    if clean.startswith("domain:"):
        clean = clean[7:]
    parts = clean.split(":")
    return parts[0].strip().lower()


def _extract_version_tag(account_key: str) -> str:
    if account_key and account_key.count(":") >= 2:
        parts = account_key.split(":")
        if parts[-1].startswith("v") and parts[-1][1:].isdigit():
            return parts[-1]
    return "v1"


class AccountReader(IAccountReader):
    def _query_version_rows(self, cursor: Any, base_dom: str) -> List[Tuple[Any, ...]]:
        cand_keys = [f"domain:{base_dom}", base_dom]
        for i in range(1, 15):
            cand_keys.extend([f"domain:{base_dom}:v{i}", f"{base_dom}:v{i}"])
        placeholders = _get_ph(cursor, cand_keys)
        return cursor.execute(
            f"""
            SELECT id, account_key, priority_tier, signal_count
            FROM accounts
            WHERE account_key IN ({placeholders})
            ORDER BY id ASC
            """,
            cand_keys,
        ).fetchall()

    def _fetch_version_batch_counts(
        self, cursor: Any, acc_ids: List[int]
    ) -> Tuple[Dict[int, int], Dict[int, int]]:
        id_placeholders = _get_ph(cursor, acc_ids)
        assets_map: Dict[int, int] = {}
        for acc_id, cnt in cursor.execute(
            f"SELECT account_id, count(*) FROM assets WHERE account_id IN ({id_placeholders}) GROUP BY account_id",
            acc_ids,
        ).fetchall():
            assets_map[acc_id] = cnt

        signals_map: Dict[int, int] = {}
        for acc_id, cnt in cursor.execute(
            f"SELECT account_id, count(*) FROM signals WHERE account_id IN ({id_placeholders}) GROUP BY account_id",
            acc_ids,
        ).fetchall():
            signals_map[acc_id] = cnt

        return assets_map, signals_map

    def _fetch_version_scores_map(
        self, cursor: Any, acc_keys: List[str]
    ) -> Dict[str, int]:
        scores_map: Dict[str, int] = {}
        key_placeholders = _get_ph(cursor, acc_keys)
        try:
            for a_key, sc in cursor.execute(
                f"SELECT account_key, score FROM ai_scores WHERE account_key IN ({key_placeholders}) AND is_latest=1",
                acc_keys,
            ).fetchall():
                scores_map[a_key] = sc
        except Exception:
            pass
        return scores_map

    def _build_sorted_version_summaries(
        self,
        rows: List[Tuple[Any, ...]],
        base_dom: str,
        assets_map: Dict[int, int],
        signals_map: Dict[int, int],
        scores_map: Dict[str, int],
    ) -> List[AccountVersionSummary]:
        versions: List[AccountVersionSummary] = []
        for acc_id, a_key, p_tier, s_cnt in rows:
            v_tag = _extract_version_tag(a_key)
            a_cnt = assets_map.get(acc_id, 0)
            sig_cnt = signals_map.get(acc_id, s_cnt or 0)
            ai_sc = scores_map.get(a_key)
            if ai_sc is None:
                ai_sc = scores_map.get(f"domain:{base_dom}") or scores_map.get(base_dom)

            versions.append(
                AccountVersionSummary(
                    version=v_tag,
                    account_key=a_key,
                    priority_tier=p_tier,
                    signals_count=sig_cnt,
                    assets_count=a_cnt,
                    ai_score=ai_sc,
                    is_active=False,
                )
            )

        def _ver_num(v: AccountVersionSummary) -> int:
            val = v.version.lstrip("v")
            return int(val) if val.isdigit() else 1

        versions.sort(key=_ver_num, reverse=True)
        return versions

    def get_account_versions(
        self, conn: Any, account_key: str
    ) -> List[AccountVersionSummary]:
        base_dom = _extract_base_domain(account_key)
        if not base_dom:
            return []

        raw = _extract_raw_conn(conn)
        cursor = raw.cursor()
        try:
            rows = self._query_version_rows(cursor, base_dom)
            if not rows:
                return []

            acc_ids = [r[0] for r in rows]
            acc_keys = [r[1] for r in rows]

            assets_map, signals_map = self._fetch_version_batch_counts(cursor, acc_ids)
            scores_map = self._fetch_version_scores_map(cursor, acc_keys)

            return self._build_sorted_version_summaries(
                rows, base_dom, assets_map, signals_map, scores_map
            )
        finally:
            try:
                cursor.close()
            except Exception:
                pass

    def _resolve_target_account_key(
        self,
        account_key: str,
        version: Optional[str],
        all_versions: List[AccountVersionSummary],
    ) -> str:
        base_dom = _extract_base_domain(account_key)
        if version:
            for v_sum in all_versions:
                if v_sum.version.lower() == version.lower():
                    return v_sum.account_key
            if version.lower() == "v1":
                return f"domain:{base_dom}"
            return f"domain:{base_dom}:{version}"

        if account_key.count(":") >= 2:
            return account_key
        elif all_versions:
            return all_versions[0].account_key
        return (
            f"domain:{base_dom}"
            if not account_key.startswith("domain:")
            else account_key
        )

    def _fetch_account_record(
        self, session: Session, target_key: str
    ) -> Optional[AccountTable]:
        statement = (
            select(AccountTable)
            .where(
                or_(
                    AccountTable.account_key == target_key,
                    AccountTable.account_key == target_key.replace("domain:", ""),
                    AccountTable.account_key == f"domain:{target_key}",
                )
            )
            .options(
                selectinload(AccountTable.domains),  # type: ignore
                selectinload(AccountTable.assets),  # type: ignore
                selectinload(AccountTable.ips),  # type: ignore
                selectinload(AccountTable.hostnames),  # type: ignore
                selectinload(AccountTable.ports),  # type: ignore
                selectinload(AccountTable.products),  # type: ignore
                selectinload(AccountTable.cloud_providers),  # type: ignore
                selectinload(AccountTable.signals),  # type: ignore
            )
            .order_by(col(AccountTable.id).desc())
            .limit(1)
        )
        return session.exec(statement).first()

    def _fetch_latest_score_for_account(
        self, session: Session, canonical_key: str, base_dom: str, active_version: str
    ) -> Optional[AIScoreTable]:
        candidate_score_keys = [
            canonical_key,
            f"domain:{base_dom}:{active_version}",
            f"{base_dom}:{active_version}",
        ]
        if active_version == "v1":
            candidate_score_keys.extend([f"domain:{base_dom}", base_dom])

        try:
            score_stmt = (
                select(AIScoreTable)
                .where(
                    col(AIScoreTable.account_key).in_(candidate_score_keys),
                    AIScoreTable.is_latest == 1,
                )
                .order_by(col(AIScoreTable.version).desc(), col(AIScoreTable.id).desc())
                .limit(1)
            )
            score_row = session.exec(score_stmt).first()
            if not score_row:
                score_stmt_fallback = (
                    select(AIScoreTable)
                    .where(col(AIScoreTable.account_key).in_(candidate_score_keys))
                    .order_by(
                        col(AIScoreTable.version).desc(), col(AIScoreTable.id).desc()
                    )
                    .limit(1)
                )
                score_row = session.exec(score_stmt_fallback).first()
            if not score_row:
                score_stmt_dom = (
                    select(AIScoreTable)
                    .where(
                        col(AIScoreTable.account_key).in_(
                            [f"domain:{base_dom}", base_dom]
                        )
                    )
                    .order_by(
                        col(AIScoreTable.version).desc(), col(AIScoreTable.id).desc()
                    )
                    .limit(1)
                )
                score_row = session.exec(score_stmt_dom).first()
            return score_row
        except Exception:
            return None

    def _format_score_detail(
        self, score_row: Optional[AIScoreTable]
    ) -> Tuple[Optional[int], Optional[Dict[str, Any]]]:
        if not score_row:
            return None, None

        ai_score = score_row.score
        try:
            risks = (
                json.loads(score_row.key_risks)
                if isinstance(score_row.key_risks, str)
                else score_row.key_risks
            )
        except Exception:
            risks = [score_row.key_risks] if score_row.key_risks else []

        try:
            tokens = (
                json.loads(score_row.tokens_used)
                if isinstance(score_row.tokens_used, str)
                else score_row.tokens_used
            )
        except Exception:
            tokens = {}

        latest_score = {
            "id": score_row.id,
            "account_key": score_row.account_key,
            "version": score_row.version,
            "score": score_row.score,
            "priority_tier": score_row.priority_tier,
            "key_risks": risks,
            "suggested_outreach": score_row.suggested_outreach,
            "score_rationale": score_row.score_rationale,
            "model_version": score_row.model_version,
            "model_name": score_row.model_name,
            "tokens_used": tokens,
            "latency_ms": score_row.latency_ms,
            "cost_usd": score_row.cost_usd,
            "timestamp": score_row.scored_at,
        }
        return ai_score, latest_score

    def _build_account_from_record(
        self,
        acc_record: AccountTable,
        all_versions: List[AccountVersionSummary],
        score_row: Optional[AIScoreTable],
    ) -> Account:
        canonical_key = acc_record.account_key
        base_dom = _extract_base_domain(canonical_key)
        priority_tier = acc_record.priority_tier
        domains = [d.domain for d in acc_record.domains]
        assets = [
            Asset(ip=a.ip, port=a.port, hostname=a.hostname) for a in acc_record.assets
        ]
        ips = [i.ip for i in acc_record.ips]
        hostnames = [h.hostname for h in acc_record.hostnames]
        ports = [p.port for p in acc_record.ports]
        products = [pr.product for pr in acc_record.products]
        cloud_providers = [cp.provider for cp in acc_record.cloud_providers]
        signals = [
            SecuritySignal(
                name=s.name,
                severity=_to_signal_severity(s.severity),
                category=s.category,
                evidence=s.evidence,
            )
            for s in acc_record.signals
        ]

        active_version = _extract_version_tag(canonical_key)
        ai_score, latest_score = self._format_score_detail(score_row)
        primary_domain = domains[0] if domains else base_dom

        for v_s in all_versions:
            if v_s.version == active_version:
                v_s.is_active = True

        return Account(
            account_key=canonical_key,
            version=active_version,
            domain=primary_domain,
            domains=domains,
            priority_tier=priority_tier,
            critical_signals_count=len(
                [
                    s
                    for s in signals
                    if getattr(s.severity, "value", str(s.severity)).lower()
                    == "critical"
                ]
            ),
            high_signals_count=len(
                [
                    s
                    for s in signals
                    if getattr(s.severity, "value", str(s.severity)).lower() == "high"
                ]
            ),
            medium_signals_count=len(
                [
                    s
                    for s in signals
                    if getattr(s.severity, "value", str(s.severity)).lower() == "medium"
                ]
            ),
            low_signals_count=len(
                [
                    s
                    for s in signals
                    if getattr(s.severity, "value", str(s.severity)).lower() == "low"
                ]
            ),
            total_signals_count=len(signals),
            total_assets=len(assets),
            total_subdomains=len(hostnames),
            assets=assets,
            ips=ips,
            hostnames=hostnames,
            ports=ports,
            products=products,
            cloud_providers=cloud_providers,
            signals=signals,
            ai_score=ai_score,
            latest_score=latest_score,
            available_versions=all_versions,
        )

    def load_account(
        self, conn: Any, account_key: str, version: Optional[str] = None
    ) -> Optional[Account]:
        base_dom = _extract_base_domain(account_key)
        all_versions = self.get_account_versions(conn, account_key)
        target_key = self._resolve_target_account_key(
            account_key, version, all_versions
        )

        with _get_session(conn) as session:
            acc_record = self._fetch_account_record(session, target_key)
            if not acc_record:
                return None

            active_version = _extract_version_tag(acc_record.account_key)
            score_row = self._fetch_latest_score_for_account(
                session, acc_record.account_key, base_dom, active_version
            )
            return self._build_account_from_record(acc_record, all_versions, score_row)

    def _convert_record_to_batch_item(
        self, acc: AccountTable, as_dict: bool, max_preview_items: int
    ) -> Union[Dict[str, Any], Account]:
        key = acc.account_key
        version = _extract_version_tag(key)
        domains = [d.domain for d in acc.domains]
        ports = [p.port for p in acc.ports]
        products = [pr.product for pr in acc.products]
        cloud_providers = [cp.provider for cp in acc.cloud_providers]

        seen_sigs = set()
        signals: List[Any] = []
        for s in acc.signals:
            sig_tup = (s.name, s.severity, s.category)
            if sig_tup not in seen_sigs:
                seen_sigs.add(sig_tup)
                if as_dict:
                    signals.append(
                        {
                            "name": s.name,
                            "severity": s.severity,
                            "category": s.category,
                            "evidence": s.evidence,
                        }
                    )
                else:
                    signals.append(
                        SecuritySignal(
                            name=s.name,
                            severity=_to_signal_severity(s.severity),
                            category=s.category,
                            evidence=s.evidence,
                        )
                    )

        assets: List[Any] = []
        for a in acc.assets[:max_preview_items]:
            if as_dict:
                assets.append({"ip": a.ip, "port": a.port, "hostname": a.hostname})
            else:
                assets.append(Asset(ip=a.ip, port=a.port, hostname=a.hostname))

        ips = [i.ip for i in acc.ips[:max_preview_items]]
        hostnames = [h.hostname for h in acc.hostnames[:max_preview_items]]

        if as_dict:
            return {
                "account_key": key,
                "version": version,
                "domains": domains,
                "assets": assets,
                "ips": ips,
                "hostnames": hostnames,
                "ports": ports,
                "products": products,
                "cloud_providers": cloud_providers,
                "signals": signals,
            }
        else:
            return Account(
                account_key=key,
                version=version,
                domains=domains,
                assets=assets,
                ips=ips,
                hostnames=hostnames,
                ports=ports,
                products=products,
                cloud_providers=cloud_providers,
                signals=signals,
            )

    def load_accounts_batch(
        self,
        conn: Any,
        account_keys: List[str],
        as_dict: bool = False,
        max_preview_items: int = 25,
    ) -> List[Any]:
        if not account_keys:
            return []

        with _get_session(conn) as session:
            statement = (
                select(AccountTable)
                .where(col(AccountTable.account_key).in_(account_keys))
                .options(
                    selectinload(AccountTable.domains),  # type: ignore
                    selectinload(AccountTable.assets),  # type: ignore
                    selectinload(AccountTable.ips),  # type: ignore
                    selectinload(AccountTable.hostnames),  # type: ignore
                    selectinload(AccountTable.ports),  # type: ignore
                    selectinload(AccountTable.products),  # type: ignore
                    selectinload(AccountTable.cloud_providers),  # type: ignore
                    selectinload(AccountTable.signals),  # type: ignore
                )
            )
            records = session.exec(statement).all()
            if not records:
                return []

            accounts_by_key = {
                acc.account_key: self._convert_record_to_batch_item(
                    acc, as_dict, max_preview_items
                )
                for acc in records
            }
            return [accounts_by_key[k] for k in account_keys if k in accounts_by_key]

    def _batch_load_domains(
        self, cursor: Any, acc_ids: List[int]
    ) -> Dict[int, List[str]]:
        id_placeholders = _get_ph(cursor, acc_ids)
        domains_by_id: Dict[int, List[str]] = defaultdict(list)
        for acc_id, domain in cursor.execute(
            f"SELECT account_id, domain FROM domains WHERE account_id IN ({id_placeholders})",
            acc_ids,
        ):
            domains_by_id[acc_id].append(domain)
        return domains_by_id

    def _batch_load_asset_counts(
        self, cursor: Any, acc_ids: List[int]
    ) -> Dict[int, int]:
        id_placeholders = _get_ph(cursor, acc_ids)
        assets_count_by_id: Dict[int, int] = defaultdict(int)
        for acc_id, cnt in cursor.execute(
            f"SELECT account_id, count(*) FROM assets WHERE account_id IN ({id_placeholders}) GROUP BY account_id",
            acc_ids,
        ):
            assets_count_by_id[acc_id] = cnt
        return assets_count_by_id

    def _batch_load_hostname_counts(
        self, cursor: Any, acc_ids: List[int]
    ) -> Dict[int, int]:
        id_placeholders = _get_ph(cursor, acc_ids)
        hostnames_count_by_id: Dict[int, int] = defaultdict(int)
        for acc_id, cnt in cursor.execute(
            f"SELECT account_id, count(*) FROM hostnames WHERE account_id IN ({id_placeholders}) GROUP BY account_id",
            acc_ids,
        ):
            hostnames_count_by_id[acc_id] = cnt
        return hostnames_count_by_id

    def _batch_load_cloud_providers(
        self, cursor: Any, acc_ids: List[int]
    ) -> Dict[int, List[str]]:
        id_placeholders = _get_ph(cursor, acc_ids)
        providers_by_id: Dict[int, List[str]] = defaultdict(list)
        for acc_id, provider in cursor.execute(
            f"SELECT account_id, provider FROM cloud_providers WHERE account_id IN ({id_placeholders})",
            acc_ids,
        ):
            providers_by_id[acc_id].append(provider)
        return providers_by_id

    def _batch_load_signal_counts(
        self, cursor: Any, acc_ids: List[int]
    ) -> Dict[int, Dict[str, int]]:
        id_placeholders = _get_ph(cursor, acc_ids)
        signals_by_id: Dict[int, Dict[str, int]] = defaultdict(
            lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0}
        )
        for acc_id, sev, cnt in cursor.execute(
            f"SELECT account_id, lower(severity), count(*) FROM signals WHERE account_id IN ({id_placeholders}) GROUP BY account_id, lower(severity)",
            acc_ids,
        ):
            s_map = signals_by_id[acc_id]
            if sev in ("critical", "high", "medium", "low"):
                s_map[sev] += cnt
            s_map["total"] += cnt
        return signals_by_id

    def _batch_load_scores_map(
        self, cursor: Any, account_keys: List[str], base_doms: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        scores_map: Dict[str, Dict[str, Any]] = {}
        try:
            cand_keys = set(account_keys)
            for b_dom in base_doms:
                cand_keys.add(b_dom)
                cand_keys.add(f"domain:{b_dom}")
                for i in range(1, 15):
                    cand_keys.add(f"domain:{b_dom}:v{i}")
                    cand_keys.add(f"{b_dom}:v{i}")

            if not cand_keys:
                return scores_map

            cand_list = list(cand_keys)
            placeholders = _get_ph(cursor, cand_list)
            for acc_key, sc, p_tier, ver in cursor.execute(
                f"""
                SELECT account_key, score, priority_tier, version
                FROM ai_scores
                WHERE account_key IN ({placeholders})
                ORDER BY is_latest DESC, version DESC, id DESC
                """,
                cand_list,
            ).fetchall():
                score_val = {"score": sc, "priority_tier": p_tier, "version": ver}
                if acc_key not in scores_map:
                    scores_map[acc_key] = score_val
                dom_key = f"domain:{_extract_base_domain(acc_key)}"
                if dom_key not in scores_map:
                    scores_map[dom_key] = score_val
                raw_dom = _extract_base_domain(acc_key)
                if raw_dom not in scores_map:
                    scores_map[raw_dom] = score_val
        except Exception:
            pass
        return scores_map

    def _batch_load_domain_versions(
        self,
        cursor: Any,
        base_doms: List[str],
        scores_map: Dict[str, Dict[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        versions_by_base_domain: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        try:
            cand_keys = set()
            for b_dom in base_doms:
                cand_keys.add(b_dom)
                cand_keys.add(f"domain:{b_dom}")
                for i in range(1, 15):
                    cand_keys.add(f"domain:{b_dom}:v{i}")
                    cand_keys.add(f"{b_dom}:v{i}")

            if cand_keys:
                cand_list = list(cand_keys)
                placeholders = _get_ph(cursor, cand_list)
                for v_id, v_key, v_tier, v_sig_cnt in cursor.execute(
                    f"SELECT id, account_key, priority_tier, signal_count FROM accounts WHERE account_key IN ({placeholders}) ORDER BY id ASC",
                    cand_list,
                ).fetchall():
                    b_dom = _extract_base_domain(v_key)
                    v_tag = _extract_version_tag(v_key)
                    sc_info = (
                        scores_map.get(v_key)
                        or scores_map.get(f"domain:{b_dom}")
                        or scores_map.get(b_dom)
                    )
                    versions_by_base_domain[b_dom].append(
                        {
                            "version": v_tag,
                            "account_key": v_key,
                            "priority_tier": v_tier,
                            "signals_count": v_sig_cnt or 0,
                            "ai_score": sc_info["score"] if sc_info else None,
                            "is_active": False,
                        }
                    )
        except Exception:
            pass
        return versions_by_base_domain

    def _assemble_account_summaries(
        self,
        account_keys: List[str],
        acc_id_map: Dict[int, str],
        acc_tier_map: Dict[str, str],
        domains_by_id: Dict[int, List[str]],
        assets_count_by_id: Dict[int, int],
        hostnames_count_by_id: Dict[int, int],
        providers_by_id: Dict[int, List[str]],
        signals_by_id: Dict[int, Dict[str, int]],
        scores_map: Dict[str, Dict[str, Any]],
        versions_by_base_domain: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        key_to_acc_id = {v: k for k, v in acc_id_map.items()}
        result = []

        def _ver_order(item: Dict[str, Any]) -> int:
            v_str = item.get("version", "").lstrip("v")
            return int(v_str) if v_str.isdigit() else 1

        for key in account_keys:
            acc_id = key_to_acc_id.get(key)
            if acc_id is None:
                continue
            domains = domains_by_id.get(acc_id, [])
            primary_domain = domains[0] if domains else key.replace("domain:", "")
            base_dom = _extract_base_domain(primary_domain or key)
            total_assets = assets_count_by_id.get(acc_id, 0)
            total_subdomains = hostnames_count_by_id.get(acc_id, 0)
            providers = providers_by_id.get(acc_id, [])
            sig_counts = signals_by_id.get(
                acc_id, {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0}
            )
            latest_score = (
                scores_map.get(key)
                or scores_map.get(f"domain:{primary_domain}")
                or scores_map.get(primary_domain)
                or (scores_map.get(base_dom) if base_dom else None)
            )

            version = _extract_version_tag(key)
            domain_vers = versions_by_base_domain.get(base_dom, [])
            domain_vers_sorted = sorted(domain_vers, key=_ver_order, reverse=True)

            for v_it in domain_vers_sorted:
                if v_it.get("version") == version:
                    v_it["is_active"] = True

            result.append(
                {
                    "account_key": key,
                    "version": version,
                    "domain": primary_domain,
                    "domains": domains,
                    "priority_tier": acc_tier_map.get(key, "tier_4_low"),
                    "critical_signals_count": sig_counts["critical"],
                    "high_signals_count": sig_counts["high"],
                    "medium_signals_count": sig_counts["medium"],
                    "low_signals_count": sig_counts["low"],
                    "total_signals_count": sig_counts["total"],
                    "total_assets": total_assets,
                    "total_subdomains": total_subdomains,
                    "cloud_providers": providers,
                    "ai_score": latest_score["score"] if latest_score else None,
                    "latest_score": latest_score,
                    "total_versions": len(domain_vers_sorted)
                    if domain_vers_sorted
                    else 1,
                    "available_versions": domain_vers_sorted,
                }
            )

        return result

    def load_accounts_summary_batch(
        self,
        conn: Any,
        account_keys: List[str],
    ) -> List[Dict[str, Any]]:
        if not account_keys:
            return []

        raw = _extract_raw_conn(conn)
        cursor = raw.cursor()
        try:
            placeholders = _get_ph(cursor, account_keys)
            acc_rows = cursor.execute(
                f"SELECT id, account_key, priority_tier FROM accounts WHERE account_key IN ({placeholders})",
                account_keys,
            ).fetchall()

            if not acc_rows:
                return []

            acc_id_map = {row[0]: row[1] for row in acc_rows}
            acc_tier_map = {row[1]: row[2] for row in acc_rows}
            acc_ids = list(acc_id_map.keys())
            base_doms = list(
                set(
                    _extract_base_domain(k)
                    for k in account_keys
                    if _extract_base_domain(k)
                )
            )

            domains_by_id = self._batch_load_domains(cursor, acc_ids)
            assets_count_by_id = self._batch_load_asset_counts(cursor, acc_ids)
            hostnames_count_by_id = self._batch_load_hostname_counts(cursor, acc_ids)
            providers_by_id = self._batch_load_cloud_providers(cursor, acc_ids)
            signals_by_id = self._batch_load_signal_counts(cursor, acc_ids)
            scores_map = self._batch_load_scores_map(cursor, account_keys, base_doms)
            versions_by_base_domain = self._batch_load_domain_versions(
                cursor, base_doms, scores_map
            )

            return self._assemble_account_summaries(
                account_keys=account_keys,
                acc_id_map=acc_id_map,
                acc_tier_map=acc_tier_map,
                domains_by_id=domains_by_id,
                assets_count_by_id=assets_count_by_id,
                hostnames_count_by_id=hostnames_count_by_id,
                providers_by_id=providers_by_id,
                signals_by_id=signals_by_id,
                scores_map=scores_map,
                versions_by_base_domain=versions_by_base_domain,
            )
        finally:
            try:
                cursor.close()
            except Exception:
                pass

    def _deduplicate_latest_domains(self, rows: Any, limit: int) -> List[str]:
        domain_map: Dict[str, Tuple[int, int, str]] = {}
        for row in rows:
            acc_id = row[0] if len(row) > 0 else None
            acc_key = row[1] if len(row) > 1 else ""
            base_dom = _extract_base_domain(acc_key)
            if not base_dom:
                continue
            ver_tag = _extract_version_tag(acc_key)
            ver_num = int(ver_tag.lstrip("v")) if ver_tag.lstrip("v").isdigit() else 1
            acc_id_val = int(acc_id or 0)
            if base_dom not in domain_map:
                domain_map[base_dom] = (ver_num, acc_id_val, acc_key)
            else:
                curr_v, curr_id, _ = domain_map[base_dom]
                if ver_num > curr_v or (ver_num == curr_v and acc_id_val > curr_id):
                    domain_map[base_dom] = (ver_num, acc_id_val, acc_key)

        return [val[2] for val in domain_map.values()][:limit]

    def search_accounts_by_domain(
        self, conn: Any, domain_query: str, limit: int = 10
    ) -> List[str]:
        cleaned_query = domain_query.strip()
        if not cleaned_query:
            return []
        with _get_session(conn) as session:
            statement = (
                select(
                    AccountTable.id, AccountTable.account_key, AccountTable.signal_count
                )
                .outerjoin(
                    DomainTable, col(AccountTable.id) == col(DomainTable.account_id)
                )
                .where(
                    or_(
                        col(DomainTable.domain).contains(cleaned_query),
                        col(AccountTable.account_key).contains(cleaned_query),
                    )
                )
                .distinct()
                .order_by(
                    col(AccountTable.signal_count).desc(), col(AccountTable.id).desc()
                )
                .limit(max(limit * 20, 50))
            )
            rows = session.exec(statement).all()
            return self._deduplicate_latest_domains(rows, limit)

    def get_accounts_by_signal(
        self, conn: Any, signal_name: str, skip: int = 0, limit: int = 20
    ) -> Tuple[List[str], int]:
        with _get_session(conn) as session:
            count_stmt = select(
                func.count(func.distinct(col(SignalTable.account_id)))
            ).where(SignalTable.name == signal_name)
            total = session.exec(count_stmt).one() or 0

            statement = (
                select(AccountTable.account_key)
                .join(SignalTable, col(AccountTable.id) == col(SignalTable.account_id))
                .where(SignalTable.name == signal_name)
                .distinct()
                .order_by(
                    col(AccountTable.signal_count).desc(), col(AccountTable.id).asc()
                )
                .offset(skip)
                .limit(limit)
            )
            account_keys = list(session.exec(statement).all())
            return account_keys, total

    def get_accounts_with_critical_signals(
        self, conn: Any, skip: int = 0, limit: int = 20, total: Optional[int] = None
    ) -> Tuple[List[str], int]:
        if total is None:
            stats = self.get_summary_stats(conn)
            total = stats["accounts_with_critical_signals"]

        with _get_session(conn) as session:
            statement = (
                select(AccountTable.account_key)
                .where(AccountTable.priority_tier == "tier_1_critical")
                .order_by(
                    col(AccountTable.signal_count).desc(), col(AccountTable.id).asc()
                )
                .offset(skip)
                .limit(limit)
            )
            keys = list(session.exec(statement).all())
            return keys, total

    def get_all_accounts(
        self, conn: Any, skip: int = 0, limit: int = 20, total: Optional[int] = None
    ) -> Tuple[List[str], int]:
        if total is None:
            stats = self.get_summary_stats(conn)
            total = stats["total_accounts"]
        with _get_session(conn) as session:
            statement = (
                select(AccountTable.account_key)
                .order_by(
                    col(AccountTable.signal_count).desc(), col(AccountTable.id).asc()
                )
                .offset(skip)
                .limit(limit)
            )
            keys = list(session.exec(statement).all())
            return keys, total

    def get_accounts_by_priority_tier(
        self,
        conn: Any,
        priority_tier: str,
        skip: int = 0,
        limit: int = 20,
        total: Optional[int] = None,
    ) -> Tuple[List[str], int]:
        if total is None:
            stats = self.get_summary_stats(conn)
            valid_tiers = {
                "tier_1_critical": stats["critical_count"],
                "tier_2_high": stats["high_count"],
                "tier_3_medium": stats["medium_count"],
                "tier_4_low": stats["low_count"],
            }
            if priority_tier in valid_tiers:
                total = valid_tiers[priority_tier]
            else:
                return self.get_all_accounts(conn, skip=skip, limit=limit)

        with _get_session(conn) as session:
            statement = (
                select(AccountTable.account_key)
                .where(AccountTable.priority_tier == priority_tier)
                .order_by(
                    col(AccountTable.signal_count).desc(), col(AccountTable.id).asc()
                )
                .offset(skip)
                .limit(limit)
            )
            keys = list(session.exec(statement).all())
            return keys, total

    def get_summary_stats(self, conn: Any) -> Dict[str, int]:
        with _get_session(conn) as session:
            statement = select(
                AccountTable.priority_tier, func.count(col(AccountTable.id))
            ).group_by(AccountTable.priority_tier)
            tier_counts = dict(session.exec(statement).all())

            critical_count = tier_counts.get("tier_1_critical", 0)
            high_count = tier_counts.get("tier_2_high", 0)
            medium_count = tier_counts.get("tier_3_medium", 0)
            low_count = tier_counts.get("tier_4_low", 0)
            total_accounts = critical_count + high_count + medium_count + low_count

            return {
                "total_accounts": total_accounts,
                "critical_count": critical_count,
                "high_count": high_count,
                "medium_count": medium_count,
                "low_count": low_count,
                "accounts_with_critical_signals": critical_count,
            }

import sqlite3
from typing import Optional, Dict, List, Tuple, Any
from collections import defaultdict

from src.services.accounts.types import IAccountReader, Account, Asset, SecuritySignal


class AccountReader(IAccountReader):

    def load_account(self, conn: sqlite3.Connection, account_key: str) -> Optional[Account]:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, account_key, priority_tier FROM accounts WHERE account_key = ? OR account_key = ? OR account_key = ? LIMIT 1",
            (account_key, f"domain:{account_key}", account_key.replace("domain:", "")),
        )
        row = cursor.fetchone()
        if not row:
            return None

        account_id, canonical_key, priority_tier = row[0], row[1], row[2]

        cursor.execute("SELECT domain FROM domains WHERE account_id = ?", (account_id,))
        domains = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT ip, port, hostname FROM assets WHERE account_id = ?", (account_id,))
        assets = [Asset(ip=r[0], port=r[1], hostname=r[2]) for r in cursor.fetchall()]

        cursor.execute("SELECT ip FROM ips WHERE account_id = ?", (account_id,))
        ips = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT hostname FROM hostnames WHERE account_id = ?", (account_id,))
        hostnames = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT port FROM ports WHERE account_id = ?", (account_id,))
        ports = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT product FROM products WHERE account_id = ?", (account_id,))
        products = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT provider FROM cloud_providers WHERE account_id = ?", (account_id,))
        cloud_providers = [r[0] for r in cursor.fetchall()]

        cursor.execute("SELECT name, severity, category, evidence FROM signals WHERE account_id = ?", (account_id,))
        signals = [SecuritySignal(name=r[0], severity=r[1], category=r[2], evidence=r[3]) for r in cursor.fetchall()]

        ai_score = None
        latest_score = None
        try:
            import json
            cursor.execute(
                """
                SELECT id, account_key, version, score, priority_tier, key_risks,
                       suggested_outreach, score_rationale, model_version, model_name,
                       tokens_used, latency_ms, cost_usd, scored_at
                FROM ai_scores
                WHERE (account_key = ? OR account_key = ? OR account_key = ?) AND is_latest = 1
                ORDER BY version DESC LIMIT 1
                """,
                (canonical_key, account_key, f"domain:{account_key}"),
            )
            score_row = cursor.fetchone()
            if score_row:
                ai_score = score_row[3]
                try:
                    risks = json.loads(score_row[5]) if isinstance(score_row[5], str) else score_row[5]
                except Exception:
                    risks = [score_row[5]] if score_row[5] else []
                try:
                    tokens = json.loads(score_row[10]) if isinstance(score_row[10], str) else score_row[10]
                except Exception:
                    tokens = {}
                latest_score = {
                    "id": score_row[0],
                    "account_key": score_row[1],
                    "version": score_row[2],
                    "score": score_row[3],
                    "priority_tier": score_row[4],
                    "key_risks": risks,
                    "suggested_outreach": score_row[6],
                    "score_rationale": score_row[7],
                    "model_version": score_row[8],
                    "model_name": score_row[9],
                    "tokens_used": tokens,
                    "latency_ms": score_row[11],
                    "cost_usd": score_row[12],
                    "timestamp": score_row[13],
                }
        except Exception:
            pass

        primary_domain = domains[0] if domains else canonical_key.replace("domain:", "")

        version = "v1"
        if canonical_key.count(":") >= 2:
            parts = canonical_key.split(":")
            if parts[-1].startswith("v") and parts[-1][1:].isdigit():
                version = parts[-1]

        return Account(
            account_key=canonical_key,
            version=version,
            domain=primary_domain,
            domains=domains,
            priority_tier=priority_tier,
            critical_signals_count=len([s for s in signals if getattr(s.severity, "value", str(s.severity)).lower() == "critical"]),
            high_signals_count=len([s for s in signals if getattr(s.severity, "value", str(s.severity)).lower() == "high"]),
            medium_signals_count=len([s for s in signals if getattr(s.severity, "value", str(s.severity)).lower() == "medium"]),
            low_signals_count=len([s for s in signals if getattr(s.severity, "value", str(s.severity)).lower() == "low"]),
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
        )

    def load_accounts_batch(
        self,
        conn: sqlite3.Connection,
        account_keys: List[str],
        as_dict: bool = False,
        max_preview_items: int = 25,
    ) -> List[Any]:
        """High-performance batch loader fetching multiple accounts with deduplicated signals and capped previews."""
        if not account_keys:
            return []

        cursor = conn.cursor()
        placeholders = ",".join("?" * len(account_keys))
        cursor.execute(f"SELECT id, account_key, priority_tier, signal_count FROM accounts WHERE account_key IN ({placeholders})", account_keys)
        acc_rows = cursor.fetchall()
        if not acc_rows:
            return []

        id_to_key = {r[0]: r[1] for r in acc_rows}
        acc_ids = list(id_to_key.keys())
        id_placeholders = ",".join("?" * len(acc_ids))

        domains_map = defaultdict(list)
        cursor.execute(f"SELECT account_id, domain FROM domains WHERE account_id IN ({id_placeholders})", acc_ids)
        for aid, d in cursor.fetchall():
            domains_map[aid].append(d)

        ports_map = defaultdict(list)
        cursor.execute(f"SELECT account_id, port FROM ports WHERE account_id IN ({id_placeholders})", acc_ids)
        for aid, p in cursor.fetchall():
            ports_map[aid].append(p)

        products_map = defaultdict(list)
        cursor.execute(f"SELECT account_id, product FROM products WHERE account_id IN ({id_placeholders})", acc_ids)
        for aid, prod in cursor.fetchall():
            products_map[aid].append(prod)

        providers_map = defaultdict(list)
        cursor.execute(f"SELECT account_id, provider FROM cloud_providers WHERE account_id IN ({id_placeholders})", acc_ids)
        for aid, prov in cursor.fetchall():
            providers_map[aid].append(prov)

        signals_map = defaultdict(list)
        cursor.execute(
            f"""
            SELECT account_id, name, severity, category, MIN(evidence) 
            FROM signals 
            WHERE account_id IN ({id_placeholders}) 
            GROUP BY account_id, name, severity, category
            """,
            acc_ids,
        )
        for aid, name, sev, cat, ev in cursor.fetchall():
            if as_dict:
                signals_map[aid].append({"name": name, "severity": sev, "category": cat, "evidence": ev})
            else:
                signals_map[aid].append(SecuritySignal(name=name, severity=sev, category=cat, evidence=ev))

        assets_map = defaultdict(list)
        try:
            cursor.execute(
                f"""
                SELECT account_id, ip, port, hostname 
                FROM (
                    SELECT account_id, ip, port, hostname, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY id) as rn 
                    FROM assets 
                    WHERE account_id IN ({id_placeholders})
                ) WHERE rn <= ?
                """,
                acc_ids + [max_preview_items],
            )
            for aid, ip, port, host in cursor.fetchall():
                if as_dict:
                    assets_map[aid].append({"ip": ip, "port": port, "hostname": host})
                else:
                    assets_map[aid].append(Asset(ip=ip, port=port, hostname=host))
        except Exception:
            cursor.execute(f"SELECT account_id, ip, port, hostname FROM assets WHERE account_id IN ({id_placeholders})", acc_ids)
            for aid, ip, port, host in cursor.fetchall():
                if len(assets_map[aid]) < max_preview_items:
                    if as_dict:
                        assets_map[aid].append({"ip": ip, "port": port, "hostname": host})
                    else:
                        assets_map[aid].append(Asset(ip=ip, port=port, hostname=host))

        ips_map = defaultdict(list)
        try:
            cursor.execute(
                f"""
                SELECT account_id, ip 
                FROM (
                    SELECT account_id, ip, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY id) as rn 
                    FROM ips 
                    WHERE account_id IN ({id_placeholders})
                ) WHERE rn <= ?
                """,
                acc_ids + [max_preview_items],
            )
            for aid, ip in cursor.fetchall():
                ips_map[aid].append(ip)
        except Exception:
            cursor.execute(f"SELECT account_id, ip FROM ips WHERE account_id IN ({id_placeholders})", acc_ids)
            for aid, ip in cursor.fetchall():
                if len(ips_map[aid]) < max_preview_items:
                    ips_map[aid].append(ip)

        hostnames_map = defaultdict(list)
        try:
            cursor.execute(
                f"""
                SELECT account_id, hostname 
                FROM (
                    SELECT account_id, hostname, ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY id) as rn 
                    FROM hostnames 
                    WHERE account_id IN ({id_placeholders})
                ) WHERE rn <= ?
                """,
                acc_ids + [max_preview_items],
            )
            for aid, h in cursor.fetchall():
                hostnames_map[aid].append(h)
        except Exception:
            cursor.execute(f"SELECT account_id, hostname FROM hostnames WHERE account_id IN ({id_placeholders})", acc_ids)
            for aid, h in cursor.fetchall():
                if len(hostnames_map[aid]) < max_preview_items:
                    hostnames_map[aid].append(h)

        accounts_by_key = {}
        for aid, key in id_to_key.items():
            version = "v1"
            if key.count(":") >= 2:
                parts = key.split(":")
                if parts[-1].startswith("v") and parts[-1][1:].isdigit():
                    version = parts[-1]

            if as_dict:
                accounts_by_key[key] = {
                    "account_key": key,
                    "version": version,
                    "domains": domains_map[aid],
                    "assets": assets_map[aid],
                    "ips": ips_map[aid],
                    "hostnames": hostnames_map[aid],
                    "ports": ports_map[aid],
                    "products": products_map[aid],
                    "cloud_providers": providers_map[aid],
                    "signals": signals_map[aid],
                }
            else:
                accounts_by_key[key] = Account(
                    account_key=key,
                    version=version,
                    domains=domains_map[aid],
                    assets=assets_map[aid],
                    ips=ips_map[aid],
                    hostnames=hostnames_map[aid],
                    ports=ports_map[aid],
                    products=products_map[aid],
                    cloud_providers=providers_map[aid],
                    signals=signals_map[aid],
                )

        return [accounts_by_key[k] for k in account_keys if k in accounts_by_key]

    def load_accounts_summary_batch(
        self,
        conn: sqlite3.Connection,
        account_keys: List[str],
    ) -> List[Dict[str, Any]]:
        """Ultra-lightweight batch loader returning only summary data for list views (no ports/products/ips arrays)."""
        if not account_keys:
            return []

        cursor = conn.cursor()
        placeholders = ",".join("?" * len(account_keys))
        cursor.execute(
            f"SELECT id, account_key, priority_tier, signal_count FROM accounts WHERE account_key IN ({placeholders})",
            account_keys,
        )
        acc_rows = cursor.fetchall()
        if not acc_rows:
            return []

        id_to_meta = {r[0]: (r[1], r[2]) for r in acc_rows}
        acc_ids = list(id_to_meta.keys())
        id_placeholders = ",".join("?" * len(acc_ids))

        domains_map = defaultdict(list)
        cursor.execute(f"SELECT account_id, domain FROM domains WHERE account_id IN ({id_placeholders})", acc_ids)
        for aid, d in cursor.fetchall():
            domains_map[aid].append(d)

        providers_map = defaultdict(list)
        cursor.execute(f"SELECT account_id, provider FROM cloud_providers WHERE account_id IN ({id_placeholders})", acc_ids)
        for aid, prov in cursor.fetchall():
            providers_map[aid].append(prov)

        crit_counts = defaultdict(int)
        high_counts = defaultdict(int)
        med_counts = defaultdict(int)
        low_counts = defaultdict(int)
        total_sig_counts = defaultdict(int)

        cursor.execute(
            f"""
            SELECT 
                account_id,
                SUM(CASE WHEN LOWER(severity) = 'critical' THEN 1 ELSE 0 END) as crit_cnt,
                SUM(CASE WHEN LOWER(severity) = 'high' THEN 1 ELSE 0 END) as high_cnt,
                SUM(CASE WHEN LOWER(severity) = 'medium' THEN 1 ELSE 0 END) as med_cnt,
                SUM(CASE WHEN LOWER(severity) = 'low' THEN 1 ELSE 0 END) as low_cnt,
                COUNT(*) as total_cnt
            FROM signals 
            WHERE account_id IN ({id_placeholders}) 
            GROUP BY account_id
            """,
            acc_ids,
        )
        for aid, crit_c, high_c, med_c, low_c, tot_c in cursor.fetchall():
            crit_counts[aid] = crit_c or 0
            high_counts[aid] = high_c or 0
            med_counts[aid] = med_c or 0
            low_counts[aid] = low_c or 0
            total_sig_counts[aid] = tot_c or 0

        assets_count_map = defaultdict(int)
        cursor.execute(
            f"SELECT account_id, COUNT(*) FROM assets WHERE account_id IN ({id_placeholders}) GROUP BY account_id",
            acc_ids,
        )
        for aid, count in cursor.fetchall():
            assets_count_map[aid] = count

        subdomains_count_map = defaultdict(int)
        cursor.execute(
            f"SELECT account_id, COUNT(*) FROM hostnames WHERE account_id IN ({id_placeholders}) GROUP BY account_id",
            acc_ids,
        )
        for aid, count in cursor.fetchall():
            subdomains_count_map[aid] = count

        scores_map = {}
        try:
            cursor.execute(
                f"SELECT account_key, score, priority_tier, version FROM ai_scores WHERE account_key IN ({placeholders}) AND is_latest = 1",
                account_keys,
            )
            for acc_k, sc, pt, ver in cursor.fetchall():
                scores_map[acc_k] = {
                    "score": sc,
                    "priority_tier": pt,
                    "version": ver,
                }
        except Exception:
            pass

        accounts_by_key = {}
        for aid, (key, tier) in id_to_meta.items():
            primary_domain = domains_map[aid][0] if domains_map[aid] else key.replace("domain:", "")
            total_assets = assets_count_map[aid]
            total_subdomains = subdomains_count_map[aid]
            latest_score = scores_map.get(key)

            version = "v1"
            if key.count(":") >= 2:
                parts = key.split(":")
                if parts[-1].startswith("v") and parts[-1][1:].isdigit():
                    version = parts[-1]

            accounts_by_key[key] = {
                "account_key": key,
                "version": version,
                "domain": primary_domain,
                "domains": domains_map[aid],
                "priority_tier": tier,
                "critical_signals_count": crit_counts[aid],
                "high_signals_count": high_counts[aid],
                "medium_signals_count": med_counts[aid],
                "low_signals_count": low_counts[aid],
                "total_signals_count": total_sig_counts[aid],
                "total_assets": total_assets,
                "total_subdomains": total_subdomains,
                "cloud_providers": providers_map[aid],
                "ai_score": latest_score["score"] if latest_score else None,
                "latest_score": latest_score,
            }

        return [accounts_by_key[k] for k in account_keys if k in accounts_by_key]

    def search_accounts_by_domain(self, conn: sqlite3.Connection, domain_query: str, limit: int = 10) -> List[str]:
        """Search for account keys matching domain substring (capped at top N results)."""
        cursor = conn.cursor()
        query_param = f"%{domain_query.strip()}%"
        cursor.execute(
            """
            SELECT accounts.account_key 
            FROM accounts 
            JOIN (
                SELECT DISTINCT account_id FROM domains WHERE domain LIKE ?
            ) t ON accounts.id = t.account_id
            ORDER BY accounts.signal_count DESC, accounts.id ASC
            LIMIT ?
            """,
            (query_param, limit),
        )
        return [r[0] for r in cursor.fetchall()]

    def get_accounts_by_signal(self, conn: sqlite3.Connection, signal_name: str, skip: int = 0, limit: int = 20) -> Tuple[List[str], int]:
        """Get account keys with a specific security signal."""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(DISTINCT account_id) FROM signals WHERE name = ?", (signal_name,))
        total = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT accounts.account_key 
            FROM accounts 
            JOIN (
                SELECT DISTINCT account_id FROM signals WHERE name = ?
            ) t ON accounts.id = t.account_id
            ORDER BY accounts.signal_count DESC, accounts.id ASC
            LIMIT ? OFFSET ?
            """,
            (signal_name, limit, skip),
        )
        account_keys = [r[0] for r in cursor.fetchall()]
        return account_keys, total

    def get_accounts_with_critical_signals(self, conn: sqlite3.Connection, skip: int = 0, limit: int = 20) -> Tuple[List[str], int]:
        """Get account keys that have critical signals."""
        stats = self.get_summary_stats(conn)
        total = stats["accounts_with_critical_signals"]

        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT account_key 
            FROM accounts 
            WHERE priority_tier = 'tier_1_critical' 
            ORDER BY signal_count DESC, id ASC 
            LIMIT ? OFFSET ?
            """,
            (limit, skip),
        )
        return [r[0] for r in cursor.fetchall()], total

    def get_all_accounts(self, conn: sqlite3.Connection, skip: int = 0, limit: int = 20) -> Tuple[List[str], int]:
        """Get all account keys paginated and sorted by signal count descending."""
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM accounts")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT account_key FROM accounts ORDER BY signal_count DESC, id ASC LIMIT ? OFFSET ?", (limit, skip))
        account_keys = [r[0] for r in cursor.fetchall()]
        return account_keys, total

    def get_accounts_by_priority_tier(
        self, conn: sqlite3.Connection, priority_tier: str, skip: int = 0, limit: int = 20
    ) -> Tuple[List[str], int]:
        """Get account keys filtered by priority tier."""
        cursor = conn.cursor()
        stats = self.get_summary_stats(conn)

        valid_tiers = {
            "tier_1_critical": stats["critical_count"],
            "tier_2_high": stats["high_count"],
            "tier_3_medium": stats["medium_count"],
            "tier_4_low": stats["low_count"],
        }

        if priority_tier in valid_tiers:
            total = valid_tiers[priority_tier]
            cursor.execute(
                """
                SELECT account_key 
                FROM accounts 
                WHERE priority_tier = ? 
                ORDER BY signal_count DESC, id ASC 
                LIMIT ? OFFSET ?
                """,
                (priority_tier, limit, skip),
            )
            keys = [r[0] for r in cursor.fetchall()]
            return keys, total
        else:
            return self.get_all_accounts(conn, skip=skip, limit=limit)

    def get_summary_stats(self, conn: sqlite3.Connection) -> Dict[str, int]:
        """Calculate aggregated summary statistics from database using indexed accounts table."""
        cursor = conn.cursor()
        cursor.execute("SELECT priority_tier, COUNT(*) FROM accounts GROUP BY priority_tier")
        tier_counts = dict(cursor.fetchall())

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


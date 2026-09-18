import time
from typing import Optional, List, Dict, Any

from src.services.accounts.types import Account, Asset, SecuritySignal
from src.services.database import (
    get_dynamo_resource,
    get_table_name,
    float_to_decimal,
    decimal_to_python,
)
from src.services.logger import get_logger

logger = get_logger("services.accounts.dynamo_crawled")


class DynamoCrawledRepository:

    def __init__(self, table_name: Optional[str] = None):
        self._table_name = table_name or get_table_name("crawled")
        self._table = None

    @property
    def table(self):
        if self._table is None:
            dynamo = get_dynamo_resource()
            self._table = dynamo.Table(self._table_name)
        return self._table

    def save_crawled_account(self, account: Account, priority_tier: str) -> None:
        """Saves or updates a crawled account in DynamoDB."""
        try:
            acc_key = account.account_key
            clean_dom = account.domain or acc_key.replace("domain:", "")

            assets_data = [
                {"ip": a.ip, "port": a.port, "hostname": a.hostname}
                for a in (account.assets or [])
            ]
            signals_data = [
                {
                    "name": s.name,
                    "severity": s.severity.value if hasattr(s.severity, "value") else str(s.severity),
                    "category": getattr(s, "category", ""),
                    "evidence": s.evidence or "",
                }
                for s in (account.signals or [])
            ]

            item = {
                "account_key": acc_key,
                "domain": clean_dom,
                "domains": account.domains or [clean_dom],
                "priority_tier": priority_tier,
                "signal_count": len(account.signals or []),
                "assets": assets_data,
                "signals": signals_data,
                "ips": account.ips or [],
                "hostnames": account.hostnames or [],
                "ports": account.ports or [],
                "products": account.products or [],
                "cloud_providers": account.cloud_providers or [],
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }

            self.table.put_item(Item=float_to_decimal(item))
            logger.info("Saved crawled account to DynamoDB", account_key=acc_key, tier=priority_tier)
        except Exception as e:
            logger.error(f"Error saving crawled account to DynamoDB: {e}", account_key=account.account_key)

    def get_crawled_account(self, account_key: str) -> Optional[Account]:
        """Fetches a crawled account by key or domain from DynamoDB."""
        try:
            keys_to_try = [
                account_key,
                f"domain:{account_key}",
                account_key.replace("domain:", ""),
            ]
            for k in set(keys_to_try):
                resp = self.table.get_item(Key={"account_key": k})
                item = resp.get("Item")
                if item:
                    return self._map_to_account(decimal_to_python(item))
            return None
        except Exception as e:
            logger.error(f"Error fetching crawled account from DynamoDB: {e}", account_key=account_key)
            return None

    def search_crawled_accounts(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Searches crawled accounts in DynamoDB by domain or hostname match."""
        try:
            clean_q = query.strip().lower()
            if not clean_q:
                return []

            direct = self.get_crawled_account(clean_q)
            results = []
            if direct:
                results.append(self._to_summary_dict(direct))

            resp = self.table.scan(
                FilterExpression="contains(account_key, :q) OR contains(#dom, :q)",
                ExpressionAttributeNames={"#dom": "domain"},
                ExpressionAttributeValues={":q": clean_q},
                Limit=limit,
            )
            for it in resp.get("Items", []):
                acc = self._map_to_account(decimal_to_python(it))
                summary = self._to_summary_dict(acc)
                if not any(r["account_key"] == summary["account_key"] for r in results):
                    results.append(summary)
                if len(results) >= limit:
                    break

            return results
        except Exception as e:
            logger.error(f"Error searching crawled accounts in DynamoDB: {e}", query=query)
            return []

    def _map_to_account(self, item: Dict[str, Any]) -> Account:
        assets = [
            Asset(ip=a.get("ip", ""), port=a.get("port", 0), hostname=a.get("hostname", ""))
            for a in item.get("assets", [])
        ]
        signals = [
            SecuritySignal(
                name=s.get("name", ""),
                severity=s.get("severity", "medium"),
                category=s.get("category", ""),
                evidence=s.get("evidence", ""),
            )
            for s in item.get("signals", [])
        ]
        return Account(
            account_key=item.get("account_key", ""),
            domain=item.get("domain", ""),
            domains=item.get("domains", []),
            assets=assets,
            ips=item.get("ips", []),
            hostnames=item.get("hostnames", []),
            ports=item.get("ports", []),
            products=item.get("products", []),
            cloud_providers=item.get("cloud_providers", []),
            signals=signals,
        )

    def _to_summary_dict(self, acc: Account) -> Dict[str, Any]:
        return {
            "account_key": acc.account_key,
            "domain": acc.domain or (acc.domains[0] if acc.domains else acc.account_key),
            "priority_tier": "tier_2_high" if len(acc.signals) >= 2 else "tier_3_medium",
            "signal_count": len(acc.signals),
            "critical_count": sum(1 for s in acc.signals if getattr(s, "severity", "") in ["critical", "CRITICAL"]),
            "assets_count": len(acc.assets),
            "top_signals": [s.name for s in acc.signals[:3]],
            "technologies": acc.products[:5] if acc.products else [],
            "cloud_providers": acc.cloud_providers[:3] if acc.cloud_providers else [],
        }

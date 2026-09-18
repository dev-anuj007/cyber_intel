"""Aggregator Service for Raw Asset Data Aggregation, PTR Filtering, and Security Signal Detection."""

import json
import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Set

from src.services.accounts.types import Account, Asset, SecuritySignal, SignalSeverity
from src.services.aggregator.types import IAggregatorService
from src.services.logger import get_logger

logger = get_logger("services.aggregator")


def normalize_domain(domain: str) -> str:
    """Normalize domain to lowercase and strip whitespace and trailing dots."""
    if not domain or not isinstance(domain, str):
        return ""
    return domain.lower().strip().rstrip(".")


def is_valid_account_domain(domain: str) -> bool:
    """Validate domain format."""
    if not domain:
        return False
    if "/" in domain or "\\" in domain:
        return False
    if domain.endswith(".in-addr.arpa") or domain.endswith(".ip6.arpa"):
        return False
    if "." not in domain:
        return False
    return True


def is_dynamic_ip_ptr(hostname: str) -> bool:
    """Algorithmically detect if a hostname is an auto-generated dynamic IP reverse PTR record."""
    if not hostname:
        return False
    h = hostname.lower().strip()
    if re.search(r'\b\d{1,3}[-\.]\d{1,3}[-\.]\d{1,3}[-\.]\d{1,3}\b', h):
        return True
    if re.match(r'^(ip|node|host|cpe|static|dynamic|pool|dialup|cust|broadband|dsl|fiber|vps|server|ec2|vm)[0-9\-_]', h):
        return True
    return False


def is_infrastructure_transit_domain(domain: str) -> bool:
    """Algorithmically detect dynamic cloud or ISP transit reverse domains."""
    if not domain or not isinstance(domain, str):
        return True
    d = normalize_domain(domain)
    if not is_valid_account_domain(d):
        return True
    if is_dynamic_ip_ptr(d):
        return True
    return False


def extract_root_domain_match(hostname: str, candidate_domains: List[str]) -> List[str]:
    """Given a hostname and candidate certificate domains, find exact root matches."""
    norm_host = normalize_domain(hostname)
    matches = []
    for domain in candidate_domains:
        norm_dom = normalize_domain(domain)
        if norm_host == norm_dom or norm_host.endswith("." + norm_dom):
            matches.append(f"domain:{norm_dom}")
    return matches


class AggregatorService(IAggregatorService):
    """Service encapsulating asset aggregation, feature extraction, and signal detection."""

    def resolve_account_keys(self, record: dict) -> List[str]:
        """Resolve precise account identities from record domain and hostname metadata."""
        raw_domains = record.get("domains") or []
        valid_domains = []

        for domain in raw_domains:
            if not isinstance(domain, str):
                continue

            domain = normalize_domain(domain)
            if is_infrastructure_transit_domain(domain):
                continue

            valid_domains.append(domain)

        if not valid_domains:
            return []

        hostnames = record.get("hostnames") or []
        if isinstance(hostnames, str):
            hostnames = [hostnames]

        matched_keys = set()
        has_only_ptr = len(hostnames) > 0

        for h in hostnames:
            if isinstance(h, str) and h.strip():
                if is_dynamic_ip_ptr(h):
                    continue
                has_only_ptr = False
                for key in extract_root_domain_match(h, valid_domains):
                    matched_keys.add(key)

        if matched_keys:
            return sorted(list(matched_keys))

        if has_only_ptr:
            return []

        return sorted(list(set(f"domain:{d}" for d in valid_domains)))

    def get_asset_id(self, features: dict) -> Optional[Tuple[str, Optional[int], Optional[str]]]:
        """Generate unique asset identity tuple from IP, port, hostname."""
        ip = features.get("ip")
        port = features.get("port")
        hostname = features.get("hostname")

        if not ip and not hostname:
            return None

        return (ip, port, hostname)

    def extract_vulnerability_features(self, vulns: Optional[dict]) -> dict:
        """Extract vulnerability metrics from raw record vuln dictionary."""
        vulns = vulns or {}

        if not vulns:
            return {
                "vulnerability_count": 0,
                "max_cvss": None,
                "max_epss": None,
                "kev_count": 0,
                "ransomware_count": 0,
            }

        cvss_scores = []
        epss_scores = []
        kev_count = 0
        ransomware_count = 0

        for details in vulns.values():
            if not isinstance(details, dict):
                continue

            if isinstance(details.get("cvss"), (int, float)):
                cvss_scores.append(details["cvss"])
            if isinstance(details.get("epss"), (int, float)):
                epss_scores.append(details["epss"])
            if details.get("kev") is True:
                kev_count += 1
            if details.get("ransomware_campaign") not in (None, "", "Unknown"):
                ransomware_count += 1

        return {
            "vulnerability_count": len(vulns),
            "max_cvss": max(cvss_scores) if cvss_scores else None,
            "max_epss": max(epss_scores) if epss_scores else None,
            "kev_count": kev_count,
            "ransomware_count": ransomware_count,
        }

    def extract_features(self, record: dict) -> dict:
        """Extract structured features from raw scan record."""
        http = record.get("http") or {}
        cloud = record.get("cloud") or {}
        tags = record.get("tags") or []

        ip_value = None
        if record.get("ip"):
            ip_int = record.get("ip")
            if isinstance(ip_int, int):
                ip_value = f"{(ip_int >> 24) & 0xff}.{(ip_int >> 16) & 0xff}.{(ip_int >> 8) & 0xff}.{ip_int & 0xff}"
            else:
                ip_value = str(ip_int)

        features = {
            "ip": ip_value,
            "port": record.get("port"),
            "hostname": record.get("hostnames", [None])[0] if record.get("hostnames") else None,
            "domain": record.get("domains", [None])[0] if record.get("domains") else None,
            "product": record.get("product"),
            "version": record.get("version"),
            "os": record.get("os"),
            "asn": record.get("asn"),
            "http_status": http.get("status"),
            "http_server": http.get("server"),
            "cloud_provider": cloud.get("provider"),
            "cloud_region": cloud.get("region"),
            "tags": tags,
        }

        vuln_features = self.extract_vulnerability_features(record.get("vulns"))
        features.update(vuln_features)
        return features

    def detect_signals(self, features: dict) -> List[SecuritySignal]:
        """Detect security signals from extracted features."""
        signals = []

        if "eol-product" in (features.get("tags") or []):
            signals.append(
                SecuritySignal(
                    name="eol_product",
                    severity=SignalSeverity.HIGH,
                    category="technology_risk",
                    evidence="Product is tagged as end-of-life",
                )
            )

        kev_count = features.get("kev_count", 0)
        if kev_count > 0:
            signals.append(
                SecuritySignal(
                    name="kev_vulnerability",
                    severity=SignalSeverity.CRITICAL,
                    category="vulnerability",
                    evidence=f"{kev_count} vulnerability(s) listed in CISA KEV",
                )
            )

        max_cvss = features.get("max_cvss")
        if max_cvss is not None:
            if max_cvss >= 9.0:
                severity = SignalSeverity.CRITICAL
            elif max_cvss >= 7.0:
                severity = SignalSeverity.HIGH
            else:
                severity = None

            if severity:
                signals.append(
                    SecuritySignal(
                        name="high_severity_vulnerability",
                        severity=severity,
                        category="vulnerability",
                        evidence=f"Maximum CVSS score: {max_cvss}",
                    )
                )

        max_epss = features.get("max_epss")
        if max_epss is not None and max_epss >= 0.5:
            signals.append(
                SecuritySignal(
                    name="high_exploitation_probability",
                    severity=SignalSeverity.HIGH,
                    category="vulnerability",
                    evidence=f"Maximum EPSS score: {max_epss:.2f}",
                )
            )

        ransomware_count = features.get("ransomware_count", 0)
        if ransomware_count > 0:
            signals.append(
                SecuritySignal(
                    name="ransomware_associated_vulnerability",
                    severity=SignalSeverity.CRITICAL,
                    category="vulnerability",
                    evidence=f"{ransomware_count} vulnerability(s) associated with ransomware campaigns",
                )
            )

        vulnerability_count = features.get("vulnerability_count", 0)
        if vulnerability_count >= 5:
            signals.append(
                SecuritySignal(
                    name="multiple_vulnerabilities",
                    severity=SignalSeverity.MEDIUM,
                    category="vulnerability",
                    evidence=f"{vulnerability_count} vulnerabilities detected",
                )
            )

        port = features.get("port")
        if port is not None and port not in {80, 443}:
            signals.append(
                SecuritySignal(
                    name="non_standard_exposed_port",
                    severity=SignalSeverity.LOW,
                    category="attack_surface",
                    evidence=f"Exposed port: {port}",
                )
            )

        return signals

    def build_accounts(self, records: List[dict]) -> Dict[str, Account]:
        with logger.span("aggregator.build_accounts", input_records_count=len(records)):
            accounts: Dict[str, Account] = {}
            signal_keys_by_account: Dict[str, Set[Tuple[str, str, str, str]]] = defaultdict(set)

            for record in records:
                features = self.extract_features(record)
                signals = self.detect_signals(features)
                account_keys = self.resolve_account_keys(record)

                if not account_keys:
                    continue

                asset_id = self.get_asset_id(features)

                for account_key in account_keys:
                    if account_key not in accounts:
                        accounts[account_key] = Account(
                            account_key=account_key,
                            domains=[],
                            assets=[],
                            ips=[],
                            hostnames=[],
                            ports=[],
                            products=[],
                            cloud_providers=[],
                            signals=[],
                        )

                    account = accounts[account_key]
                    domain = account_key.replace("domain:", "")

                    if domain not in account.domains:
                        account.domains.append(domain)

                    if asset_id:
                        asset_host = asset_id[2]
                        if not asset_host or asset_host == domain or asset_host.endswith("." + domain):
                            asset = Asset(ip=asset_id[0], port=asset_id[1], hostname=asset_host)
                            if asset not in account.assets:
                                account.assets.append(asset)

                    if features.get("ip") and features["ip"] not in account.ips:
                        account.ips.append(features["ip"])

                    if features.get("hostname"):
                        h = features["hostname"]
                        if h == domain or h.endswith("." + domain):
                            if h not in account.hostnames:
                                account.hostnames.append(h)

                    if features.get("port") is not None and features["port"] not in account.ports:
                        account.ports.append(features["port"])

                    if features.get("product") and features["product"] not in account.products:
                        account.products.append(features["product"])

                    if (
                        features.get("cloud_provider")
                        and features["cloud_provider"] not in account.cloud_providers
                    ):
                        account.cloud_providers.append(features["cloud_provider"])

                    for s in signals:
                        s_sev = s.severity if isinstance(s.severity, str) else s.severity.value
                        s_key = (s.name, s_sev, s.category, s.evidence)
                        if s_key not in signal_keys_by_account[account_key]:
                            signal_keys_by_account[account_key].add(s_key)
                            account.signals.append(s)

            logger.info("Accounts aggregated successfully", total_accounts=len(accounts), input_records=len(records))
            return accounts

    def load_accounts_from_jsonl(self, jsonl_path: str, limit: Optional[int] = None) -> Dict[str, Account]:
        with logger.span("aggregator.load_jsonl", path=jsonl_path, limit=limit):
            records = []
            with open(jsonl_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if limit and i >= limit:
                        break
                    try:
                        record = json.loads(line)
                        records.append(record)
                    except json.JSONDecodeError:
                        continue

            return self.build_accounts(records)


default_aggregator_service = AggregatorService()
detect_signals = default_aggregator_service.detect_signals
extract_features = default_aggregator_service.extract_features
build_accounts = default_aggregator_service.build_accounts
load_accounts_from_jsonl = default_aggregator_service.load_accounts_from_jsonl
resolve_account_keys = default_aggregator_service.resolve_account_keys

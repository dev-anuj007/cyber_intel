import ipaddress
from typing import Any, Dict, Optional

from src.services.aggregator.types import RecordFeatures, VulnerabilityFeatures


class FeatureExtractor:
    def extract_features(self, record: Dict[str, Any]) -> Dict[str, Any]:
        http = record.get("http") or {}
        cloud = record.get("cloud") or {}
        tags = record.get("tags") or []

        features: Dict[str, Any] = {
            "ip": self.format_ip(record.get("ip")),
            "port": record.get("port"),
            "hostname": (
                record.get("hostnames", [None])[0] if record.get("hostnames") else None
            ),
            "domain": (
                record.get("domains", [None])[0] if record.get("domains") else None
            ),
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

    def extract_record_features(self, record: Dict[str, Any]) -> RecordFeatures:
        feat_dict = self.extract_features(record)
        return RecordFeatures.model_validate(feat_dict)

    def extract_vulnerability_features(
        self, vulns: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
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
                cvss_scores.append(float(details["cvss"]))
            if isinstance(details.get("epss"), (int, float)):
                epss_scores.append(float(details["epss"]))
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

    def extract_typed_vulnerability_features(
        self, vulns: Optional[Dict[str, Any]]
    ) -> VulnerabilityFeatures:
        vuln_dict = self.extract_vulnerability_features(vulns)
        return VulnerabilityFeatures.model_validate(vuln_dict)

    @staticmethod
    def format_ip(ip_val: Any) -> Optional[str]:
        if not ip_val:
            return None
        if isinstance(ip_val, int):
            try:
                return str(ipaddress.IPv4Address(ip_val))
            except ValueError:
                return str(ip_val)
        return str(ip_val)

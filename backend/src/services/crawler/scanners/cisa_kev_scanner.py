import socket
import ssl
import httpx
from typing import List, Dict, Any, Optional, Set
from src.services.accounts.types import Asset, SecuritySignal, SignalSeverity
from src.services.aggregator.aggregator_service import normalize_domain
from src.services.crawler.scanners.base import IScanner, ScanResult
from src.services.logger import get_logger

logger = get_logger("crawler.scanners.cisa_kev")

# Embedded Top High-Risk Exploited Vulnerabilities from CISA KEV
CURATED_CISA_KEV_RULES = [
    {
        "cve": "CVE-2023-4966",
        "vendor": "Citrix",
        "product": "NetScaler / ADC",
        "name": "Citrix Bleed Sensitive Information Disclosure",
        "keywords": ["citrix", "netscaler", "nshttp"],
        "severity": SignalSeverity.CRITICAL,
        "due_date": "2023-10-23",
    },
    {
        "cve": "CVE-2023-46805",
        "vendor": "Ivanti",
        "product": "Connect Secure (ICS)",
        "name": "Ivanti Connect Secure Authentication Bypass",
        "keywords": ["ivanti", "connect secure", "pulse secure", "dana-na"],
        "severity": SignalSeverity.CRITICAL,
        "due_date": "2024-01-22",
    },
    {
        "cve": "CVE-2021-44228",
        "vendor": "Apache",
        "product": "Log4j",
        "name": "Apache Log4j Remote Code Execution (Log4Shell)",
        "keywords": ["log4j", "solr", "elasticsearch/7", "apache-solr"],
        "severity": SignalSeverity.CRITICAL,
        "due_date": "2021-12-24",
    },
    {
        "cve": "CVE-2023-22515",
        "vendor": "Atlassian",
        "product": "Confluence Data Center & Server",
        "name": "Atlassian Confluence Broken Access Control",
        "keywords": ["confluence", "atlassian.confluence"],
        "severity": SignalSeverity.CRITICAL,
        "due_date": "2023-10-10",
    },
    {
        "cve": "CVE-2022-1388",
        "vendor": "F5",
        "product": "BIG-IP",
        "name": "F5 BIG-IP iControl REST Authentication Bypass",
        "keywords": ["big-ip", "f5 networks", "icontrol"],
        "severity": SignalSeverity.CRITICAL,
        "due_date": "2022-05-31",
    },
    {
        "cve": "CVE-2021-26855",
        "vendor": "Microsoft",
        "product": "Exchange Server",
        "name": "Microsoft Exchange Server SSRF (Proxylogit)",
        "keywords": ["owa", "exchange", "microsoft-iis/10.0"],
        "severity": SignalSeverity.CRITICAL,
        "due_date": "2021-03-11",
    },
    {
        "cve": "CVE-2021-41773",
        "vendor": "Apache",
        "product": "HTTP Server 2.4.49 / 2.4.50",
        "name": "Apache HTTP Server Path Traversal and RCE",
        "keywords": ["apache/2.4.49", "apache/2.4.50", "apache/2.2"],
        "severity": SignalSeverity.HIGH,
        "due_date": "2021-11-03",
    },
]


class CisaKevScanner:
    scanner_type: str = "cisa_kev"
    display_name: str = "CISA KEV & Exploited CVE Threat Feed"
    description: str = "Correlates perimeter banners, technologies, and products against the official CISA Known Exploited Vulnerabilities catalog."

    def __init__(self, timeout: float = 2.0):
        self.timeout = timeout

    def scan(self, domain: str, options: Optional[Dict[str, Any]] = None) -> ScanResult:
        options = options or {}
        clean_domain = normalize_domain(domain)

        try:
            ip = socket.gethostbyname(clean_domain)
        except Exception:
            ip = "0.0.0.0"

        assets: List[Asset] = [Asset(ip=ip, port=443, hostname=clean_domain)]
        signals: List[SecuritySignal] = []
        products: Set[str] = set()
        cloud_providers: Set[str] = set()
        matched_cves: List[str] = []
        vulnerabilities: List[Dict[str, Any]] = []

        # 1. Grab HTTP & TLS banners
        all_text_fingerprints: List[str] = []
        with httpx.Client(verify=False, timeout=self.timeout, follow_redirects=True) as client:
            try:
                resp = client.get(f"https://{clean_domain}", headers={"User-Agent": "CISA-KEV-Threat-Audit/1.0"})
                headers_str = " ".join([f"{k}:{v}" for k, v in resp.headers.items()]).lower()
                all_text_fingerprints.append(headers_str)
                all_text_fingerprints.append(resp.text[:2000].lower())
                srv = resp.headers.get("server", "")
                if srv:
                    products.add(srv)
            except Exception:
                try:
                    resp = client.get(f"http://{clean_domain}", headers={"User-Agent": "CISA-KEV-Threat-Audit/1.0"})
                    headers_str = " ".join([f"{k}:{v}" for k, v in resp.headers.items()]).lower()
                    all_text_fingerprints.append(headers_str)
                except Exception:
                    pass

        joined_fingerprint = " ".join(all_text_fingerprints)

        # 2. Match against CISA KEV rules
        for rule in CURATED_CISA_KEV_RULES:
            if any(kw in joined_fingerprint for kw in rule["keywords"]):
                matched_cves.append(rule["cve"])
                signals.append(
                    SecuritySignal(
                        name=f"CISA KEV Alert: {rule['name']} ({rule['cve']})",
                        severity=rule["severity"],
                        category="cisa-kev",
                        evidence=f"Perimeter product matches CISA KEV signature for {rule['vendor']} {rule['product']}. Known exploited in the wild.",
                    )
                )
                vulnerabilities.append({
                    "id": rule["cve"],
                    "name": rule["name"],
                    "vendor": rule["vendor"],
                    "product": rule["product"],
                    "severity": rule["severity"].value.capitalize(),
                    "source": "CISA Known Exploited Vulnerabilities Catalog",
                })

        return ScanResult(
            domain=clean_domain,
            scanner_type=self.scanner_type,
            assets=assets,
            signals=signals,
            ips=[ip],
            hostnames=[clean_domain],
            ports=[443],
            products=list(products) or ["Cloud Service"],
            cloud_providers=list(cloud_providers) or ["External Host"],
            vulnerabilities=vulnerabilities,
            cves=matched_cves,
            metadata={
                "engine": "cisa_kev_threat_intel",
                "matched_cve_count": len(matched_cves),
                "cisa_rules_evaluated": len(CURATED_CISA_KEV_RULES),
            },
        )

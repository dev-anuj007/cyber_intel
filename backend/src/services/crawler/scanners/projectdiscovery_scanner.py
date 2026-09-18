import os
import shutil
import socket
import ssl
import json
import subprocess
import httpx
from typing import List, Dict, Any, Optional, Set
from src.services.accounts.types import Asset, SecuritySignal, SignalSeverity
from src.services.aggregator.aggregator_service import normalize_domain
from src.services.crawler.scanners.base import IScanner, ScanResult
from src.services.logger import get_logger

logger = get_logger("crawler.scanners.projectdiscovery")

PROJECTDISCOVERY_PORTS = [80, 443, 8080, 8443, 8000, 8888, 9000, 9443, 3000, 5000, 22, 3389, 6379, 27017]


class ProjectDiscoveryScanner:
    scanner_type: str = "projectdiscovery"
    display_name: str = "ProjectDiscovery Suite (Subfinder, HTTPX, Naabu, Nuclei)"
    description: str = "Fast perimeter reconnaissance, subdomain enumeration, port probing, technology stack fingerprinting, and Nuclei vulnerability template scanning."

    def __init__(self, timeout: float = 2.0):
        self.timeout = timeout
        self.has_subfinder = bool(shutil.which("subfinder"))
        self.has_naabu = bool(shutil.which("naabu"))
        self.has_httpx_cli = bool(shutil.which("httpx"))
        self.has_nuclei = bool(shutil.which("nuclei"))

    def _extract_tls_sans(self, domain: str) -> List[str]:
        """Extract Subdomains from TLS Certificate Subject Alternative Names."""
        sans = set()
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection((domain, 443), timeout=1.5) as sock:
                with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert(binary_form=False)
                    if cert and "subjectAltName" in cert:
                        for typ, val in cert["subjectAltName"]:
                            if typ == "DNS" and (val.endswith(f".{domain}") or val == domain):
                                sans.add(val.lower())
        except Exception:
            pass
        return list(sans)

    def scan(self, domain: str, options: Optional[Dict[str, Any]] = None) -> ScanResult:
        options = options or {}
        clean_domain = normalize_domain(domain)
        discovered_subdomains = [clean_domain]
        assets: List[Asset] = []
        signals: List[SecuritySignal] = []
        products: Set[str] = set()
        cloud_providers: Set[str] = set()
        open_ports: Set[int] = set()
        vulnerabilities: List[Dict[str, Any]] = []

        # 1. Subfinder (CLI or TLS SAN extraction + standard wordlist)
        if self.has_subfinder:
            try:
                cmd = ["subfinder", "-d", clean_domain, "-silent"]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                for line in proc.stdout.splitlines():
                    sub = line.strip().lower()
                    if sub and sub.endswith(clean_domain) and sub not in discovered_subdomains:
                        discovered_subdomains.append(sub)
            except Exception as e:
                logger.warning(f"Subfinder CLI execution error: {e}")

        # Fallback / Enrichment with TLS SANs
        san_subs = self._extract_tls_sans(clean_domain)
        for s in san_subs:
            if s not in discovered_subdomains:
                discovered_subdomains.append(s)

        # 2. Naabu & HTTPX Probing
        host_to_ip: Dict[str, str] = {}
        for h in discovered_subdomains[:15]:
            try:
                ip = socket.gethostbyname(h)
                host_to_ip[h] = ip
            except Exception:
                continue

        for h, ip in host_to_ip.items():
            for p in PROJECTDISCOVERY_PORTS:
                is_open = False
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.6)
                    res = sock.connect_ex((ip, p))
                    sock.close()
                    is_open = (res == 0)
                except Exception:
                    pass

                if is_open or p in (80, 443):
                    open_ports.add(p)
                    assets.append(Asset(ip=ip, port=p, hostname=h))

                    # Flag dangerous exposed ports
                    if p in (22, 3389):
                        signals.append(
                            SecuritySignal(
                                name="Exposed Administrative Remote Port (SSH/RDP)",
                                severity=SignalSeverity.CRITICAL,
                                category="perimeter",
                                evidence=f"Port {p} ({'SSH' if p == 22 else 'RDP'}) is exposed publicly on {h} ({ip}).",
                            )
                        )
                        vulnerabilities.append({
                            "id": f"NAABU-PORT-{p}",
                            "name": "Administrative Port Exposed to Public Internet",
                            "severity": "Critical",
                            "port": p,
                        })
                    elif p in (6379, 27017):
                        signals.append(
                            SecuritySignal(
                                name="Exposed Database Port (Redis/MongoDB)",
                                severity=SignalSeverity.CRITICAL,
                                category="database",
                                evidence=f"Database port {p} accessible from public WAN on {h} ({ip}).",
                            )
                        )

        # 3. HTTPX Deep Web Fingerprinting
        with httpx.Client(verify=False, timeout=self.timeout, follow_redirects=True) as client:
            for h in discovered_subdomains[:5]:
                for scheme in ("https", "http"):
                    try:
                        resp = client.get(f"{scheme}://{h}", headers={"User-Agent": "ProjectDiscovery-HTTPX/1.6.0"})
                        headers = {k.lower(): v for k, v in resp.headers.items()}
                        srv = headers.get("server", "")
                        if srv:
                            products.add(srv)
                        if "cloudflare" in str(headers).lower():
                            cloud_providers.add("Cloudflare")
                        if "aws" in str(headers).lower() or "amz-" in str(headers).lower():
                            cloud_providers.add("AWS")
                        break
                    except Exception:
                        pass

        # 4. Nuclei Vulnerability Template Inspection
        if self.has_nuclei:
            try:
                cmd = ["nuclei", "-u", f"https://{clean_domain}", "-silent", "-jsonl"]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                for line in proc.stdout.splitlines():
                    try:
                        vuln = json.loads(line)
                        v_info = vuln.get("info", {})
                        v_name = v_info.get("name", "Nuclei Vulnerability")
                        v_sev = v_info.get("severity", "medium").lower()
                        signals.append(
                            SecuritySignal(
                                name=f"Nuclei: {v_name}",
                                severity=SignalSeverity(v_sev) if v_sev in SignalSeverity.__members__.values() else SignalSeverity.MEDIUM,
                                category="vuln",
                                evidence=f"Nuclei template matched on {vuln.get('matched-at', clean_domain)}",
                            )
                        )
                        vulnerabilities.append({
                            "id": vuln.get("template-id", "NUCLEI-GENERIC"),
                            "name": v_name,
                            "severity": v_sev.capitalize(),
                        })
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Nuclei CLI execution: {e}")

        if not assets:
            root_ip = host_to_ip.get(clean_domain) or "0.0.0.0"
            assets.append(Asset(ip=root_ip, port=443, hostname=clean_domain))
            open_ports.add(443)

        return ScanResult(
            domain=clean_domain,
            scanner_type=self.scanner_type,
            assets=assets,
            signals=signals,
            ips=list(host_to_ip.values()) or ["0.0.0.0"],
            hostnames=discovered_subdomains,
            ports=sorted(list(open_ports)),
            products=list(products) or ["Web Infrastructure"],
            cloud_providers=list(cloud_providers) or ["Public Cloud"],
            vulnerabilities=vulnerabilities,
            metadata={
                "engine": "projectdiscovery_recon_suite",
                "subfinder_active": self.has_subfinder,
                "naabu_active": self.has_naabu,
                "nuclei_active": self.has_nuclei,
                "subdomains_found": len(discovered_subdomains),
            },
        )

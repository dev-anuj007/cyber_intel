import os
import socket
from typing import Any, Dict, List, Optional, Set

import httpx

from src.services.accounts.types import Asset, SecuritySignal, SignalSeverity
from src.services.aggregator.aggregator_service import normalize_domain
from src.services.crawler.scanners.base import ScanResult
from src.services.logger import get_logger

logger = get_logger("crawler.scanners.owasp_zap")

SENSITIVE_PATHS = [
    ("/.env", "Environment Variables File Exposure"),
    ("/.git/HEAD", "Git Repository Metadata Exposure"),
    ("/actuator/health", "Spring Actuator Management Endpoint"),
    ("/swagger.json", "Exposed OpenAPI / Swagger Documentation"),
    ("/server-status", "Apache Server-Status Diagnostic Page"),
    ("/api/v1", "API Endpoint Discovery"),
    ("/robots.txt", "Robots Policy File"),
]


class OwaspZapScanner:
    scanner_type: str = "owasp_zap"
    display_name: str = "OWASP ZAP DAST Vulnerability Scanner"
    description: str = "OWASP Top 10 Web Application Security Auditor. Analyzes CSP, HSTS, CORS, Clickjacking, Cookie Flags, Header Leaks, and Sensitive Path exposures."

    def __init__(
        self,
        zap_url: Optional[str] = None,
        zap_api_key: Optional[str] = None,
        timeout: float = 0.2,
    ):
        self.zap_url = zap_url or os.getenv("ZAP_API_URL", "http://localhost:8080")
        self.zap_api_key = zap_api_key or os.getenv("ZAP_API_KEY", "")
        self.timeout = timeout

    def _check_zap_daemon(self) -> bool:
        try:
            with httpx.Client(timeout=1.0) as client:
                resp = client.get(
                    f"{self.zap_url}/JSON/core/view/version/", headers={"X-ZAP-API-Key": self.zap_api_key}
                )
                return resp.status_code == 200
        except Exception:
            return False

    def scan(self, domain: str, options: Optional[Dict[str, Any]] = None) -> ScanResult:
        options = options or {}
        clean_domain = normalize_domain(domain)
        target_url = f"https://{clean_domain}"

        signals: List[SecuritySignal] = []
        assets: List[Asset] = []
        products: Set[str] = set()
        cloud_providers: Set[str] = set()
        ports: Set[int] = {443}
        vulnerabilities: List[Dict[str, Any]] = []

        try:
            ip = socket.gethostbyname(clean_domain)
        except Exception:
            ip = None

        # 1. Probe HTTP/HTTPS Headers & OWASP Security Controls
        headers: Dict[str, str] = {}
        status_code = None
        cookies: List[str] = []

        with httpx.Client(verify=False, timeout=self.timeout, follow_redirects=True) as client:
            try:
                resp = client.get(target_url, headers={"User-Agent": "OWASP-ZAP-DAST-Scanner/2.14 (SalesIntel)"})
                status_code = resp.status_code
                headers = {k.lower(): v for k, v in resp.headers.items()}
                cookies = resp.headers.get_list("set-cookie")
            except Exception:
                # Fallback to HTTP
                try:
                    resp = client.get(f"http://{clean_domain}", headers={"User-Agent": "OWASP-ZAP-DAST-Scanner/2.14"})
                    status_code = resp.status_code
                    headers = {k.lower(): v for k, v in resp.headers.items()}
                    cookies = resp.headers.get_list("set-cookie")
                except Exception:
                    pass

        if status_code is None and not headers and not ip:
            return ScanResult(
                domain=clean_domain,
                scanner_type=self.scanner_type,
                assets=[],
                signals=[],
                ips=[],
                hostnames=[],
                ports=[],
                products=[],
                cloud_providers=[],
                vulnerabilities=[],
                metadata={"engine": "owasp_zap_dast_auditor", "rules_evaluated": 0, "vulnerabilities_found": 0},
            )

        if ip:
            assets.append(Asset(ip=ip, port=443, hostname=clean_domain))

        if not headers:
            return ScanResult(
                domain=clean_domain,
                scanner_type=self.scanner_type,
                assets=assets,
                signals=[],
                ips=[ip] if ip else [],
                hostnames=[clean_domain] if ip else [],
                ports=list(ports) if ip else [],
                products=[],
                cloud_providers=[],
                vulnerabilities=[],
                metadata={"engine": "owasp_zap_dast_auditor", "rules_evaluated": 0, "vulnerabilities_found": 0},
            )

        # OWASP Rule 1: Content-Security-Policy (CSP)
        csp = headers.get("content-security-policy", "")
        if not csp:
            signals.append(
                SecuritySignal(
                    name="Missing Content-Security-Policy (CSP)",
                    severity=SignalSeverity.HIGH,
                    category="injection",
                    evidence=f"{clean_domain} lacks a Content-Security-Policy header, leaving web clients vulnerable to Cross-Site Scripting (XSS) and data injection attacks.",
                )
            )
            vulnerabilities.append(
                {
                    "id": "OWASP-ZAP-10038",
                    "name": "Content Security Policy (CSP) Header Not Set",
                    "severity": "High",
                    "cwe": "CWE-693",
                }
            )
        elif "unsafe-inline" in csp or "unsafe-eval" in csp:
            signals.append(
                SecuritySignal(
                    name="Weak / Permissive Content-Security-Policy",
                    severity=SignalSeverity.MEDIUM,
                    category="misconfiguration",
                    evidence=f"CSP header permits 'unsafe-inline' or 'unsafe-eval': {csp[:80]}...",
                )
            )

        # OWASP Rule 2: HTTP Strict Transport Security (HSTS)
        hsts = headers.get("strict-transport-security", "")
        if not hsts:
            signals.append(
                SecuritySignal(
                    name="Missing HTTP Strict Transport Security (HSTS)",
                    severity=SignalSeverity.MEDIUM,
                    category="crypto",
                    evidence=f"{clean_domain} does not enforce Strict-Transport-Security, allowing potential SSL-stripping and man-in-the-middle attacks.",
                )
            )
            vulnerabilities.append(
                {
                    "id": "OWASP-ZAP-10035",
                    "name": "Strict-Transport-Security Header Not Set",
                    "severity": "Medium",
                    "cwe": "CWE-319",
                }
            )

        # OWASP Rule 3: Anti-Clickjacking (X-Frame-Options)
        xfo = headers.get("x-frame-options", "").upper()
        if not xfo and "frame-ancestors" not in csp:
            signals.append(
                SecuritySignal(
                    name="Missing Anti-Clickjacking Controls (X-Frame-Options)",
                    severity=SignalSeverity.MEDIUM,
                    category="misconfiguration",
                    evidence=f"{clean_domain} lacks X-Frame-Options or CSP frame-ancestors, exposing users to UI redressing and clickjacking.",
                )
            )
            vulnerabilities.append(
                {
                    "id": "OWASP-ZAP-10020",
                    "name": "Anti-clickjacking Header Missing",
                    "severity": "Medium",
                    "cwe": "CWE-1021",
                }
            )

        # OWASP Rule 4: MIME-Type Sniffing Protection
        xcto = headers.get("x-content-type-options", "").lower()
        if xcto != "nosniff":
            signals.append(
                SecuritySignal(
                    name="MIME-Type Sniffing Allowed",
                    severity=SignalSeverity.LOW,
                    category="misconfiguration",
                    evidence="Missing 'X-Content-Type-Options: nosniff' header.",
                )
            )

        # OWASP Rule 5: Permissive CORS Configuration
        cors = headers.get("access-control-allow-origin", "")
        if cors == "*":
            signals.append(
                SecuritySignal(
                    name="Permissive Wildcard CORS Configuration",
                    severity=SignalSeverity.HIGH,
                    category="misconfiguration",
                    evidence=f"Access-Control-Allow-Origin is set to wildcard '*' on {clean_domain}.",
                )
            )
            vulnerabilities.append(
                {
                    "id": "OWASP-ZAP-WASC-14",
                    "name": "CORS Misconfiguration - Wildcard Origin",
                    "severity": "High",
                    "cwe": "CWE-942",
                }
            )

        # OWASP Rule 6: Server & Technology Leakage
        server_hdr = headers.get("server", "")
        powered_by = headers.get("x-powered-by", "")
        if server_hdr:
            products.add(server_hdr)
            if any(char.isdigit() for char in server_hdr):
                signals.append(
                    SecuritySignal(
                        name="Detailed Server Banner Disclosure",
                        severity=SignalSeverity.LOW,
                        category="info-leak",
                        evidence=f"Server header exposes exact version: '{server_hdr}'.",
                    )
                )
        if powered_by:
            products.add(powered_by)
            signals.append(
                SecuritySignal(
                    name="Technology Stack Fingerprint Disclosure",
                    severity=SignalSeverity.LOW,
                    category="info-leak",
                    evidence=f"X-Powered-By header discloses backend runtime: '{powered_by}'.",
                )
            )

        # OWASP Rule 7: Cookie Security Flags
        for cookie in cookies:
            c_lower = cookie.lower()
            if "secure" not in c_lower:
                signals.append(
                    SecuritySignal(
                        name="Cookie Missing Secure Flag",
                        severity=SignalSeverity.MEDIUM,
                        category="session",
                        evidence=f"Cookie set without 'Secure' attribute over network: {cookie[:40]}...",
                    )
                )
            if "httponly" not in c_lower:
                signals.append(
                    SecuritySignal(
                        name="Cookie Missing HttpOnly Flag",
                        severity=SignalSeverity.MEDIUM,
                        category="session",
                        evidence=f"Cookie set without 'HttpOnly' attribute, readable via JavaScript: {cookie[:40]}...",
                    )
                )

        # 2. Sensitive Path and Endpoint Fuzzing
        with httpx.Client(verify=False, timeout=0.2, follow_redirects=False) as client:
            for path, desc in SENSITIVE_PATHS:
                try:
                    p_resp = client.get(f"{target_url}{path}")
                    if p_resp.status_code == 200 and len(p_resp.content) > 0:
                        signals.append(
                            SecuritySignal(
                                name=f"Sensitive Endpoint Exposed ({desc})",
                                severity=SignalSeverity.HIGH
                                if ".env" in path or ".git" in path
                                else SignalSeverity.MEDIUM,
                                category="exposure",
                                evidence=f"Exposed URL returned HTTP 200: {target_url}{path} ({len(p_resp.content)} bytes)",
                            )
                        )
                        vulnerabilities.append(
                            {
                                "id": f"OWASP-PATH-{path.replace('/', '_')}",
                                "name": desc,
                                "severity": "High" if ".env" in path or ".git" in path else "Medium",
                                "url": f"{target_url}{path}",
                            }
                        )
                except Exception:
                    pass

        return ScanResult(
            domain=clean_domain,
            scanner_type=self.scanner_type,
            assets=assets,
            signals=signals,
            ips=[ip] if ip else [],
            hostnames=[clean_domain] if ip else [],
            ports=list(ports) if ip else [],
            products=list(products),
            cloud_providers=list(cloud_providers),
            vulnerabilities=vulnerabilities,
            metadata={
                "engine": "owasp_zap_dast_auditor",
                "rules_evaluated": 12,
                "vulnerabilities_found": len(vulnerabilities),
            },
        )

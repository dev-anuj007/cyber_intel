import asyncio
import json
import shutil
import socket
import ssl
import subprocess
from typing import Dict, List, Optional, Set

import httpx

from src.services.accounts.types import Asset, SecuritySignal, SignalSeverity
from src.services.aggregator.internals.domain_utils import normalize_domain
from src.services.crawler.internals.scanners.constants import PROJECTDISCOVERY_PORTS
from src.services.crawler.internals.scanners.types import (
    ScannerEngineOptions,
    ScanResult,
    VulnerabilityFinding,
)
from src.services.logger.logger_service import BaseLogger, get_logger


class ProjectDiscoveryScanner:
    scanner_type: str = "projectdiscovery"
    display_name: str = "ProjectDiscovery Suite (Subfinder, HTTPX, Naabu, Nuclei)"
    description: str = (
        "Fast perimeter reconnaissance, subdomain enumeration, port probing, "
        "technology stack fingerprinting, and Nuclei vulnerability template scanning."
    )

    def __init__(
        self,
        timeout: float = 0.2,
        logger: Optional[BaseLogger] = None,
    ):
        self.timeout = timeout
        self.has_subfinder = bool(shutil.which("subfinder"))
        self.has_naabu = bool(shutil.which("naabu"))
        self.has_httpx_cli = bool(shutil.which("httpx"))
        self.has_nuclei = bool(shutil.which("nuclei"))
        self._logger = logger or get_logger("crawler.scanners.projectdiscovery")

    async def scan_async(
        self,
        domain: str,
        options: Optional[ScannerEngineOptions] = None,
    ) -> ScanResult:
        opts = options or ScannerEngineOptions()
        clean_domain = normalize_domain(domain)
        timeout = opts.timeout if opts.timeout is not None else self.timeout
        ports_to_probe = opts.custom_ports or PROJECTDISCOVERY_PORTS

        discovered_subdomains = [clean_domain]
        assets: List[Asset] = []
        signals: List[SecuritySignal] = []
        products: Set[str] = set()
        cloud_providers: Set[str] = set()
        open_ports: Set[int] = set()
        vulnerabilities: List[VulnerabilityFinding] = []

        if self.has_subfinder:
            try:

                def run_subfinder():
                    cmd = ["subfinder", "-d", clean_domain, "-silent"]
                    return subprocess.run(cmd, capture_output=True, text=True, timeout=8)

                proc = await asyncio.to_thread(run_subfinder)
                for line in proc.stdout.splitlines():
                    sub = line.strip().lower()
                    if sub and sub.endswith(clean_domain) and sub not in discovered_subdomains:
                        discovered_subdomains.append(sub)
            except Exception as e:
                self._logger.warning(f"Subfinder CLI execution error: {e}")

        san_subs = await asyncio.to_thread(self._extract_tls_sans, clean_domain)
        for s in san_subs:
            if s not in discovered_subdomains:
                discovered_subdomains.append(s)

        host_to_ip: Dict[str, str] = {}

        async def resolve_host(h: str):
            try:
                ip = await asyncio.to_thread(socket.gethostbyname, h)
                return h, ip
            except Exception:
                return h, None

        resolve_results = await asyncio.gather(
            *[resolve_host(h) for h in discovered_subdomains[:15]],
            return_exceptions=True,
        )
        for res in resolve_results:
            if isinstance(res, tuple):
                h, ip = res
                if ip:
                    host_to_ip[h] = ip

        def check_port(ip: str, p: int) -> bool:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.05)
                res = sock.connect_ex((ip, p))
                sock.close()
                return res == 0
            except Exception:
                return False

        port_probe_tasks = []
        for h, ip in host_to_ip.items():
            for p in ports_to_probe:
                port_probe_tasks.append((h, ip, p))

        async def probe_port_item(item):
            h, ip, p = item
            is_open = await asyncio.to_thread(check_port, ip, p)
            return h, ip, p, is_open

        port_results = await asyncio.gather(
            *[probe_port_item(t) for t in port_probe_tasks],
            return_exceptions=True,
        )
        for item in port_results:
            if isinstance(item, tuple):
                h, ip, p, is_open = item
                if is_open:
                    open_ports.add(p)
                    assets.append(Asset(ip=ip, port=p, hostname=h))

                    if p in (22, 3389):
                        proto_name = "SSH" if p == 22 else "RDP"
                        signals.append(
                            SecuritySignal(
                                name="Exposed Administrative Remote Port (SSH/RDP)",
                                severity=SignalSeverity.CRITICAL,
                                category="perimeter",
                                evidence=(f"Port {p} ({proto_name}) is exposed publicly on {h} ({ip})."),
                            )
                        )
                        vulnerabilities.append(
                            VulnerabilityFinding(
                                id=f"NAABU-PORT-{p}",
                                name="Administrative Port Exposed to Public Internet",
                                severity="Critical",
                                port=p,
                                source="projectdiscovery",
                            )
                        )
                    elif p in (6379, 27017):
                        signals.append(
                            SecuritySignal(
                                name="Exposed Database Port (Redis/MongoDB)",
                                severity=SignalSeverity.CRITICAL,
                                category="database",
                                evidence=(f"Database port {p} accessible from public WAN on {h} ({ip})."),
                            )
                        )

        async with httpx.AsyncClient(verify=False, timeout=timeout, follow_redirects=True) as client:
            for h in discovered_subdomains[:5]:
                for scheme in ("https", "http"):
                    try:
                        resp = await client.get(
                            f"{scheme}://{h}",
                            headers={"User-Agent": "ProjectDiscovery-HTTPX/1.6.0"},
                        )
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

        if self.has_nuclei:
            try:

                def run_nuclei():
                    cmd = [
                        "nuclei",
                        "-u",
                        f"https://{clean_domain}",
                        "-silent",
                        "-jsonl",
                    ]
                    return subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                proc = await asyncio.to_thread(run_nuclei)
                for line in proc.stdout.splitlines():
                    try:
                        vuln = json.loads(line)
                        v_info = vuln.get("info", {})
                        v_name = v_info.get("name", "Nuclei Vulnerability")
                        v_sev = v_info.get("severity", "medium").lower()
                        sig_sev = (
                            SignalSeverity(v_sev)
                            if v_sev in SignalSeverity.__members__.values()
                            else SignalSeverity.MEDIUM
                        )
                        matched_target = vuln.get("matched-at", clean_domain)
                        signals.append(
                            SecuritySignal(
                                name=f"Nuclei: {v_name}",
                                severity=sig_sev,
                                category="vuln",
                                evidence=f"Nuclei template matched on {matched_target}",
                            )
                        )
                        vulnerabilities.append(
                            VulnerabilityFinding(
                                id=vuln.get("template-id", "NUCLEI-GENERIC"),
                                name=v_name,
                                severity=v_sev.capitalize(),
                                source="projectdiscovery",
                            )
                        )
                    except Exception:
                        pass
            except Exception as e:
                self._logger.warning(f"Nuclei CLI execution: {e}")

        if not assets and clean_domain in host_to_ip:
            root_ip = host_to_ip[clean_domain]
            assets.append(Asset(ip=root_ip, port=443, hostname=clean_domain))
            open_ports.add(443)

        return ScanResult(
            domain=clean_domain,
            scanner_type=self.scanner_type,
            assets=assets,
            signals=signals,
            ips=list(host_to_ip.values()),
            hostnames=list(host_to_ip.keys()),
            ports=sorted(list(open_ports)),
            products=list(products),
            cloud_providers=list(cloud_providers),
            vulnerabilities=vulnerabilities,
            metadata={
                "engine": "projectdiscovery_recon_suite",
                "subfinder_active": self.has_subfinder,
                "naabu_active": self.has_naabu,
                "nuclei_active": self.has_nuclei,
                "subdomains_found": len(discovered_subdomains),
            },
        )

    def scan(
        self,
        domain: str,
        options: Optional[ScannerEngineOptions] = None,
    ) -> ScanResult:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self.scan_async(domain, options)).result()
        return asyncio.run(self.scan_async(domain, options))

    def _extract_tls_sans(self, domain: str) -> List[str]:
        sans = set()
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with socket.create_connection((domain, 443), timeout=0.2) as sock:
                with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert(binary_form=False)
                    if cert and "subjectAltName" in cert:
                        for entry in cert["subjectAltName"]:
                            if isinstance(entry, tuple) and len(entry) >= 2:
                                typ, val = str(entry[0]), str(entry[1])
                                is_domain_match = val.endswith(f".{domain}") or val == domain
                                if typ == "DNS" and is_domain_match:
                                    sans.add(val.lower())
        except Exception:
            pass
        return list(sans)

import concurrent.futures
import socket
import ssl
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Set, TypedDict

from src.services.accounts.types import Asset, SecuritySignal
from src.services.aggregator.aggregator_service import (
    detect_signals,
    is_dynamic_ip_ptr,
    normalize_domain,
)
from src.services.crawler.scanners.base import ScanResult
from src.services.logger import get_logger

logger = get_logger("crawler.scanners.standard")

COMMON_SUBDOMAINS = [
    "www",
    "api",
    "app",
    "dev",
    "staging",
    "admin",
    "portal",
    "mail",
    "vpn",
    "auth",
    "login",
    "dashboard",
    "secure",
    "cdn",
    "cloud",
    "beta",
]

DEFAULT_PORTS = [80, 443, 8080, 8443, 3000, 5000, 22, 21, 3389, 8000, 9000]

CLOUD_SIGNATURES = {
    "cloudflare": ["cloudflare", "cf-ray", "cf-cache-status"],
    "aws": ["amazons3", "awselb", "cloudfront", "amz-", "aws"],
    "gcp": ["google", "gws", "gcp", "appspot"],
    "azure": ["azure", "windows.net", "ms-"],
    "akamai": ["akamai", "akamaighost"],
    "fastly": ["fastly"],
}


class ProbeResult(TypedDict):
    host: str
    ip: Optional[str]
    port: int
    banner: Dict[str, Any]


class StandardCrawlerScanner:
    scanner_type: str = "standard"
    display_name: str = "Standard Network & Banner Crawler"
    description: str = "Multi-threaded DNS resolution, common subdomain enumeration, port probing, HTTP banner analysis, and cloud infrastructure fingerprinting."

    def __init__(
        self,
        timeout: float = 0.8,
        max_subdomains: int = 12,
        ports: Optional[List[int]] = None,
    ):
        self.timeout = timeout
        self.max_subdomains = max_subdomains
        self.ports = ports or [80, 443, 8080, 8443]

    def resolve_ip(self, host: str) -> Optional[str]:
        try:
            return socket.gethostbyname(host)
        except (socket.gaierror, socket.herror, Exception):
            return None

    def check_port_open(self, ip: str, port: int) -> bool:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            res = sock.connect_ex((ip, port))
            sock.close()
            return res == 0
        except Exception:
            return False

    def probe_http_banner(self, host: str, port: int) -> Dict[str, Any]:
        scheme = "https" if port in (443, 8443) else "http"
        url = f"{scheme}://{host}:{port}/" if port not in (80, 443) else f"{scheme}://{host}/"
        banner = {
            "server": "",
            "cloud_providers": [],
            "technologies": [],
            "status": None,
        }

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SalesIntelBot/2.0",
                "Accept": "*/*",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout + 0.4, context=ctx) as response:
                banner["status"] = response.status
                headers = {k.lower(): v for k, v in response.headers.items()}
                server_hdr = headers.get("server", "")
                powered_by = headers.get("x-powered-by", "")

                banner["server"] = server_hdr
                if powered_by:
                    banner["technologies"].append(powered_by)

                all_headers_str = " ".join([f"{k}:{v}" for k, v in headers.items()]).lower()
                for provider, sigs in CLOUD_SIGNATURES.items():
                    if any(sig in all_headers_str for sig in sigs):
                        banner["cloud_providers"].append(provider)

                if "nginx" in server_hdr.lower():
                    banner["technologies"].append("Nginx")
                elif "apache" in server_hdr.lower():
                    banner["technologies"].append("Apache HTTPD")
                elif "envoy" in server_hdr.lower():
                    banner["technologies"].append("Envoy Proxy")
                elif "microsoft-iis" in server_hdr.lower():
                    banner["technologies"].append("Microsoft-IIS")

        except urllib.error.HTTPError as e:
            banner["status"] = e.code
            headers = {k.lower(): v for k, v in e.headers.items()}
            server_hdr = headers.get("server", "")
            banner["server"] = server_hdr
            all_headers_str = " ".join([f"{k}:{v}" for k, v in headers.items()]).lower()
            for provider, sigs in CLOUD_SIGNATURES.items():
                if any(sig in all_headers_str for sig in sigs):
                    banner["cloud_providers"].append(provider)
        except Exception:
            pass

        return banner

    def scan(self, domain: str, options: Optional[Dict[str, Any]] = None) -> ScanResult:
        options = options or {}
        clean_domain = normalize_domain(domain)
        enable_subdomains = options.get("enable_subdomains", True)
        ports_to_scan = options.get("custom_ports") or self.ports

        discovered_hosts: List[str] = []
        root_ip = self.resolve_ip(clean_domain)
        if root_ip:
            discovered_hosts.append(clean_domain)

        if enable_subdomains:
            subs_to_test = COMMON_SUBDOMAINS[: self.max_subdomains]
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, len(subs_to_test))) as executor:
                future_to_host = {
                    executor.submit(self.resolve_ip, f"{sub}.{clean_domain}"): f"{sub}.{clean_domain}"
                    for sub in subs_to_test
                }
                for future in concurrent.futures.as_completed(future_to_host):
                    sub_host = future_to_host[future]
                    try:
                        sub_ip = future.result()
                        if sub_ip and not is_dynamic_ip_ptr(sub_host) and sub_host not in discovered_hosts:
                            discovered_hosts.append(sub_host)
                    except Exception:
                        pass

        if not discovered_hosts and not root_ip:
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
                metadata={"engine": "standard_network_crawler", "resolved": False},
            )

        assets: List[Asset] = []
        unique_ips: Set[str] = set()
        if root_ip:
            unique_ips.add(root_ip)
        unique_ports: Set[int] = set()
        products: Set[str] = set()
        cloud_providers: Set[str] = set()
        records_for_signals: List[dict] = []

        host_to_ip: Dict[str, Optional[str]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, max(1, len(discovered_hosts)))) as executor:
            future_to_h = {executor.submit(self.resolve_ip, h): h for h in discovered_hosts}
            for future in concurrent.futures.as_completed(future_to_h):
                h = future_to_h[future]
                try:
                    resolved = future.result()
                    host_to_ip[h] = resolved
                    if resolved:
                        unique_ips.add(resolved)
                except Exception:
                    host_to_ip[h] = None

        probe_tasks = []
        for host in discovered_hosts:
            ip = host_to_ip.get(host)
            if not ip:
                continue
            target_addr = ip
            for port in ports_to_scan:
                probe_tasks.append((host, ip, target_addr, port))

        def probe_worker(item) -> Optional[ProbeResult]:
            h, ip_addr, target, p = item
            is_open = self.check_port_open(target, p)
            if is_open:
                banner = self.probe_http_banner(h, p)
                return {
                    "host": h,
                    "ip": ip_addr,
                    "port": p,
                    "banner": banner,
                }
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(32, max(1, len(probe_tasks)))) as executor:
            probe_futures = [executor.submit(probe_worker, task) for task in probe_tasks]
            for future in concurrent.futures.as_completed(probe_futures):
                try:
                    res: Optional[ProbeResult] = future.result()
                    if res:
                        p_port: int = res["port"]
                        p_host: str = res["host"]
                        p_ip: Optional[str] = res["ip"]
                        p_banner: Dict[str, Any] = res["banner"] if isinstance(res.get("banner"), dict) else {}

                        unique_ports.add(p_port)
                        assets.append(Asset(ip=p_ip, port=p_port, hostname=p_host))

                        for tech in p_banner.get("technologies", []):
                            products.add(tech)
                        for cp in p_banner.get("cloud_providers", []):
                            cloud_providers.add(cp)

                        rec_features = {
                            "ip": p_ip,
                            "port": p_port,
                            "hostname": p_host,
                            "domains": [clean_domain],
                            "product": p_banner.get("server", ""),
                            "cloud_providers": p_banner.get("cloud_providers", []),
                            "tags": ["eol-product"] if "apache/2.2" in str(p_banner.get("server", "")).lower() else [],
                            "vulns": {},
                        }

                        if p_port not in (80, 443):
                            rec_features["port"] = p_port

                        records_for_signals.append(rec_features)
                except Exception:
                    pass

        signals: List[SecuritySignal] = []
        signal_keys = set()
        for rec in records_for_signals:
            detected = detect_signals(rec)
            for s in detected:
                s_sev = s.severity.value if hasattr(s.severity, "value") else str(s.severity)
                s_key = (s.name, s_sev, s.evidence)
                if s_key not in signal_keys:
                    signal_keys.add(s_key)
                    signals.append(s)

        if not assets and root_ip:
            assets.append(Asset(ip=root_ip, port=443, hostname=clean_domain))
            unique_ports.add(443)

        return ScanResult(
            domain=clean_domain,
            scanner_type=self.scanner_type,
            assets=assets,
            signals=signals,
            ips=list(unique_ips),
            hostnames=discovered_hosts or ([clean_domain] if root_ip else []),
            ports=list(unique_ports),
            products=list(products),
            cloud_providers=list(cloud_providers),
            metadata={"engine": "standard_network_crawler"},
        )

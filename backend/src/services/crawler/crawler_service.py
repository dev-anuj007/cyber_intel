import socket
import ssl
import time
import urllib.request
import urllib.error
import concurrent.futures
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Callable

from src.services.accounts.types import Account, Asset, SecuritySignal
from src.services.aggregator.aggregator_service import (
    detect_signals,
    is_dynamic_ip_ptr,
    normalize_domain,
)
from src.services.crawler.types import (
    ICrawlerService,
    ICrawlerReader,
    ICrawlerWriter,
)
from src.services.crawler.repositories.reader import CrawlerReader
from src.services.crawler.repositories.writer import CrawlerWriter
from src.services.jobs.jobs_service import default_jobs_service
from src.services.logger import get_logger

logger = get_logger("services.crawler")

COMMON_SUBDOMAINS = [
    "www", "api", "app", "dev", "staging", "admin", "portal", "mail",
    "vpn", "auth", "login", "dashboard", "secure", "cdn", "cloud", "beta"
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


class CrawlerService(ICrawlerService):
    def __init__(
        self,
        db_path: Optional[Path] = None,
        timeout: float = 0.8,
        max_subdomains: int = 12,
        ports: Optional[List[int]] = None,
        reader: Optional[ICrawlerReader] = None,
        writer: Optional[ICrawlerWriter] = None,
        accounts_service: Optional[Any] = None,
    ):
        self.db_path = db_path
        self.timeout = timeout
        self.max_subdomains = max_subdomains
        self.ports = ports or [80, 443, 8080, 8443]
        self.reader = reader or CrawlerReader()
        self.writer = writer or CrawlerWriter()
        self._accounts_service = accounts_service

    def set_accounts_service(self, accounts_service: Any) -> None:
        self._accounts_service = accounts_service

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
            with urllib.request.urlopen(req, timeout=self.timeout, context=ctx if scheme == "https" else None) as resp:
                banner["status"] = resp.status
                headers = dict(resp.headers)
                server_hdr = headers.get("Server", "") or headers.get("server", "")
                banner["server"] = server_hdr

                hdr_str = " ".join(f"{k}:{v}" for k, v in headers.items()).lower()
                for cp, sigs in CLOUD_SIGNATURES.items():
                    if any(sig in hdr_str for sig in sigs):
                        if cp not in banner["cloud_providers"]:
                            banner["cloud_providers"].append(cp)

                if "nginx" in server_hdr.lower():
                    banner["technologies"].append("Nginx")
                if "apache" in server_hdr.lower():
                    banner["technologies"].append("Apache HTTP Server")
                if "cloudflare" in server_hdr.lower() or "cloudflare" in banner["cloud_providers"]:
                    banner["technologies"].append("Cloudflare")
                if "express" in server_hdr.lower() or "x-powered-by: express" in hdr_str:
                    banner["technologies"].append("Express.js")
                if "react" in hdr_str or "next" in hdr_str:
                    banner["technologies"].append("React / Next.js")

        except urllib.error.HTTPError as e:
            banner["status"] = e.code
            server_hdr = e.headers.get("Server", "") or e.headers.get("server", "")
            banner["server"] = server_hdr
        except Exception:
            pass

        return banner

    def crawl_domain_with_retries(
        self,
        domain: str,
        scan_depth: str = "standard",
        enable_subdomains: bool = True,
        custom_ports: Optional[List[int]] = None,
        save_to_database: bool = False,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        last_exception = None
        for attempt in range(max_retries):
            try:
                return self.crawl_domain(
                    domain=domain,
                    scan_depth=scan_depth,
                    enable_subdomains=enable_subdomains,
                    custom_ports=custom_ports,
                    save_to_database=save_to_database,
                )
            except Exception as e:
                last_exception = e
                wait_time = 1.0 * (2 ** attempt)
                logger.warning(
                    f"Crawl attempt {attempt + 1}/{max_retries} failed for domain '{domain}': {e}. Retrying in {wait_time:.1f}s",
                    domain=domain,
                    attempt=attempt + 1,
                    wait_time=wait_time,
                )
                time.sleep(wait_time)

        raise last_exception or RuntimeError(f"Crawl failed for domain '{domain}' after {max_retries} attempts")

    def crawl_domain(
        self,
        domain: str,
        scan_depth: str = "standard",
        enable_subdomains: bool = True,
        custom_ports: Optional[List[int]] = None,
        save_to_database: bool = False,
    ) -> Dict[str, Any]:
        clean_domain = normalize_domain(domain)
        if not clean_domain:
            raise ValueError("Target domain cannot be empty")

        cached = self.reader.get_cached_scan(clean_domain)
        if cached:
            return cached

        with logger.span("crawler.recon", domain=clean_domain, scan_depth=scan_depth):
            start_time = time.time()
            ports_to_scan = custom_ports or self.ports
            if scan_depth == "quick":
                ports_to_scan = [80, 443]
            elif scan_depth == "deep":
                ports_to_scan = list(set(self.ports + DEFAULT_PORTS))

            discovered_hosts: List[str] = [clean_domain]
            if enable_subdomains and scan_depth != "quick":
                subdomain_prefixes = COMMON_SUBDOMAINS[:self.max_subdomains]
                candidate_hosts = [f"{prefix}.{clean_domain}" for prefix in subdomain_prefixes]
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(16, len(candidate_hosts))) as executor:
                    future_to_host = {executor.submit(self.resolve_ip, h): h for h in candidate_hosts}
                    for future in concurrent.futures.as_completed(future_to_host):
                        sub_host = future_to_host[future]
                        try:
                            sub_ip = future.result()
                            if sub_ip and not is_dynamic_ip_ptr(sub_host):
                                discovered_hosts.append(sub_host)
                        except Exception:
                            pass

            assets: List[Asset] = []
            unique_ips: Set[str] = set()
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
                target_addr = ip or host
                for port in ports_to_scan:
                    probe_tasks.append((host, ip, target_addr, port))

            def probe_worker(item):
                h, ip_addr, target, p = item
                is_open = self.check_port_open(target, p)
                if is_open or p in (80, 443):
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
                        res = future.result()
                        if res:
                            p_port = res["port"]
                            p_host = res["host"]
                            p_ip = res["ip"]
                            p_banner = res["banner"]

                            unique_ports.add(p_port)
                            assets.append(Asset(ip=p_ip, port=p_port, hostname=p_host))

                            for tech in p_banner["technologies"]:
                                products.add(tech)
                            for cp in p_banner["cloud_providers"]:
                                cloud_providers.add(cp)

                            rec_features = {
                                "ip": p_ip,
                                "port": p_port,
                                "hostname": p_host,
                                "domains": [clean_domain],
                                "product": p_banner["server"],
                                "cloud_providers": p_banner["cloud_providers"],
                                "tags": ["eol-product"] if "apache/2.2" in str(p_banner["server"]).lower() else [],
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

            if not assets:
                root_ip = self.resolve_ip(clean_domain) or "0.0.0.0"
                unique_ips.add(root_ip)
                assets.append(Asset(ip=root_ip, port=443, hostname=clean_domain))
                unique_ports.add(443)

            elapsed_ms = int((time.time() - start_time) * 1000)

            account = Account(
                account_key=f"domain:{clean_domain}",
                domains=[clean_domain],
                assets=assets,
                ips=list(unique_ips),
                hostnames=discovered_hosts,
                ports=list(unique_ports),
                products=list(products) or ["Web Service"],
                cloud_providers=list(cloud_providers) or ["Cloud Infrastructure"],
                signals=signals,
            )

            if not self._accounts_service:
                from src.services.accounts.accounts_service import default_accounts_service
                self._accounts_service = default_accounts_service

            existing = self._accounts_service.get_account(f"domain:{clean_domain}") or self._accounts_service.get_account(clean_domain)
            if existing:
                merged_domains = list(dict.fromkeys([clean_domain] + account.domains + (existing.domains or [])))
                merged_ips = list(dict.fromkeys(list(unique_ips) + (account.ips or []) + (existing.ips or [])))
                merged_hostnames = list(dict.fromkeys(discovered_hosts + (account.hostnames or []) + (existing.hostnames or [])))
                merged_ports = sorted(list(set(list(unique_ports) + (account.ports or []) + (existing.ports or []))))
                merged_products = list(dict.fromkeys(list(products) + (account.products or []) + (existing.products or [])))
                merged_providers = list(dict.fromkeys(list(cloud_providers) + (account.cloud_providers or []) + (existing.cloud_providers or [])))

                asset_tuples = set()
                merged_assets = []
                for a in ((account.assets or []) + (existing.assets or [])):
                    tup = (a.ip, a.port, a.hostname)
                    if tup not in asset_tuples:
                        asset_tuples.add(tup)
                        merged_assets.append(a)

                signal_tuples = set()
                merged_signals = []
                for s in ((account.signals or []) + (existing.signals or [])):
                    s_sev = s.severity.value if hasattr(s.severity, "value") else str(s.severity)
                    tup = (s.name, s_sev, getattr(s, "category", ""), s.evidence)
                    if tup not in signal_tuples:
                        signal_tuples.add(tup)
                        merged_signals.append(s)

                account = Account(
                    account_key=existing.account_key or account.account_key,
                    domain=clean_domain,
                    domains=merged_domains,
                    assets=merged_assets,
                    ips=merged_ips,
                    hostnames=merged_hostnames,
                    ports=merged_ports,
                    products=merged_products or ["Web Service"],
                    cloud_providers=merged_providers or ["Cloud Infrastructure"],
                    signals=merged_signals,
                    ai_score=existing.ai_score,
                    latest_score=existing.latest_score,
                )

            if save_to_database:
                self._accounts_service.save_account(account)

            scan_result = {
                "domain": clean_domain,
                "account_key": account.account_key,
                "scan_depth": scan_depth,
                "elapsed_ms": elapsed_ms,
                "discovered_hosts": account.hostnames,
                "assets_count": len(account.assets),
                "ips_count": len(account.ips),
                "ports_discovered": account.ports,
                "technologies": account.products,
                "cloud_providers": account.cloud_providers,
                "signals_detected_count": len(account.signals),
                "signals": [s.model_dump() if hasattr(s, "model_dump") else s.dict() for s in account.signals],
                "account": account.model_dump() if hasattr(account, "model_dump") else account.dict(),
            }

            self.writer.cache_scan(clean_domain, scan_result)
            logger.info(
                "Crawler reconnaissance finished",
                domain=clean_domain,
                elapsed_ms=elapsed_ms,
                hosts_count=len(account.hostnames),
                signals_count=len(account.signals),
                technologies=account.products,
            )
            return scan_result

    def handle_crawler_job_scan(
        self,
        job_id: str,
        payload: Dict[str, Any],
        progress_cb: Callable,
    ) -> Dict[str, Any]:
        domains = payload.get("domains", [])
        scan_depth = payload.get("scan_depth", "standard")
        enable_subdomains = payload.get("enable_subdomains", True)
        custom_ports = payload.get("custom_ports")
        save_to_db = payload.get("save_to_database", True)

        results = []
        total_assets = 0
        total_signals = 0

        for idx, dom in enumerate(domains):
            try:
                res = self.crawl_domain_with_retries(
                    domain=dom,
                    scan_depth=scan_depth,
                    enable_subdomains=enable_subdomains,
                    custom_ports=custom_ports,
                    save_to_database=save_to_db,
                    max_retries=3,
                )
                results.append(res)
                total_assets += res.get("assets_count", 0)
                total_signals += res.get("signals_detected_count", 0)
            except Exception as e:
                logger.error(f"Error in crawler job {job_id} for domain {dom}: {e}")
                results.append({
                    "domain": dom,
                    "error": str(e),
                    "assets_count": 0,
                    "signals_detected_count": 0,
                })

            progress_cb(
                idx + 1,
                len(domains),
                metadata={
                    "assets_discovered_count": total_assets,
                    "signals_detected_count": total_signals,
                    "domains_count": len(domains),
                    "scan_depth": scan_depth,
                },
                partial_results=results,
            )

        return {
            "results": results,
            "metadata": {
                "assets_discovered_count": total_assets,
                "signals_detected_count": total_signals,
                "domains_count": len(domains),
                "scan_depth": scan_depth,
            },
        }


DomainCrawler = CrawlerService
default_crawler_service = CrawlerService()

default_jobs_service.register_handler("crawler_scan", default_crawler_service.handle_crawler_job_scan)

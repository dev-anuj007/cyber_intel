from typing import Dict, List

from src.services.accounts.types import SignalSeverity
from src.services.crawler.internals.scanners.types import KevRule

COMMON_SUBDOMAINS: List[str] = [
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

DEFAULT_PORTS: List[int] = [80, 443, 8080, 8443, 3000, 5000, 22, 21, 3389, 8000, 9000]

PROJECTDISCOVERY_PORTS: List[int] = [
    80,
    443,
    8080,
    8443,
    8000,
    8888,
    9000,
    9443,
    3000,
    5000,
    22,
    3389,
    6379,
    27017,
]

CLOUD_SIGNATURES: Dict[str, List[str]] = {
    "cloudflare": ["cloudflare", "cf-ray", "cf-cache-status"],
    "aws": ["amazons3", "awselb", "cloudfront", "amz-", "aws"],
    "gcp": ["google", "gws", "gcp", "appspot"],
    "azure": ["azure", "windows.net", "ms-"],
    "akamai": ["akamai", "akamaighost"],
    "fastly": ["fastly"],
}

SENSITIVE_PATHS: List[tuple[str, str]] = [
    ("/.env", "Environment Variables File Exposure"),
    ("/.git/HEAD", "Git Repository Metadata Exposure"),
    ("/actuator/health", "Spring Actuator Management Endpoint"),
    ("/swagger.json", "Exposed OpenAPI / Swagger Documentation"),
    ("/server-status", "Apache Server-Status Diagnostic Page"),
    ("/api/v1", "API Endpoint Discovery"),
    ("/robots.txt", "Robots Policy File"),
]

CURATED_CISA_KEV_RULES: List[KevRule] = [
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

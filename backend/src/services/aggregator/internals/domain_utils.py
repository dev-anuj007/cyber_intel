import re
from typing import List, Optional

from src.services.aggregator.internals.constants import TRANSIT_DOMAINS


def normalize_domain(domain: Optional[str] = None) -> str:
    if not domain or not isinstance(domain, str):
        return ""
    return domain.lower().strip().rstrip(".")


def is_valid_account_domain(domain: str) -> bool:
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
    if not hostname:
        return False
    h = hostname.lower().strip()
    if re.search(r"\b\d{1,3}[-\.]\d{1,3}[-\.]\d{1,3}[-\.]\d{1,3}\b", h):
        return True
    if re.match(
        r"^(ip|node|host|cpe|static|dynamic|pool|dialup|cust|broadband|dsl|fiber|vps|server|ec2|vm)[0-9\-_]", h
    ):
        return True
    return False


def is_infrastructure_transit_domain(domain: str) -> bool:
    if not domain or not isinstance(domain, str):
        return True
    d = normalize_domain(domain)
    if not is_valid_account_domain(d):
        return True
    if is_dynamic_ip_ptr(d):
        return True
    for transit in TRANSIT_DOMAINS:
        if d == transit or d.endswith("." + transit):
            return True
    return False


def extract_root_domain_match(hostname: str, candidate_domains: List[str]) -> List[str]:
    norm_host = normalize_domain(hostname)
    matches = []
    for domain in candidate_domains:
        norm_dom = normalize_domain(domain)
        if norm_host == norm_dom or norm_host.endswith("." + norm_dom):
            matches.append(f"domain:{norm_dom}")
    return matches

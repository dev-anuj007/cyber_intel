from typing import Any, List, Set

from src.services.aggregator.internals.domain_utils import (
    extract_root_domain_match,
    is_dynamic_ip_ptr,
    is_infrastructure_transit_domain,
    normalize_domain,
)


class AccountKeyResolver:
    def resolve(self, record: dict) -> List[str]:
        raw_domains = record.get("domains") or []
        valid_domains = self._filter_valid_domains(raw_domains)
        if not valid_domains:
            return []

        hostnames = record.get("hostnames") or []
        if isinstance(hostnames, str):
            hostnames = [hostnames]

        matched_keys: Set[str] = set()
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

    def filter_valid_domains(self, raw_domains: List[Any]) -> List[str]:
        """Public alias for backward compatibility."""
        return self._filter_valid_domains(raw_domains)

    # =========================================================================
    # Internal / Helper Methods
    # =========================================================================

    def _filter_valid_domains(self, raw_domains: List[Any]) -> List[str]:
        valid_domains = []
        for domain in raw_domains:
            if not isinstance(domain, str):
                continue
            normalized = normalize_domain(domain)
            if is_infrastructure_transit_domain(normalized):
                continue
            valid_domains.append(normalized)
        return valid_domains

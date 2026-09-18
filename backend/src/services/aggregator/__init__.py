"""Aggregator Service Package."""

from src.services.aggregator.aggregator_service import (
    AggregatorService,
    default_aggregator_service,
    normalize_domain,
    is_valid_account_domain,
    is_dynamic_ip_ptr,
    is_infrastructure_transit_domain,
    extract_root_domain_match,
    detect_signals,
    extract_features,
    build_accounts,
    load_accounts_from_jsonl,
    resolve_account_keys,
)
from src.services.aggregator.types import IAggregatorService

__all__ = [
    "AggregatorService",
    "default_aggregator_service",
    "IAggregatorService",
    "normalize_domain",
    "is_valid_account_domain",
    "is_dynamic_ip_ptr",
    "is_infrastructure_transit_domain",
    "extract_root_domain_match",
    "detect_signals",
    "extract_features",
    "build_accounts",
    "load_accounts_from_jsonl",
    "resolve_account_keys",
]

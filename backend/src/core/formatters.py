import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Union


def normalize_domain(domain: str) -> str:
    if not domain:
        return ""
    clean = domain.strip().lower()
    clean = re.sub(r"^https?://", "", clean)
    clean = clean.split("/")[0].split(":")[0]
    return clean


def extract_base_domain(account_key: str) -> str:
    clean = (account_key or "").strip()
    if clean.startswith("domain:"):
        clean = clean[7:]
    parts = clean.split(":")
    return parts[0].strip().lower()


def extract_version_tag(account_key: str) -> str:
    if account_key and account_key.count(":") >= 2:
        parts = account_key.split(":")
        if parts[-1].startswith("v") and parts[-1][1:].isdigit():
            return parts[-1]
    return "v1"


def format_account_key(domain: str, version: Optional[str] = None) -> str:
    base = normalize_domain(domain)
    if not version or version.lower() == "v1":
        return f"domain:{base}"
    ver_tag = version if version.startswith("v") else f"v{version}"
    return f"domain:{base}:{ver_tag}"


def format_tier_display_name(tier: Optional[str]) -> str:
    tier_map = {
        "tier_1_critical": "Tier 1 (Critical)",
        "tier_2_high": "Tier 2 (High)",
        "tier_3_medium": "Tier 3 (Medium)",
        "tier_4_low": "Tier 4 (Low)",
    }
    return tier_map.get((tier or "").lower(), tier or "Unknown")


def format_severity_display_name(severity: Optional[str]) -> str:
    sev_map = {
        "critical": "Critical",
        "high": "High",
        "medium": "Medium",
        "low": "Low",
    }
    return sev_map.get((severity or "").lower(), (severity or "Low").capitalize())


def format_currency(amount: Optional[Union[float, int]] = None, precision: int = 4) -> str:
    try:
        val = float(amount or 0.0)
        return f"${val:.{precision}f}"
    except (ValueError, TypeError):
        return "$0.0000"


def format_tokens(tokens: Union[int, Dict[str, int], None]) -> str:
    if isinstance(tokens, dict):
        total = tokens.get("total") or (tokens.get("input", 0) + tokens.get("output", 0))
        return f"{total:,}"
    try:
        val = int(tokens or 0)
        return f"{val:,}"
    except (ValueError, TypeError):
        return "0"


def format_latency(latency_ms: Union[int, float, None]) -> str:
    try:
        val = float(latency_ms or 0.0)
        if val >= 1000:
            return f"{val / 1000.0:.2f}s"
        return f"{int(val)}ms"
    except (ValueError, TypeError):
        return "0ms"


def format_truncated_list(items: List[str], max_items: int = 10, suffix: str = "more") -> str:
    if not items:
        return "None"
    if len(items) <= max_items:
        return ", ".join(items)
    sampled = ", ".join(items[:max_items])
    remaining = len(items) - max_items
    return f"{sampled}, ... (+{remaining} {suffix})"


def format_iso_datetime(dt: Optional[Union[datetime, str, float, int]] = None) -> str:
    if dt is None:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    if isinstance(dt, (int, float)):
        return datetime.fromtimestamp(dt, tz=timezone.utc).isoformat()
    return str(dt)

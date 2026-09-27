from src.core.formatters import (
    extract_base_domain,
    extract_version_tag,
    format_account_key,
    format_currency,
    format_iso_datetime,
    format_latency,
    format_severity_display_name,
    format_tier_display_name,
    format_tokens,
    format_truncated_list,
    normalize_domain,
)


def test_domain_formatters():
    assert normalize_domain("https://app.example.com/login:443") == "app.example.com"
    assert normalize_domain("HTTP://SUB.DOMAIN.ORG/") == "sub.domain.org"
    assert normalize_domain("") == ""

    assert extract_base_domain("domain:example.com") == "example.com"
    assert extract_base_domain("domain:example.com:v2") == "example.com"
    assert extract_base_domain("example.com:v3") == "example.com"

    assert extract_version_tag("domain:example.com:v2") == "v2"
    assert extract_version_tag("domain:example.com") == "v1"
    assert extract_version_tag("example.com") == "v1"

    assert format_account_key("example.com") == "domain:example.com"
    assert format_account_key("example.com", "v1") == "domain:example.com"
    assert format_account_key("example.com", "v2") == "domain:example.com:v2"
    assert format_account_key("example.com", "3") == "domain:example.com:v3"


def test_tier_and_severity_formatters():
    assert format_tier_display_name("tier_1_critical") == "Tier 1 (Critical)"
    assert format_tier_display_name("tier_2_high") == "Tier 2 (High)"
    assert format_tier_display_name("tier_3_medium") == "Tier 3 (Medium)"
    assert format_tier_display_name("tier_4_low") == "Tier 4 (Low)"
    assert format_tier_display_name(None) == "Unknown"

    assert format_severity_display_name("critical") == "Critical"
    assert format_severity_display_name("high") == "High"
    assert format_severity_display_name("medium") == "Medium"
    assert format_severity_display_name("low") == "Low"
    assert format_severity_display_name(None) == "Low"


def test_metric_and_string_formatters():
    assert format_currency(0.0045) == "$0.0045"
    assert format_currency(12.5, precision=2) == "$12.50"
    assert format_currency(None) == "$0.0000"

    assert format_tokens(1250) == "1,250"
    assert format_tokens({"input": 1000, "output": 250}) == "1,250"
    assert format_tokens(None) == "0"

    assert format_latency(250) == "250ms"
    assert format_latency(1500) == "1.50s"
    assert format_latency(None) == "0ms"

    assert format_truncated_list(["a", "b", "c"], max_items=5) == "a, b, c"
    assert (
        format_truncated_list(["a", "b", "c", "d"], max_items=2)
        == "a, b, ... (+2 more)"
    )
    assert format_truncated_list([]) == "None"

    assert "T" in format_iso_datetime()

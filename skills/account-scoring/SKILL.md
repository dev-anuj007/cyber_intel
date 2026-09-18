---
name: account-scoring
description: Reusable AI workflow for scoring and prioritizing B2B sales target accounts based on external cybersecurity telemetry, vulnerability exploitability, and attack surface risk.
version: 2.0.0
---

# SKILL: Account Risk Scoring & Sales Prioritization

## Purpose
Evaluate raw security telemetry and attack surface characteristics for a given business account to generate a calibrated, actionable account risk score (1–100), assign a priority tier (Critical, High, Medium, Low), extract key business risks, and generate an initial consultative sales outreach angle.

## When to Use
- **Trigger:** When an SDR or Account Executive imports a domain or needs to triage accounts for outbound targeting.
- **Batch Processing:** Run nightly or on-demand across batches of accounts (e.g. 50–500 accounts) to refresh sales tiering.
- **Ad-Hoc Inspection:** Real-time on-demand scoring when a sales rep views an individual account in the sales dashboard.

## Inputs Schema
```json
{
  "account_key": "domain:healthcare-hospital.org",
  "domains": ["healthcare-hospital.org"],
  "assets": [
    { "ip": "198.51.100.24", "port": 443, "hostname": "portal.healthcare-hospital.org" }
  ],
  "ips": ["198.51.100.24"],
  "hostnames": ["portal.healthcare-hospital.org"],
  "ports": [443, 8443],
  "products": ["Apache Tomcat 8.5", "OpenSSL 1.0.2"],
  "cloud_providers": ["AWS"],
  "signals": [
    {
      "name": "kev_vulnerability",
      "severity": "critical",
      "category": "vulnerability",
      "evidence": "CVE-2023-46604 listed in CISA Known Exploited Vulnerabilities catalog"
    },
    {
      "name": "ransomware_associated_vulnerability",
      "severity": "critical",
      "category": "vulnerability",
      "evidence": "Associated with active LockBit 3.0 ransomware campaigns"
    },
    {
      "name": "eol_product",
      "severity": "high",
      "category": "infrastructure",
      "evidence": "End-of-Life Apache Tomcat 8.5 detected on external perimeter"
    }
  ]
}
```

## Output Schema
```json
{
  "score": 94,
  "priority_tier": "tier_1_critical",
  "key_risks": [
    "Active CISA KEV listing (CVE-2023-46604) under active threat actor exploitation",
    "Direct correlation with LockBit ransomware campaign tradecraft",
    "Critical HIPAA and patient data compliance exposure via vulnerable public patient portal"
  ],
  "suggested_outreach": "We identified a CISA-cataloged vulnerability actively targeted by ransomware groups on your external patient portal. Given the acute operational and regulatory risks in healthcare, let's connect for 15 minutes this week to share our diagnostic findings and remediation plan."
}
```

## Scoring Rubric & Tier Rules
- **Tier 1 Critical (90–100):** CISA KEV listed vulnerabilities, active ransomware associations, CVSS ≥ 9.0 on public assets, critical infrastructure / healthcare with unmitigated perimeter exploits.
- **Tier 2 High (65–89):** High severity CVEs (CVSS 7.0–8.9), high EPSS exploit probability (>0.50), EOL infrastructure (e.g. Windows Server 2003, old OpenSSL), regulated sectors.
- **Tier 3 Medium (40–64):** Medium vulnerabilities (CVSS 4.0–6.9), non-standard open ports (8080, 8443, 9200), standard technology stack without weaponized exploits.
- **Tier 4 Low (1–39):** Minimal attack surface, modern cloud posture, zero high/critical vulnerabilities.

## Dependent Prompts
- Baseline Prompt: `prompts/account_scoring_v1.0.txt`
- Calibrated Production Prompt: `prompts/account_scoring_v2.0.txt`

## Worked Example Invocation

### Command / API Call
```python
from src.services.scorer import ScorerService as AccountScorer
from src.models import Account, SecuritySignal, SignalSeverity, Asset

scorer = AccountScorer(prompt_version="v2.0")
account = Account(
    account_key="domain:fintech-payments.io",
    domains=["fintech-payments.io"],
    assets=[Asset(ip="203.0.113.10", port=443, hostname="api.fintech-payments.io")],
    ips=["203.0.113.10"],
    hostnames=["api.fintech-payments.io"],
    ports=[443],
    products=["Nginx", "Node.js"],
    cloud_providers=["GCP"],
    signals=[
        SecuritySignal(
            name="high_severity_vulnerability",
            severity=SignalSeverity.HIGH,
            category="vulnerability",
            evidence="CVSS 8.4 API authentication bypass detected"
        ),
        SecuritySignal(
            name="high_exploitation_probability",
            severity=SignalSeverity.HIGH,
            category="vulnerability",
            evidence="EPSS score 0.72 indicates high likelihood of in-the-wild exploitation"
        )
    ]
)

score_result = scorer.score_account(account)
print(f"Tier: {score_result.priority_tier.value}, Score: {score_result.score}")
```

### Result
```
Tier: tier_2_high, Score: 82
Key Risks:
1. High-severity authentication vulnerability (CVSS 8.4) on public API gateway
2. Top-decile EPSS exploitability (0.72) indicating imminent weaponization
Outreach Angle: Your API perimeter shows a high-probability authentication exposure that directly impacts payment transaction integrity. Let's schedule a brief 15-minute briefing to review mitigation options.
```

## Production Cost Model
| Model Tier | Workload | Pricing (Input / Output per 1M) | Est. Cost / Account | 1,000 Accounts | 50,000 Accounts (Full DB) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Gemini 2.5 Flash Lite** | High-volume batch triage | $0.075 / $0.30 | **$0.00018** | **$0.18** | **$9.00** |
| **Gemini 2.5 Flash** | Standard interactive scoring | $0.15 / $0.60 | **$0.00036** | **$0.36** | **$18.00** |
| **Gemini 2.5 Pro** | Deep executive briefing | $1.25 / $5.00 | **$0.00300** | **$3.00** | **$150.00** |

**Production Ceiling Policy:** Max monthly LLM budget capped at $50.00, enforced via pre-filtering heuristic rules (filtering low-signal accounts prior to LLM evaluation) and strict in-memory caching of scores.

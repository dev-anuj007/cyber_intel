---
name: account-scoring
description: Reusable AI workflow for scoring and prioritizing B2B sales target accounts based on external cybersecurity telemetry, vulnerability exploitability, and attack surface risk.
version: 2.0.0
---

# SKILL: Account Risk Scoring & Sales Prioritization (v2.0)

## Purpose
Score B2B target accounts for sales readiness and outbound targeting based on external cybersecurity telemetry. This skill computes a calibrated risk score (1–100), assigns an actionable priority tier, surfaces top enterprise risks, and suggests a high-conversion sales angle.

## When to Use
- **Trigger:** When an SDR or Account Executive needs to prioritize accounts for outbound prospecting campaigns.
- **Batch Processing:** Run nightly or on-demand across batches of accounts to refresh sales tiering.
- **Ad-Hoc Inspection:** Instant single-account scoring when viewing an account detail card in the sales dashboard.

## Inputs Schema
```json
{
  "account": {
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
        "evidence": "1 vulnerability(s) listed in CISA KEV"
      },
      {
        "name": "ransomware_associated_vulnerability",
        "severity": "critical",
        "category": "vulnerability",
        "evidence": "Associated with active ransomware campaigns"
      }
    ]
  }
}
```

## Outputs Schema
```json
{
  "score": 94,
  "priority_tier": "tier_1_critical",
  "key_risks": [
    "Active CISA Known Exploited Vulnerability (KEV) on external perimeter",
    "Ransomware campaign weaponization profile detected",
    "Healthcare sector regulatory liability (HIPAA) on exposed patient portal"
  ],
  "suggested_outreach": "We detected an active CISA-cataloged vulnerability on your external patient portal currently targeted by ransomware campaigns. Given strict HIPAA requirements, let's schedule a brief 15-minute diagnostic walkthrough this week."
}
```

## Scoring Rubric & Tier Rules
- **Tier 1 Critical (90–100):** Ransomware-linked vulnerabilities, CISA KEV exploits, CVSS ≥ 9.0 on public perimeter, critical infrastructure or healthcare with active weaponized flaws.
- **Tier 2 High (65–89):** Multiple high-severity vulnerabilities (CVSS 7.0–8.9), high EPSS (>0.50), EOL infrastructure, regulated sectors.
- **Tier 3 Medium (40–64):** Medium vulnerabilities (CVSS 4.0–6.9), non-standard open ports, normal security posture.
- **Tier 4 Low (1–39):** Minimal attack surface, modern cloud posture, zero high/critical vulnerabilities.

## Dependent Prompts
- Baseline Prompt: `prompts/account_scoring_v1.0.txt`
- Production Calibrated Prompt: `prompts/account_scoring_v2.0.txt`

## Cost Model
- **Gemini 2.5 Flash Lite:** ~$0.00018 per account ($0.18 per 1,000 accounts)
- **Gemini 2.5 Flash:** ~$0.00036 per account ($0.36 per 1,000 accounts)
- **Ceiling:** Enforce heuristic rule pre-filtering for zero-signal accounts to maintain total monthly LLM expenditure under $50.00.

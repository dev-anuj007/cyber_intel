---
name: outreach-generator
description: Reusable AI workflow for generating hyper-personalized, high-conversion outbound sales emails and executive battlecards grounded in real cybersecurity vulnerability evidence.
version: 1.0.0
---

# SKILL: B2B Cybersecurity Sales Outreach Generator

## Purpose
Transform technical security vulnerability findings and threat intelligence signals into consultative, compelling outbound sales copy (cold emails, LinkedIn messages, and executive briefing notes) targeted at CISOs, VPs of Infrastructure, and Heads of Security.

## When to Use
- **Trigger:** When an SDR or Account Executive clicks "Draft Outreach" or exports a prioritized campaign list from the platform.
- **Workflow:** Takes an enriched `AccountScore` and generates targeted messaging that references concrete CVEs, EOL systems, or attack surface exposures without aggressive fearmongering.

## Inputs Schema
```json
{
  "account_key": "domain:regional-creditunion.bank",
  "domain": "regional-creditunion.bank",
  "priority_tier": "tier_2_high",
  "score": 82,
  "key_risks": [
    "Unpatched high-severity CVE-2023-38606 in mobile banking API endpoint",
    "Legacy SSL/TLS ciphers exposing transaction communications"
  ],
  "technologies": ["F5 BIG-IP", "Nginx", "Java"],
  "target_persona": "CISO"
}
```

## Outputs Schema
```json
{
  "subject_line": "Security review: External API exposure on regional-creditunion.bank",
  "email_body": "Hi [First Name],\n\nDuring an external perimeter assessment of regional financial institutions, our research team noticed an unpatched API authentication vulnerability alongside legacy TLS endpoints on your public mobile banking perimeter.\n\nGiven the strict FFIEC compliance standards and increasing credential stuffing attempts against financial portals, we put together a rapid mitigation brief tailored to your F5/Nginx stack.\n\nDo you have 15 minutes this Thursday for a peer-to-peer walkthrough of our findings?\n\nBest regards,\n[Sales Rep Name]\nCybersecurity Solutions Team",
  "recommended_channel": "Email / LinkedIn InMail",
  "pain_points_addressed": ["Regulatory FFIEC compliance", "API perimeter breach risk"]
}
```

## Dependent Prompts
- Prompt File: `prompts/outreach_draft_v1.0.txt`

## Cost Model
- **Token Usage:** ~350 prompt tokens, ~200 completion tokens = ~550 total tokens.
- **Cost per Draft:** ~$0.00015 (using Gemini Flash / Flash Lite).
- **Campaign (500 prospects):** ~$0.075 USD total.

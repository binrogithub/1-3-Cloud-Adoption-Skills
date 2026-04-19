# IPS Finance Tuning Guide

## Overview

This document provides guidance on configuring and tuning the Intrusion Prevention System (IPS) for financial workloads on Huawei Cloud CFW. It covers protection modes, rule categories, virtual patching, and finance-specific tuning recommendations.

## IPS Protection Modes

| Mode | Value | Behavior | When to Use |
|------|-------|----------|-------------|
| Observation | 0 | Detect and log, do not block | Pre-production validation only |
| Strict | 1 | Detect and block all matched threats | **Production (required for finance)** |
| Medium | 2 | Block high/critical, observe medium/low | Transitional periods |
| Loose | 3 | Block critical only, observe all others | Not recommended for finance |

### Switching Protection Mode

```bash
# Switch to strict protection mode (required for financial production)
echo "b" | hcloud CFW ChangeIpsProtectMode \
  --cli-region="<region>" \
  --object_id="<object_id>" \
  --mode="1"
```

> **Financial Rule**: IPS must be in strict protection mode (mode=1) for any production environment processing financial transactions. Observation mode is only acceptable in pre-production or staging environments.

## IPS Feature Status

### Basic Defense

Basic IPS defense provides signature-based threat detection using Huawei's threat intelligence database.

```bash
# Check basic defense status
hcloud CFW ListIpsSwitchStatus \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --object_id="<object_id>"
```

Response field `basic_defense_status`:
- `1` = Enabled (required)
- `0` = Disabled (must enable for finance)

### Virtual Patching

Virtual patching provides zero-day vulnerability protection by applying virtual patches to known vulnerabilities before vendor patches are available.

```bash
# Enable virtual patching
hcloud CFW ChangeIpsSwitchStatus \
  --cli-region="<region>" \
  --object_id="<object_id>" \
  --ips_type="2" \
  --status="1"
```

> **Financial Rule**: Virtual patching must be enabled for all financial workloads. This is critical for PCI DSS 6.5 (application vulnerability protection) and ISO A.8.8 (technical vulnerability management).

## IPS Rule Categories for Finance

### Critical Categories (Must Enable)

| Category | Description | Financial Relevance |
|----------|-------------|-------------------|
| Web Attacks | SQL injection, XSS, CSRF, RFI/LFI | Direct attack on banking applications |
| Authentication Attacks | Brute force, credential stuffing | Account takeover prevention |
| Exploit Kits | Known exploit kit detection | Drive-by attack prevention |
| Malware | Virus, trojan, ransomware | Endpoint and server protection |
| Botnet | C2 communication detection | Prevent data exfiltration via botnet |
| Buffer Overflow | Memory corruption attacks | Application exploit prevention |

### Important Categories (Should Enable)

| Category | Description | Financial Relevance |
|----------|-------------|-------------------|
| DDoS | Distributed denial of service | Service availability protection |
| Information Disclosure | Data leakage attempts | Cardholder data protection |
| Phishing | Phishing site detection | Social engineering defense |
| Crypto Mining | Cryptocurrency mining malware | Resource abuse prevention |

### Finance-Specific Tuning Recommendations

| Configuration | Recommended Value | Rationale |
|---------------|-------------------|-----------|
| Basic Defense | Enabled | Core threat protection for all traffic |
| Protection Mode | Strict (1) | Active blocking required for banking |
| Virtual Patching | Enabled | Zero-day protection before patches applied |
| Severity Focus | Critical, High, Medium | Block significant threats, log low for review |

## IPS Rule Mode Management

### Change Individual Rule Mode

```bash
# Set a specific IPS rule to block mode
hcloud CFW ChangeIpsRuleMode \
  --cli-region="<region>" \
  --object_id="<object_id>" \
  --rule_id="<rule_id>" \
  --mode="1"
```

### View Advanced IPS Rules

```bash
# List advanced IPS rules for review
hcloud CFW ListAdvancedIpsRules \
  --cli-region="<region>" \
  --object_id="<object_id>" \
  --limit="100" \
  --offset="0"
```

## IPS Configuration for Payment Systems

Payment systems require the most stringent IPS configuration:

### Payment Gateway Protection

| Threat Vector | IPS Category | Action | Priority |
|---------------|-------------|--------|----------|
| SQL Injection on payment API | Web Attacks | Block | Critical |
| Credential stuffing on login | Authentication Attacks | Block | Critical |
| XSS on payment form | Web Attacks | Block | Critical |
| CSRF token bypass | Web Attacks | Block | High |
| Botnet C2 from compromised host | Botnet | Block | Critical |
| Ransomware on payment server | Malware | Block | Critical |
| DDoS on payment endpoint | DDoS | Block | High |

### Core Banking Protection

| Threat Vector | IPS Category | Action | Priority |
|---------------|-------------|--------|----------|
| Brute force on banking portal | Authentication Attacks | Block | Critical |
| API injection on transaction API | Web Attacks | Block | Critical |
| Data exfiltration attempt | Information Disclosure | Block | High |
| Internal lateral movement | Botnet + Malware | Block | High |

## IPS Validation

After configuration, validate IPS settings:

```bash
# Check IPS switch status
hcloud CFW ListIpsSwitchStatus \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --object_id="<object_id>"

# Expected response for finance:
# basic_defense_status: 1 (enabled)
# virtual_patches_status: 1 (enabled)

# Check IPS protection mode
hcloud CFW ListIpsProtectMode \
  --cli-region="<region>" \
  --object_id="<object_id>"

# Expected response for finance:
# mode: 1 (strict protection)
```

## IPS Tuning Workflow

```
1. Enable basic defense           → ChangeIpsSwitchStatus (if not enabled)
2. Enable virtual patching        → ChangeIpsSwitchStatus (ips_type=2, status=1)
3. Set strict protection mode     → ChangeIpsProtectMode (mode=1)
4. Review advanced IPS rules      → ListAdvancedIpsRules
5. Adjust individual rule modes   → ChangeIpsRuleMode (as needed)
6. Validate configuration         → ListIpsSwitchStatus + ListIpsProtectMode
7. Monitor in observation mode    → (optional, pre-production only)
8. Switch to strict mode          → ChangeIpsProtectMode (mode=1)
```

## Common Pitfalls

| Pitfall | Impact | Prevention |
|---------|--------|------------|
| Running IPS in observation mode in production | Attacks detected but not blocked | Enforce mode=1 for production |
| Virtual patching disabled | Zero-day vulnerabilities unprotected | Always enable for finance |
| Only blocking critical severity | Medium threats may exploit banking systems | Block Critical, High, and Medium |
| Not reviewing IPS logs | Missed attack patterns | Regular review of IPS logs via LTS |
| Changing mode without testing | Potential legitimate traffic blocked | Test in observation mode first, then switch |

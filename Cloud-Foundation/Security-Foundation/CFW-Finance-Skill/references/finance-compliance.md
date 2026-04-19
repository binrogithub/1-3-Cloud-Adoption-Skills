# Financial Compliance Mapping for CFW

## Overview

This document maps financial regulatory requirements to specific Huawei Cloud CFW features and configurations. It serves as the compliance reference for AI agent-driven CFW deployment.

## PCI DSS v4.0 Mapping

| PCI DSS Requirement | Description | CFW Feature | Configuration |
|---------------------|-------------|-------------|---------------|
| 1.1 | Network security controls defined and maintained | CFW Instance + ACL | Create CFW instance with documented ACL rules |
| 1.2 | Network traffic restricted to trusted sources | ACL Inbound Rules | Default deny, explicit allow for banking services |
| 1.3 | Network access to cardholder data environment restricted | ACL + Network Segmentation | Deny rules for unauthorized zones, allow only DMZ-to-App |
| 1.4 | Network connections between trusted and untrusted networks controlled | CFW Internet Border | EIP protection with geo-blocking for high-risk regions |
| 1.5 | Intrusion detection/prevention mechanisms in place | IPS | Enable IPS in strict protection mode (mode=1) |
| 1.6 | Network segmentation maintains CDE isolation | ACL Rules | Separate rules for DMZ, Application, Data, Management zones |
| 5.3 | Malicious software prevented or detected | Anti-Virus + IPS | Enable anti-virus and IPS malware signatures |
| 5.4 | Phishing and social engineering protections | URL Filtering | Block known phishing domains |
| 6.5 | Application vulnerabilities addressed | Virtual Patching | Enable virtual patching (ips_type=2, status=1) |
| 10.1 | Audit logs enabled for all system components | LTS Logging | Enable LTS with 365-day retention for attack and IPS logs |
| 10.2 | Audit logs review for anomalies | Alarm Configuration | Enable attack alarms with CRITICAL/HIGH/MEDIUM severity |
| 10.3 | Audit logs retained for at least 1 year | LTS + OBS | Attack logs: 365 days in LTS + OBS; IPS logs: 365 days |
| 11.4 | Intrusion detection and testing | IPS + Traffic Capture | IPS enabled, periodic traffic capture for analysis |
| 12.4 | Security policies established and maintained | CFW Full Configuration | Documented rule set, change management process |

## ISO 27001:2022 Mapping

| ISO 27001 Control | Description | CFW Feature | Configuration |
|-------------------|-------------|-------------|---------------|
| A.5.1 | Information security policies | CFW Rule Documentation | Named rules with descriptions following convention |
| A.8.1 | Asset inventory | CFW Protected Objects | EIP and VPC protection with documented inventory |
| A.8.20 | Networks security | CFW Full Stack | All four security layers enabled |
| A.8.21 | Security of network services | ACL + IPS | Service-specific rules with IPS inspection |
| A.8.22 | Segregation of networks | ACL Zone Rules | DMZ, App, Data, Management zone separation |
| A.8.23 | Web filtering | URL Filtering | Domain-based allow/deny lists |
| A.8.24 | Use of cryptography | HTTPS-Only Rule | Port 443 allow, port 80 deny for banking |
| A.8.25 | Secure development lifecycle | Virtual Patching | Zero-day protection for application vulnerabilities |
| A.8.8 | Management of technical vulnerabilities | IPS + Virtual Patching | Strict mode IPS with virtual patching enabled |
| A.8.9 | Configuration management | CFW Configuration Audit | Validation script confirming all gates pass |
| A.8.15 | Logging | LTS Integration | All log types enabled with required retention |
| A.8.16 | Monitoring activities | Alarm Configuration | Attack, bandwith, and resource alarms enabled |
| A.5.14 | Transfer of information | ACL Egress Rules | Outbound rules for DNS, NTP, authorized services |

## NIST Cybersecurity Framework Mapping

| NIST Function | Category | CFW Feature | Configuration |
|---------------|----------|-------------|---------------|
| Identify | ID.AM - Asset Management | CFW Protected Objects | EIP and VPC inventory |
| Identify | ID.RA - Risk Assessment | IPS Rule Categories | Enable relevant IPS signatures for finance |
| Protect | PR.AC - Access Control | ACL Rules | Default deny, explicit allow, zone segmentation |
| Protect | PR.AC - Remote Access | ACL + Geo-Blocking | Restrict management access by region |
| Protect | PR.DS - Data Security | HTTPS-Only + IPS | Encrypt in transit, inspect for exfiltration |
| Protect | PR.IP - Information Protection | Virtual Patching | Zero-day vulnerability protection |
| Protect | PR.MA - Maintenance | CFW Rule Management | Named rules, change tracking, audit |
| Protect | PR.PT - Protective Technology | CFW Full Stack | All security features enabled |
| Detect | DE.AE - Anomalies and Events | IPS + Alarms | Strict mode IPS, attack alarms enabled |
| Detect | DE.CM - Continuous Monitoring | LTS + Alarms | Real-time logging, threshold alerts |
| Detect | DE.DP - Detection Processes | Traffic Capture | Packet capture for forensic analysis |
| Respond | RS.AN - Analysis | Attack Logs + IPS Logs | Detailed event logging for investigation |
| Respond | RS.CO - Communications | SMN Notifications | Alarm notifications to security team |
| Recover | RC.RP - Recovery Planning | CFW Configuration Backup | Documented rule set for rapid restoration |

## Regional Banking Regulations

### Mexico (CNBV / Banxico)

| Requirement | CFW Feature | Configuration |
|-------------|-------------|---------------|
| Network perimeter protection | CFW Internet Border | All EIPs protected |
| Intrusion detection | IPS | Strict protection mode enabled |
| Access logging | LTS | 365-day retention for attack logs |
| Incident notification | SMN Alarms | Real-time attack notifications |
| Data protection in transit | HTTPS-Only Rule | TLS 1.2+ enforcement via port 443 |
| Vulnerability management | Virtual Patching | Zero-day protection enabled |

### General Financial Regulatory Patterns

| Pattern | CFW Implementation |
|---------|-------------------|
| Know your traffic | Enable flow logs with 90-day retention |
| Block by geography | Geo-blocking ACL rules for high-risk regions |
| Segregate cardholder data | Zone-based ACL rules (DMZ → App → Data) |
| Detect and respond | IPS strict mode + attack alarms + SMN |
| Audit everything | LTS logging for all log types |
| Patch immediately | Virtual patching for zero-day coverage |

## Compliance Checklist

Use this checklist to verify CFW meets financial regulatory requirements:

- [ ] CFW instance created and running (status=2)
- [ ] IPS basic defense enabled (basic_defense_status=1)
- [ ] IPS in strict protection mode (mode=1)
- [ ] Virtual patching enabled (virtual_patches_status=1)
- [ ] ACL rules follow default-deny principle
- [ ] HTTPS-only rule for banking services
- [ ] Network segmentation rules in place (DMZ, App, Data, Management)
- [ ] Geo-blocking rules for high-risk regions
- [ ] LTS logging enabled (lts_enable=1)
- [ ] Attack log retention >= 365 days
- [ ] IPS log retention >= 365 days
- [ ] Attack alarms enabled (CRITICAL, HIGH, MEDIUM)
- [ ] Bandwidth alarms enabled
- [ ] Resource alarms enabled
- [ ] SMN notification topic configured
- [ ] Rule naming convention followed
- [ ] Configuration documented for audit

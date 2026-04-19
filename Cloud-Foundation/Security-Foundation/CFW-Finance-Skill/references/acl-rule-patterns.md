# Finance-Specific ACL Rule Patterns

## Overview

This document provides ready-to-use ACL rule patterns for financial workloads on Huawei Cloud CFW. Each pattern includes the hcloud CLI command, the rule logic, and the compliance rationale.

## Rule Naming Convention

All rules must follow this naming convention:

```
[Customer]-[Direction]-[Service]-[Action]-[Priority]
```

Examples:
- `Finance-Inbound-HTTPS-Allow-100`
- `Finance-Outbound-DNS-Allow-200`
- `Finance-Inbound-HighRisk-Deny-50`

## Core Banking Rules

### Rule 1: HTTPS Banking Access (Inbound)

**Purpose**: Allow secure banking transactions from the internet to banking services.

**Compliance**: PCI DSS 1.2, 8.24 (encryption in transit)

```bash
hcloud CFW AddAclRule \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --object_id="<object_id>" \
  --type="0" \
  --rules.1.name="Finance-Inbound-HTTPS-Allow" \
  --rules.1.address_type="0" \
  --rules.1.direction="0" \
  --rules.1.status="1" \
  --rules.1.action_type="0" \
  --rules.1.long_connect_enable="0" \
  --rules.1.source.type="0" \
  --rules.1.source.address="0.0.0.0/0" \
  --rules.1.destination.type="0" \
  --rules.1.destination.address="0.0.0.0/0" \
  --rules.1.service.type="0" \
  --rules.1.service.protocol="6" \
  --rules.1.service.source_port="1-65535" \
  --rules.1.service.dest_port="443" \
  --rules.1.sequence.top="1"
```

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| direction | 0 (Inbound) | External clients connecting to banking services |
| action_type | 0 (Allow) | Permit HTTPS traffic |
| protocol | 6 (TCP) | HTTPS runs over TCP |
| dest_port | 443 | Standard HTTPS port |
| source.address | 0.0.0.0/0 | Allow from any source (restrict if possible) |

### Rule 2: HTTP Redirect Only (Inbound)

**Purpose**: Allow HTTP only for redirect to HTTPS. Do NOT use for transaction processing.

**Compliance**: PCI DSS 4.1 (strong cryptography), ISO A.8.24

```bash
hcloud CFW AddAclRule \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --object_id="<object_id>" \
  --type="0" \
  --rules.1.name="Finance-Inbound-HTTP-Redirect-Allow" \
  --rules.1.address_type="0" \
  --rules.1.direction="0" \
  --rules.1.status="1" \
  --rules.1.action_type="0" \
  --rules.1.long_connect_enable="0" \
  --rules.1.source.type="0" \
  --rules.1.source.address="0.0.0.0/0" \
  --rules.1.destination.type="0" \
  --rules.1.destination.address="0.0.0.0/0" \
  --rules.1.service.type="0" \
  --rules.1.service.protocol="6" \
  --rules.1.service.source_port="1-65535" \
  --rules.1.service.dest_port="80" \
  --rules.1.sequence.top="1"
```

> **Warning**: This rule should only be enabled if the application redirects HTTP to HTTPS. For strict compliance, consider disabling this rule and requiring HTTPS-only access.

### Rule 3: DNS Resolution (Outbound)

**Purpose**: Allow outbound DNS resolution for banking services.

**Compliance**: ISO A.5.14 (information transfer)

```bash
hcloud CFW AddAclRule \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --object_id="<object_id>" \
  --type="0" \
  --rules.1.name="Finance-Outbound-DNS-Allow" \
  --rules.1.address_type="0" \
  --rules.1.direction="1" \
  --rules.1.status="1" \
  --rules.1.action_type="0" \
  --rules.1.long_connect_enable="0" \
  --rules.1.source.type="0" \
  --rules.1.source.address="0.0.0.0/0" \
  --rules.1.destination.type="0" \
  --rules.1.destination.address="0.0.0.0/0" \
  --rules.1.service.type="0" \
  --rules.1.service.protocol="17" \
  --rules.1.service.source_port="1-65535" \
  --rules.1.service.dest_port="53" \
  --rules.1.sequence.top="1"
```

### Rule 4: NTP Time Sync (Outbound)

**Purpose**: Allow NTP for time synchronization (critical for transaction logging and audit).

**Compliance**: PCI DSS 10.4 (time synchronization), ISO A.8.15

```bash
hcloud CFW AddAclRule \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --object_id="<object_id>" \
  --type="0" \
  --rules.1.name="Finance-Outbound-NTP-Allow" \
  --rules.1.address_type="0" \
  --rules.1.direction="1" \
  --rules.1.status="1" \
  --rules.1.action_type="0" \
  --rules.1.long_connect_enable="0" \
  --rules.1.source.type="0" \
  --rules.1.source.address="0.0.0.0/0" \
  --rules.1.destination.type="0" \
  --rules.1.destination.address="0.0.0.0/0" \
  --rules.1.service.type="0" \
  --rules.1.service.protocol="17" \
  --rules.1.service.source_port="1-65535" \
  --rules.1.service.dest_port="123" \
  --rules.1.sequence.top="1"
```

## Deny Rules

### Rule 5: Block High-Risk Regions (Inbound)

**Purpose**: Deny inbound traffic from high-risk geographic regions.

**Compliance**: PCI DSS 1.2, ISO A.8.22

```bash
hcloud CFW AddAclRule \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --object_id="<object_id>" \
  --type="0" \
  --rules.1.name="Finance-Inbound-HighRisk-Deny" \
  --rules.1.address_type="0" \
  --rules.1.direction="0" \
  --rules.1.status="1" \
  --rules.1.action_type="1" \
  --rules.1.long_connect_enable="0" \
  --rules.1.source.type="2" \
  --rules.1.source.region_list_json='[{"region_id":"<region_id>","region_type":0}]' \
  --rules.1.destination.type="0" \
  --rules.1.destination.address="0.0.0.0/0" \
  --rules.1.service.type="0" \
  --rules.1.service.protocol="-1" \
  --rules.1.service.source_port="0" \
  --rules.1.service.dest_port="0" \
  --rules.1.sequence.top="1"
```

> **Note**: Replace `<region_id>` with the actual region IDs for high-risk countries. Use `region_type=0` for countries, `region_type=2` for continents.

### Rule 6: Block Non-Standard Ports (Inbound)

**Purpose**: Deny inbound traffic on non-standard ports to prevent unauthorized access.

**Compliance**: PCI DSS 1.2, ISO A.8.20

```bash
hcloud CFW AddAclRule \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --object_id="<object_id>" \
  --type="0" \
  --rules.1.name="Finance-Inbound-Telnet-Deny" \
  --rules.1.address_type="0" \
  --rules.1.direction="0" \
  --rules.1.status="1" \
  --rules.1.action_type="1" \
  --rules.1.long_connect_enable="0" \
  --rules.1.source.type="0" \
  --rules.1.source.address="0.0.0.0/0" \
  --rules.1.destination.type="0" \
  --rules.1.destination.address="0.0.0.0/0" \
  --rules.1.service.type="0" \
  --rules.1.service.protocol="6" \
  --rules.1.service.source_port="1-65535" \
  --rules.1.service.dest_port="23" \
  --rules.1.sequence.top="1"
```

## Network Segmentation Patterns

### Zone-Based Rule Architecture

```
Internet → [CFW] → DMZ Zone (Public-Facing)
                       ↓
                  App Zone (Business Logic)
                       ↓
                  Data Zone (Databases, Cardholder Data)
                       
                  Management Zone (Admin, VPN Only)
```

| Zone | Inbound Allow | Inbound Deny | Outbound Allow |
|------|---------------|--------------|----------------|
| DMZ | 443, 80 | All other ports | App Zone, DNS, NTP |
| Application | DMZ only | Internet direct | Data Zone, DNS, NTP |
| Data | Application only | All other sources | None (or limited) |
| Management | VPN IP range only | All other sources | All internal, DNS |

## Rule Priority Order

Rules must be ordered as follows (highest priority first):

1. **Deny known malicious IPs** (priority 1-99)
2. **Deny high-risk regions** (priority 100-199)
3. **Deny non-standard ports** (priority 200-299)
4. **Allow HTTPS banking** (priority 300-399)
5. **Allow HTTP redirect** (priority 400-499)
6. **Allow DNS/NTP outbound** (priority 500-599)
7. **Allow internal communication** (priority 600-699)
8. **Default deny all** (implicit, lowest priority)

## ACL Rule Parameter Reference

| Parameter | Values | Description |
|-----------|--------|-------------|
| address_type | 0 (IPv4), 1 (IPv6) | IP address type |
| direction | 0 (Inbound), 1 (Outbound) | Traffic direction |
| action_type | 0 (Permit), 1 (Deny) | Rule action |
| status | 0 (Disabled), 1 (Enabled) | Rule status |
| protocol | 6 (TCP), 17 (UDP), 1 (ICMP), -1 (Any) | Protocol type |
| source.type | 0 (IP), 2 (Region) | Source address type |
| long_connect_enable | 0 (Disabled), 1 (Enabled) | Long connection support |
| sequence.top | 1 | Insert at top of rule list |

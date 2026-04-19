# Logging and Alarm Configuration for Finance

## Overview

This document covers LTS (Log Tank Service) logging and SMN (Simple Message Notification) alarm configuration for financial workloads on Huawei Cloud CFW. Proper logging and alerting are mandatory for PCI DSS compliance and financial audit requirements.

## LTS Logging Configuration

### Enable LTS Integration

```bash
# Check current log status
hcloud CFW ListLogConfig \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>"

# Enable LTS logging
hcloud CFW AddLogConfig \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --lts_enable="1"
```

### Log Types and Retention

CFW generates the following log types. Financial institutions must meet minimum retention requirements:

| Log Type | Description | Min Retention | Storage | Compliance Basis |
|----------|-------------|---------------|---------|-----------------|
| Attack Logs | Security events and threat detections | 365 days | LTS + OBS | PCI DSS 10.3, ISO A.8.15 |
| IPS Logs | Intrusion prevention events | 365 days | LTS + OBS | PCI DSS 10.3, ISO A.8.15 |
| Flow Logs | Traffic flow records | 90 days | LTS | PCI DSS 10.1 |
| ACL Logs | Access control decisions | 180 days | LTS | ISO A.8.15 |
| System Logs | CFW system events | 90 days | LTS | Operational requirement |

### Log Retention Configuration

For long-term retention beyond LTS default, configure OBS (Object Storage Service) archival:

```
Attack Logs → LTS (hot, 30 days) → OBS (cold, 335 days) = 365 days total
IPS Logs   → LTS (hot, 30 days) → OBS (cold, 335 days) = 365 days total
Flow Logs  → LTS (hot, 90 days) = 90 days total
ACL Logs   → LTS (hot, 180 days) = 180 days total
System Logs → LTS (hot, 90 days) = 90 days total
```

### Log Query for Audit

```bash
# Query attack logs
hcloud CFW ListAttackLogs \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --limit="100" \
  --offset="0"

# Query access control logs
hcloud CFW ListAccessControlLogs \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --limit="100" \
  --offset="0"
```

## Alarm Configuration

### Alarm Types

| Type | Value | Description | Financial Relevance |
|------|-------|-------------|-------------------|
| Attack Alarm | 0 | Security threat notifications | Critical for incident response |
| Bandwidth Alarm | 1 | Traffic threshold alerts | DDoS detection, capacity planning |
| Resource Alarm | 2 | Capacity warnings | Prevent service degradation |

### Check Current Alarm Configuration

```bash
hcloud CFW ShowAlarmConfig \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>"
```

### Enable Attack Alarms

```bash
hcloud CFW UpdateAlarmConfig \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --alarm_type="0" \
  --enable_status="1" \
  --frequency_count="10" \
  --frequency_time="5" \
  --severity="CRITICAL,HIGH,MEDIUM"
```

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| alarm_type | 0 | Attack alarm type |
| enable_status | 1 | Enable the alarm |
| frequency_count | 10 | Alert after 10 events in window |
| frequency_time | 5 | 5-minute sliding window |
| severity | CRITICAL,HIGH,MEDIUM | All significant threats for finance |

### Enable Bandwidth Alarms

```bash
hcloud CFW UpdateAlarmConfig \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --alarm_type="1" \
  --enable_status="1" \
  --severity="1"
```

### Enable Resource Alarms

```bash
hcloud CFW UpdateAlarmConfig \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --alarm_type="2" \
  --enable_status="1" \
  --severity="3"
```

## Alarm Notification Flow

```
Threat Detected
      ↓
CFW Engine Analysis
      ↓
Alarm Generated
      ↓
SMN Topic Notification
      ↓
┌─────────────────────────────────┐
│  Notification Channels:         │
│  • Email to security team      │
│  • SMS to on-call personnel    │
│  • Webhook to SIEM/SOAR       │
│  • Chat to incident channel    │
└─────────────────────────────────┘
```

## SMN Topic Configuration

For alarm notifications, configure an SMN topic with appropriate subscriptions:

1. Create SMN topic for CFW alarms
2. Subscribe security team email
3. Subscribe on-call SMS
4. Subscribe SIEM webhook (if available)
5. Test notification delivery

## Monitoring Metrics

### Key Metrics to Monitor

| Metric | Description | Alert Threshold | Action |
|--------|-------------|-----------------|--------|
| Inbound traffic volume | Total inbound bandwidth | > 80% of capacity | Investigate potential DDoS |
| Attack event count | Security events per minute | > 100/min | Escalate to security team |
| Top attacked IP | Most targeted IP address | Any | Review and block if needed |
| Rule hit rate | Most active ACL rules | Low hit rate | Review for rule optimization |
| Blocked traffic ratio | Denied vs. total connections | Sudden increase | Check for attack campaign |
| IPS signature matches | Top matching IPS signatures | Any new signature | Review and tune |

### Monitoring Commands

```bash
# View attack statistics
hcloud CFW ListAttackStatistic \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --start_time="<start_time>" \
  --end_time="<end_time>"

# View traffic flow trend
hcloud CFW ShowFlowTrend \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --direction="0"

# View top attacks
hcloud CFW ShowAttackTop \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --start_time="<start_time>" \
  --end_time="<end_time>"
```

## Compliance Audit Trail

For financial audit, maintain the following records:

1. **Configuration change log**: All CFW configuration changes with timestamps
2. **Rule review log**: Periodic ACL rule reviews with sign-off
3. **Alarm response log**: All alarm events and response actions
4. **IPS event log**: All IPS detections and blocks
5. **Access review log**: Quarterly access control reviews

## Log and Alarm Validation

After configuration, validate:

```bash
# Verify LTS is enabled
hcloud CFW ListLogConfig \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>"
# Expected: lts_enable = 1

# Verify alarm configuration
hcloud CFW ShowAlarmConfig \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>"
# Expected: All three alarm types with enable_status = 1
```

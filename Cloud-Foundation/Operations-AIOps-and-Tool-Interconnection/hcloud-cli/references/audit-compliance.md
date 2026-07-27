# Audit and Compliance Operations

Query audit trails, compliance status, and security posture across Huawei Cloud services.

## CTS — Cloud Trace Service

CTS records API calls made in your account. Use it to audit who did what, when.

### List trackers

```bash
hcloud CTS ListTrackers --cli-region=X --cli-output=json
```

### Create a tracker

A tracker sends trace events to an OBS bucket for long-term storage:

```bash
hcloud --dryrun CTS CreateTracker --cli-region=X \
  --tracker.name=default \
  --bucket_name=audit-logs-bucket \
  --file_prefix_name=cts

hcloud CTS CreateTracker --cli-region=X \
  --tracker.name=default \
  --bucket_name=audit-logs-bucket \
  --file_prefix_name=cts
```

### List operations (traceable APIs)

```bash
hcloud CTS ListOperations --cli-region=X --cli-output=json
```

### Notifications

Configure notifications for specific trace events:

```bash
# List notifications
hcloud CTS ListNotifications --cli-region=X --cli-output=json

# Create notification (e.g., alert on delete operations)
hcloud CTS CreateNotification --cli-region=X \
  --notification.name=delete-alert \
  --notification.operations.1.service=ECS \
  --notification.operations.1.resource=servers \
  --notification.operations.1.trace=DeleteServers \
  --notification.topic_id=SMN_TOPIC_URN
```

### Check OBS buckets for CTS

```bash
hcloud CTS CheckObsBuckets --cli-region=X --cli-output=json
```

## Config — Resource Configuration

Config evaluates resource compliance against rules. Available in international regions.

### Resource summary

```bash
# All resources summary
hcloud Config CollectAllResourcesSummary --cli-region=X --cli-output=json

# Tracked resources summary
hcloud Config CollectTrackedResourcesSummary --cli-region=X --cli-output=json
```

### Policy compliance

```bash
# Policy states summary
hcloud Config CollectPolicyStatesSummary --cli-region=X --cli-output=json

# Policy assignments states
hcloud Config CollectPolicyAssignmentsStatesSummary --cli-region=X --cli-output=json

# Resource-level policy states
hcloud Config CollectResourcesPolicyStatesSummary --cli-region=X --cli-output=json
```

### Conformance packs

```bash
hcloud Config CollectConformancePackComplianceSummary --cli-region=X --cli-output=json
```

### Remediation

```bash
# Remediation execution status
hcloud Config CollectRemediationExecutionStatusesSummary --cli-region=X --cli-output=json

# Manage remediation exceptions
hcloud Config BatchCreateRemediationExceptions --cli-region=X ...
hcloud Config BatchDeleteRemediationExceptions --cli-region=X ...
```

## HSS — Host Security Service

HSS provides intrusion detection, vulnerability scanning, and baseline checks for hosts.

### Query hosts

```bash
# List protected hosts
hcloud HSS ListHosts --cli-region=X --cli-output=json

# Host details
hcloud HSS ShowHost --cli-region=X --host_id=HOST_ID --cli-output=json
```

### Vulnerabilities

```bash
# List vulnerabilities
hcloud HSS ListVulHosts --cli-region=X --cli-output=json

# Vulnerability statistics
hcloud HSS ShowVulStats --cli-region=X --cli-output=json
```

### Baseline checks

```bash
# List baseline checks
hcloud HSS ListBaselineHosts --cli-region=X --cli-output=json

# Baseline stats
hcloud HSS ShowBaselineStats --cli-region=X --cli-output=json
```

### Intrusion detection

```bash
# List intrusion events
hcloud HSS ListAlarmEvents --cli-region=X --cli-output=json

# Event details
hcloud HSS ShowAlarmEvent --cli-region=X --event_id=EVENT_ID --cli-output=json
```

### Whitelists

```bash
# Login whitelist
hcloud HSS ListLoginWhiteList --cli-region=X --cli-output=json

# Process whitelist
hcloud HSS ListAppWhitelistHosts --cli-region=X --cli-output=json
```

### Policy groups

```bash
# List policy groups
hcloud HSS ListPolicyGroups --cli-region=X --cli-output=json
```

## SecMaster — Security Master

SecMaster is the security orchestration platform for incident management, alerts, and playbooks.

### Alerts

```bash
# List alerts
hcloud SecMaster ListAlerts --cli-region=X --cli-output=json

# Alert details
hcloud SecMaster ShowAlert --cli-region=X --alert_id=ALERT_ID --cli-output=json

# Update alert status (e.g., acknowledge)
hcloud SecMaster ChangeAlert --cli-region=X --alert_id=ALERT_ID --status=Acknowledged
```

### Incidents

```bash
# List incidents
hcloud SecMaster ListIncidents --cli-region=X --cli-output=json

# Incident details
hcloud SecMaster ShowIncident --cli-region=X --incident_id=INCIDENT_ID --cli-output=json

# Update incident status
hcloud SecMaster ChangeIncident --cli-region=X --incident_id=INCIDENT_ID --status=Closed
```

### Playbooks

```bash
# List playbooks
hcloud SecMaster ListPlaybooks --cli-region=X --cli-output=json

# Playbook details
hcloud SecMaster ShowPlaybook --cli-region=X --playbook_id=PLAYBOOK_ID --cli-output=json
```

### Data objects (indicators, observables)

```bash
# List data objects
hcloud SecMaster ListDataobjects --cli-region=X --cli-output=json
```

## RMS — Resource Management Service

**Note**: RMS is primarily available in China regions. For international regions, use `Config` instead.

### Resource tracking

```bash
# All resources summary
hcloud RMS CollectAllResourcesSummary --cli-region=cn-north-4 --cli-output=json

# Count all resources
hcloud RMS CountAllResources --cli-region=cn-north-4 --cli-output=json
```

### Policy assignments

```bash
# List policy assignments
hcloud RMS ListPolicyAssignments --cli-region=cn-north-4 --cli-output=json

# Create policy assignment
hcloud RMS CreatePolicyAssignments --cli-region=cn-north-4 ...
```

### Configuration aggregators

```bash
# List aggregators
hcloud RMS ListConfigurationAggregators --cli-region=cn-north-4 --cli-output=json

# Create aggregator
hcloud RMS CreateConfigurationAggregator --cli-region=cn-north-4 ...
```

### Stored queries

```bash
# List stored queries
hcloud RMS ListStoredQueries --cli-region=cn-north-4 --cli-output=json

# Create stored query
hcloud RMS CreateStoredQuery --cli-region=cn-north-4 ...
```

## CES — Cloud Eye (Monitoring)

While not strictly audit, CES alarm rules are part of the compliance picture.

### Alarm rules

```bash
# List alarm rules
hcloud CES ListAlarmHistories --cli-region=X --cli-output=json

# List alarm templates
hcloud CES ListAlarmTemplates --cli-region=X --cli-output=json
```

### Metrics

```bash
# List metrics for a namespace
hcloud CES ListMetrics --cli-region=X --namespace=SYS.ECS --cli-output=json --cli-query='metrics[].{name:metric_name,dimensions:dimensions}'
```

### Resource groups

```bash
hcloud CES ListResourceGroups --cli-region=X --cli-output=json
```

## Common audit workflows

### "Who deleted this resource?"

```bash
# 1. Check CTS tracker exists
hcloud CTS ListTrackers --cli-region=X --cli-output=json

# 2. If no tracker, create one first (for future events)
hcloud CTS CreateTracker --cli-region=X --tracker.name=default --bucket_name=audit-bucket

# 3. Query trace events in the OBS bucket
# (CTS stores traces as JSON files in OBS — use OBS CLI to read them)
hcloud obs ls obs://audit-bucket/cts/ --cli-region=X
```

### "Are my resources compliant?"

```bash
# International regions: use Config
hcloud Config CollectPolicyStatesSummary --cli-region=X --cli-output=json

# Check for non-compliant resources
hcloud Config CollectResourcesPolicyStatesSummary --cli-region=X --cli-output=json
```

### "What security issues exist on my hosts?"

```bash
# 1. Check HSS hosts
hcloud HSS ListHosts --cli-region=X --cli-output=json --cli-query='data[].{name:host_name,id:host_id,status:protect_status}'

# 2. Check vulnerabilities
hcloud HSS ShowVulStats --cli-region=X --cli-output=json

# 3. Check baseline compliance
hcloud HSS ShowBaselineStats --cli-region=X --cli-output=json

# 4. Check intrusion events
hcloud HSS ListAlarmEvents --cli-region=X --cli-output=json
```

### "What alerts are active?"

```bash
# SecMaster alerts
hcloud SecMaster ListAlerts --cli-region=X --cli-output=json --cli-query='data[].{id:id,name:name,severity:severity,status:status}'

# CES alarm histories
hcloud CES ListAlarmHistories --cli-region=X --cli-output=json
```

## Best practices

1. **Always have a CTS tracker** — without it, API calls are not recorded. Check with `ListTrackers` and create if missing.
2. **Use Config for compliance** — define policy assignments and check `CollectPolicyStatesSummary` regularly.
3. **Monitor HSS agent status** — hosts with `protect_status != open` are unprotected.
4. **Respond to SecMaster alerts** — check `ListAlerts` and acknowledge/investigate.
5. **Archive CTS traces** — configure OBS lifecycle rules to archive old trace files.
6. **Note RMS region restrictions** — RMS is China-region only; use Config for international.

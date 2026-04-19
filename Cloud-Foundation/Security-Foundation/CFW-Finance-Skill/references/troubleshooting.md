# CFW Troubleshooting Guide for Finance

## Common Issues and Solutions

### Issue 1: CFW Instance Not Starting

**Symptoms**:
- Instance status remains in "Creating" state
- No protection object ID returned
- API returns timeout or internal error

**Diagnostic Commands**:
```bash
# Check instance status
hcloud CFW ListFirewallDetail \
  --cli-region="<region>" \
  --limit="10" \
  --offset="0" \
  --service_type="0"

# Check job status
hcloud CFW ListJob \
  --cli-region="<region>" \
  --job_id="<job_id>"

# Verify resource quotas
hcloud CFW ShowConfigQuota \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>"
```

**Solutions**:
1. Wait for instance creation to complete (may take 5-10 minutes)
2. Verify account has sufficient quotas
3. Check IAM permissions include `cfw:*:*`
4. Retry creation if job failed

### Issue 2: IPS Rules Not Applied

**Symptoms**:
- Attacks not being blocked
- IPS status shows disabled
- Protection mode is observation instead of strict

**Diagnostic Commands**:
```bash
# Verify IPS status
hcloud CFW ListIpsSwitchStatus \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --object_id="<object_id>"

# Check protection mode
hcloud CFW ListIpsProtectMode \
  --cli-region="<region>" \
  --object_id="<object_id>"
```

**Solutions**:
1. Enable basic defense: `ChangeIpsSwitchStatus` with `ips_type` not needed (auto-enabled)
2. Enable virtual patching: `ChangeIpsSwitchStatus` with `ips_type=2, status=1`
3. Switch to protection mode: `ChangeIpsProtectMode` with `mode=1`
4. Verify after each change

### Issue 3: ACL Rules Not Working

**Symptoms**:
- Traffic not matching rules
- Unexpected allow/deny behavior
- Rules created but not taking effect

**Diagnostic Commands**:
```bash
# List all ACL rules
hcloud CFW ListAclRules \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --object_id="<object_id>" \
  --limit="100" \
  --offset="0"

# Check rule hit counts
hcloud CFW ListAclRuleHitCount \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>"

# Check rule hit status
hcloud CFW ListAclRuleHitStatus \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>"
```

**Solutions**:
1. Check rule priority order (deny rules should come before allow rules)
2. Verify rule status is enabled (`status=1`)
3. Confirm address and port configurations are correct
4. Review rule direction (`direction=0` for inbound, `1` for outbound)
5. Check if `long_connect_enable` is set (required parameter)
6. Ensure `sequence.top=1` for proper rule ordering

### Issue 4: Internal Server Error (CFW.00000500)

**Symptoms**:
- API returns `{"error_code":"CFW.00000500","error_msg":"Internal Server Error"}`
- Rule creation fails intermittently

**Common Causes**:
1. Missing required parameter `long_connect_enable`
2. Missing `sequence.top` for rule ordering
3. Invalid `source_port` format (use `1-65535` not `0`)
4. Private IP addresses on Internet border (use VPC border instead)

**Solutions**:
1. Always include `long_connect_enable="0"` in ACL rule creation
2. Always include `sequence.top="1"` for rule insertion
3. Use `source_port="1-65535"` for full range, not `0`
4. For private IP rules, use VPC border protection object (type=1)

### Issue 5: Private IP Not Supported

**Symptoms**:
- Error: `{"error_code":"CFW.00200071","error_msg":"Private IP is not supported"}`

**Cause**: Internet border CFW (type=0) does not support private IP addresses (e.g., 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)

**Solutions**:
1. Use public IP addresses for Internet border rules
2. For internal network segmentation, use VPC border protection (type=1)
3. Create East-West firewall for VPC-to-VPC traffic

### Issue 6: LTS Logging Not Working

**Symptoms**:
- No logs appearing in LTS
- `lts_enable` shows 0 after enabling

**Diagnostic Commands**:
```bash
# Check log configuration
hcloud CFW ListLogConfig \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>"
```

**Solutions**:
1. Verify LTS service is available in the region
2. Re-enable logging: `AddLogConfig` with `lts_enable="1"`
3. Check IAM permissions include `lts:*:*`
4. Verify LTS log group and topic exist

### Issue 7: Alarms Not Triggering

**Symptoms**:
- No alarm notifications received
- Attack events occur but no SMN notification

**Diagnostic Commands**:
```bash
# Check alarm configuration
hcloud CFW ShowAlarmConfig \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>"
```

**Solutions**:
1. Verify `enable_status=1` for all alarm types
2. Check SMN topic configuration and subscriptions
3. Verify alarm severity levels include the events being generated
4. Check `frequency_count` and `frequency_time` thresholds
5. Test SMN topic delivery independently

## Diagnostic Workflow

```
1. Identify symptom
2. Run diagnostic command for the specific issue
3. Analyze response for configuration gaps
4. Apply fix using the appropriate API call
5. Re-run diagnostic to verify fix
6. Document the issue and resolution
```

## Emergency Procedures

### Disable a Problematic ACL Rule

```bash
# Batch update rule action to disable
hcloud CFW BatchUpdateAclRuleActions \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --object_id="<object_id>" \
  --action="1"
```

### Delete a Specific ACL Rule

```bash
hcloud CFW DeleteAclRule \
  --cli-region="<region>" \
  --fw_instance_id="<fw_instance_id>" \
  --object_id="<object_id>" \
  --acl_rule_id="<rule_id>"
```

### Check Firewall Bypass Status

If CFW appears to not be inspecting traffic, check if bypass mode is enabled:

```bash
hcloud CFW ListFirewallDetail \
  --cli-region="<region>" \
  --limit="10" \
  --offset="0" \
  --service_type="0"
```

## Support Escalation

If issues cannot be resolved with the above procedures:

1. Collect diagnostic output from all relevant commands
2. Note the CFW instance ID, region, and timestamp
3. Document the expected vs. actual behavior
4. Submit a support ticket via Huawei Cloud Console
5. For production-impacting issues, request priority escalation

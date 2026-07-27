# Troubleshooting

Common SMS migration failures, error codes, and their fixes.

## Error Codes

### SMS.0515 — Firmware Type Mismatch

**Symptom**: Migration task fails at `SSL_CONFIG` step with `MIGRATE_FAIL`.

**Error**: `"error_code":"SMS.0515","error_msg":"Inconsistent firmware type. Source: UEFI, Target: BIOS"`

**Cause**: Source server uses UEFI firmware, target ECS uses BIOS firmware (or vice versa).

**Fix**: Switch to SMS Server Template approach (`vm_template_id`). SMS will auto-create the target with matching firmware. See [firmware-compatibility.md](firmware-compatibility.md) for details.

If you must use pre-created ECS, create a private image with the correct firmware type (UEFI) and use it to create the target ECS.

### SMS.6103 — Missing diskId in Disk Node

**Symptom**: SMS task creation fails immediately.

**Error**: `"error_code":"SMS.6103","error_msg":"Missing diskId in disk node!"`

**Cause**: When using `target_server_id` (pre-created ECS), `target_server_disks` must be specified with at least `disk_id` for each disk. Omitting it or providing incomplete disk info triggers this error.

**Fix**: Add `target_server_disks` block with `disk_id`, `name`, `size`, `device_type`, and `physical_volumes` matching the source server's disk layout.

```hcl
target_server_disks {
  name        = "/dev/sda"
  size        = 10240     # MB
  device_type = "BOOT"
  disk_id     = "0"
  # ... physical_volumes ...
}
```

Or switch to `vm_template_id` approach which doesn't require explicit disk config.

### Ecs.0005 — Root Volume Size Too Small

**Symptom**: ECS creation fails during `terraform apply`.

**Error**: `"root volume size is [8], must over image mindisk [10]"`

**Cause**: The specified `system_disk_size` is smaller than the minimum disk size required by the image.

**Fix**: Increase `system_disk_size` to at least the image's `min_disk_gb`. For HuaweiCloud Ubuntu 22.04, this is typically 10 GB.

```hcl
system_disk_size = 10  # was 8
```

### SMS Agent Connection Lost

**Symptom**: Source server `state` changes to `"error"`, `connected: false`.

**Cause**: Network connectivity between the SMS Agent and the SMS service endpoint was lost.

**Fix**:
1. Check source server internet connectivity: `curl -v https://<sms-endpoint>`
2. Check agent process: `ps aux | grep linuxmain`
3. Restart agent if needed: `sudo systemctl restart sms-agent` (or equivalent)
4. Verify reconnection: `hcloud SMS ShowServer --source_id=<id> --cli-region=<sms-region>`

### SSL_CONFIG Stuck at 0%

**Symptom**: Migration task is `RUNNING` but `SSL_CONFIG` subtask stays at 0%.

**Cause**: Target ECS is stopped (SHUTOFF). SMS needs the target running to establish the SSL channel.

**Fix**: Start the target ECS before creating the SMS task. If using pre-created ECS with `power_action = "OFF"`, change to `"ON"` or remove it. If using SMS Server Template, SMS handles this automatically.

## hcloud CLI Region Limitations

### Problem

Many hcloud CLI commands don't support all HuaweiCloud regions. For example, `la-north-2` may not be in the supported list for SMS commands.

```
[USE_ERROR]The value of cli-region in the current profile is not supported.
Supported regions: my-kualalumpur-1, ap-southeast-3, cn-north-4, ap-southeast-1, ru-moscow-1
```

### Fix

Always specify `--cli-region=<sms-region>` for SMS API calls, where `<sms-region>` is one of the supported SMS regions (e.g. `ap-southeast-3`). The target ECS region is separate and specified in the Terraform provider config.

```bash
# SMS API calls — use SMS region
hcloud SMS ShowTask --task_id=<id> --cli-region=ap-southeast-3

# ECS API calls — use target region
hcloud ECS ShowServer --server_id=<id>  # uses default profile region (la-north-2)
```

## Terraform Issues

### Bandwidth block doesn't support "name"

**Error**: `An argument named "name" is not expected here.`

**Cause**: The `bandwidth` block in `huaweicloud_compute_instance` doesn't have a `name` parameter.

**Fix**: Remove the `name` field from the `bandwidth` block.

```hcl
# Wrong
bandwidth {
  name = "my-eip"  # NOT supported
  size = 10
  ...
}

# Correct
bandwidth {
  size = 10
  share_type  = "PER"
  charge_mode = "traffic"
}
```

### target_server_id requires migration_ip

**Error**: `all of migration_ip,target_server_id must be specified`

**Cause**: When using `target_server_id` in `huaweicloud_sms_task`, `migration_ip` is also required.

**Fix**: Add `migration_ip` set to the target ECS's public IP (for Internet migration) or private IP (for VPN/Direct Connect).

```hcl
migration_ip = huaweicloud_compute_instance.target.public_ip
```

### power_action is one-time

**Behavior**: `power_action` in `huaweicloud_compute_instance` is a one-time action, not a desired state. Terraform executes it during apply but doesn't track it in state.

**Implication**: On subsequent `terraform plan` runs, `power_action` won't show as a diff even if the ECS power state doesn't match. This is by design.

**Values**: `ON`, `OFF`, `REBOOT`, `FORCE-OFF`, `FORCE-REBOOT`

## Migration Task Stuck or Failed

### Check task details

```bash
hcloud SMS ShowTask --task_id=<task-id> --cli-region=<sms-region> --cli-output=json
```

Look for:
- `state`: `RUNNING`, `MIGRATE_FAIL`, `MIGRATE_SUCCESS`
- `error_json`: Error code and message
- `subtask_info`: Current subtask and progress
- `sub_tasks[]`: Per-subtask progress

### Restart a failed task

```bash
# Delete the failed task
hcloud SMS DeleteTask --task_id=<task-id> --cli-region=<sms-region>

# Or via Terraform
terraform destroy -target=huaweicloud_sms_task.migration -auto-approve

# Recreate (fix the underlying issue first!)
terraform apply -auto-approve
```

### Check source server state

```bash
hcloud SMS ShowServer --source_id=<source-id> --cli-region=<sms-region> --cli-output=json
```

If `state` is `"error"`, the agent may need to be restarted or re-registered.

## Common Pitfalls

| Pitfall | Impact | Prevention |
|---------|--------|------------|
| Using pre-created ECS with wrong firmware | SMS.0515 failure | Use SMS Server Template |
| Omitting target_server_disks with target_server_id | SMS.6103 failure | Use template approach or add disk config |
| Disk too small for image | Ecs.0005 failure | Check image min_disk_gb |
| Target ECS stopped for SSL_CONFIG | SSL stuck at 0% | Start ECS or use template |
| Wrong SMS region for API calls | CLI error | Use --cli-region=<sms-region> |
| Agent loses connectivity | MIGRATE_FAIL | Ensure stable internet connection |
| fstab LABEL= references | Warning during install | Non-blocking, accept with `y` |

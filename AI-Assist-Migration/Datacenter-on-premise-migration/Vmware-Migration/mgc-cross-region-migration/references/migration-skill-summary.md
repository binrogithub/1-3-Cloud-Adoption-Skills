# Migration Skill Summary (VMware -> Mexico City2, rsync over VPN Bridge)

## Scope

- Skill path: `skills/mgc-cross-region-migration`
- Objective: migrate on-prem VMware workloads to Huawei Cloud with Terraform + MGC script.
- Current proven scenario: `la-north-2` (Mexico City2), `SMS.6504` source incompatibility, automatic rsync path.

## Canonical Process

1. Validate source registration/permissions/target image/quota.
2. Populate `terraform.tfvars` with migration + VPN bridge + rsync parameters.
3. Run `terraform init` then `terraform apply -auto-approve`.
4. If apply reports `No changes`, force rerun with:
   - `terraform apply -replace=terraform_data.mgc_region_migration -auto-approve`
5. Confirm run output from:
   - `out/migration_result.json`
   - `out/precheck_source_checks.json`
   - `out/rsync_execution.json` (when fallback is used)
6. Validate postcheck:
   - VPC name is `vpc-migration`
   - EIP exists with 100M bandwidth and `postPaid`
   - security-group connectivity rules are present
7. If source->target SSH fails after rsync, inspect ECS console output before changing SG/VPC.

## Proven Automation Behaviors

- Auto creates/reuses target VPC/subnet and target ECS.
- Auto binds dedicated EIP (100 Mbps, pay-as-you-go).
- Auto adds source/target SG reachability rules.
- Auto switches from SMS to rsync when source precheck returns `SMS.6504`.
- Supports VPN bridge routing through OpenVPN + VPC peering.
- Treats rsync return code `23/24` as non-fatal partial/vanished warning.

## Latest Validated VMware Run (2026-05-01)

- Source SMS/VM ID: `3574494d-5e3d-40c1-9170-13075d7ac3dc`
- Source host used for rsync: `192.168.229.128`
- Target region: `la-north-2`
- Target ECS ID: `fdef023a-4a00-4d4d-b0fe-771498061653`
- Target fixed IP: `10.250.1.107`
- Target EIP: `46.250.163.126`
- Target VPC: `vpc-migration` (`52e6bbac-6ff9-4c90-ba95-4ff6f9660b62`)
- SMS precheck reason: `OS_VERSION:SMS.6504`
- Migration method: `rsync`
- rsync state: `FULL_SYNCED`
- full_sync started (CN): `2026-05-01 03:35:17 +0800`
- full_sync finished (CN): `2026-05-01 04:48:28 +0800`
- full_sync duration: `4391s`

## SSH Failure Pattern and Recovery

- Symptom:
  - `kex_exchange_identification: read: Connection reset by peer`
  - `Connection closed by <target-ip> port 22`
  - `Connection timed out`
- Root cause in this case:
  - Target boot entered emergency mode because rsync copied stale `/etc/fstab` UUIDs.
  - Missing UUIDs:
    - `7c37581b-bc60-4c6c-8552-1517b33413c9`
    - `87a3ba70-e0f3-4f1c-842d-1691208ba04c`
- Recovery SOP:
  1. Open ECS VNC/serial console.
  2. Enter emergency shell as root.
  3. `mount -o remount,rw /sysroot && chroot /sysroot`
  4. Backup and fix `/etc/fstab` (remove/fix invalid UUID mounts or add `nofail`).
  5. Reboot and re-test source->target SSH.

## Preventive Rule Added to Skill

- Exclude `/etc/fstab` from rsync by default to avoid target boot breakage.
- Keep post-rsync boot health validation mandatory before declaring migration complete.

## Evidence Files

- `out/migration_result.json`
- `out/precheck_source_checks.json`
- `out/rsync_execution.json`
- `out/postcheck_network_vmware_mx2_latest.json`

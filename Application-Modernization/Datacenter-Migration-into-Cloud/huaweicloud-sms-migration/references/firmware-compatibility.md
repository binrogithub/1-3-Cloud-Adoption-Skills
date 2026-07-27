# Firmware Compatibility

Firmware mismatch is the most common cause of SMS migration failures when using the pre-created ECS approach. This document explains the issue and how to avoid it.

## Background

Server firmware (boot mode) determines how the OS is loaded at startup. The two types are:

| Firmware | Partition Style | Boot Mode | Typical Use |
|----------|----------------|-----------|-------------|
| **UEFI** | GPT | UEFI boot | Modern cloud VMs (AWS m7i, Azure v5, etc.) |
| **BIOS** (Legacy) | MBR | Legacy BIOS boot | Older VMs, some cloud default images |

**SMS requires the source and target to use the same firmware type.** If they differ, the migrated server will not boot.

## Source Cloud Firmware Defaults

Different cloud providers use different firmware defaults for their Linux images:

| Cloud | OS | Default Firmware | Partition Style | Disk Device |
|-------|-----|-----------------|----------------|-------------|
| AWS | Ubuntu 22.04+ | **UEFI** | GPT | NVMe (`/dev/nvme0n1`) |
| AWS | Ubuntu 20.04 | BIOS | MBR | NVMe (`/dev/nvme0n1`) |
| AWS | Amazon Linux 2 | BIOS | MBR | NVMe (`/dev/nvme0n1`) |
| Azure | Ubuntu 22.04+ | **UEFI** | GPT | SCSI (`/dev/sda`) |
| GCP | Ubuntu 22.04+ | **UEFI** | GPT | SCSI (`/dev/sda`) |
| HuaweiCloud | Ubuntu 22.04 (public) | **BIOS** | MBR | VBD (`/dev/vda`) |
| HuaweiCloud | Ubuntu 22.04 (UEFI image) | **UEFI** | GPT | VBD (`/dev/vda`) |
| On-prem | Varies | Varies | Varies | Varies |

**Key issue**: Most modern cloud providers (AWS, Azure, GCP) default to UEFI for recent Linux images. HuaweiCloud public images typically use BIOS. This mismatch causes migration failures.

## How to Check Firmware Type

### On the source server

```bash
# Check if UEFI is used
ls /sys/firmware/efi 2>/dev/null && echo "UEFI" || echo "BIOS"

# Check partition style
sudo parted -l  # Look for "Partition Table: gpt" or "msdos"

# Check disk devices
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
```

### From SMS source server data

After registering the source server with SMS, the `ShowServer` API response includes:

```json
{
  "firmware": "UEFI",  // or "BIOS"
  "disks": [
    {
      "name": "/dev/nvme0n1",
      "partition_style": "GPT",  // or "MBR"
      "physical_volumes": [...]
    }
  ]
}
```

## How SMS Server Template Handles This

When using `huaweicloud_sms_server_template` (the recommended approach):

1. SMS reads the source server's firmware type (UEFI or BIOS)
2. SMS selects a compatible image for the target ECS
3. SMS creates the target ECS with matching firmware
4. Migration proceeds without firmware errors

**This is why the template approach is strongly recommended over pre-creating the ECS.**

## Pre-create ECS: The Firmware Trap

When using `target_server_id` (pre-created ECS):

1. You create the ECS from a HuaweiCloud public image (typically BIOS)
2. The source server uses UEFI
3. SMS detects the mismatch and fails with `SMS.0515`

### Error message

```
Error: Inconsistent firmware type. Source: UEFI, Target: BIOS
```

### Fix Option A: Use SMS Server Template (recommended)

Switch to `vm_template_id` approach. SMS handles firmware automatically.

### Fix Option B: Create a UEFI image

If you must use pre-created ECS, create a private UEFI image:

1. Upload an image file to OBS
2. Create a private image with UEFI boot mode via IMS console or API
3. Use the UEFI image to create the target ECS

#### Via IMS API

```bash
# Update an existing image's firmware type to UEFI
hcloud IMS UpdateImage --cli-region=<region> \
  --image_id=<image-id> \
  --op=add \
  --path=/hw_firmware_type \
  --value=uefi
```

#### Via IMS Console

1. Go to IMS console → Create Image → Import Image
2. Set Type = System disk image
3. Set Boot Mode = **UEFI**
4. Use the resulting private image to create the target ECS

## Disk Device Name Mapping

SMS automatically maps source disk device names to target device names:

| Source Cloud | Source Device | Target Device | Notes |
|-------------|---------------|---------------|-------|
| AWS (Nitro) | `/dev/nvme0n1` | `/dev/vda` | NVMe → VBD mapping |
| Azure | `/dev/sda` | `/dev/vda` | SCSI → VBD mapping |
| On-prem | `/dev/sda` | `/dev/vda` | Direct mapping |

This mapping is handled automatically by SMS during migration. The migrated OS will reference `/dev/vda*` instead of the original device names.

## Partition Style Conversion

| Source | Target (template) | Notes |
|--------|-------------------|-------|
| GPT (UEFI) | GPT (UEFI) | Preserved with template approach |
| MBR (BIOS) | MBR (BIOS) | Preserved with template approach |
| GPT → MBR | Not recommended | Requires manual conversion, may lose EFI partition |

**Important**: UEFI systems typically have an EFI System Partition (ESP) mounted at `/boot/efi` with `vfat` filesystem. This partition must be preserved in the migration. The template approach handles this automatically.

## fstab Considerations

The source server's `/etc/fstab` may reference devices by:
- Device path (`/dev/nvme0n1p1`) — SMS updates these to target device names
- UUID (`UUID=abc123`) — Preserved, works as-is
- Label (`LABEL=cloudimg-rootfs`) — May generate warnings during agent install, non-blocking

After migration, verify `/etc/fstab` references are correct for the target device names.

## References

- [HuaweiCloud FAQ: UEFI/BIOS firmware mismatch](https://support.huaweicloud.com/intl/en-us/sms_faq/sms_faq_0051.html)
- [HuaweiCloud IMS: Creating images with UEFI](https://support.huaweicloud.com/intl/en-us/usermanual-ims/ims_01_0203.html)

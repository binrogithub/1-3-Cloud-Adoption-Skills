# SMS Agent Installation

The SMS Agent must be installed on the source server to register it with the HuaweiCloud SMS service. The agent collects source server information (OS, disks, network) and performs the actual data replication during migration.

## Prerequisites

- HuaweiCloud AK/SK (ask the user — never guess)
- SMS endpoint URL (region-specific, e.g. `sms.ap-southeast-3.myhuaweicloud.com`)
- SSH access to the source server (root or sudo)
- Internet access from the source server to the SMS endpoint

## SMS Endpoint Regions

The SMS service is only available in specific regions. The endpoint determines which SMS service instance the agent registers with.

| SMS Region | Endpoint | Target Regions Supported |
|------------|----------|-------------------------|
| ap-southeast-3 | `sms.ap-southeast-3.myhuaweicloud.com` | la-north-2, ap-southeast-3, etc. |
| cn-north-4 | `sms.cn-north-4.myhuaweicloud.com` | cn-north-4, cn-north-1, etc. |

**Important**: The SMS API region is different from the target ECS region. The agent registers with the SMS service in the SMS region, but the target ECS is created in the target region specified in the Terraform provider config.

## Download and Install

### Step 1: Download the agent

```bash
# On the source server, download the SMS Agent tarball
# The URL is region-specific — check HuaweiCloud SMS console for the correct URL
wget "https://sms-agent.ap-southeast-3.myhuaweicloud.com/SMS-Agent.tar.gz" -O SMS-Agent.tar.gz
tar xzf SMS-Agent.tar.gz
cd SMS-Agent
```

### Step 2: Run the installer (interactive)

The installer has 6 interactive prompts:

| # | Prompt | Response | Notes |
|---|--------|----------|-------|
| 1 | Warnings about system changes | `y` | Accept warnings |
| 2 | License agreement | `y` | Accept EULA |
| 3 | Access Key ID | `<AK>` | HuaweiCloud AK |
| 4 | Secret Access Key | `<SK>` | HuaweiCloud SK |
| 5 | SMS endpoint | `sms.ap-southeast-3.myhuaweicloud.com` | Region-specific |
| 6 | Enterprise project ID | `0` or specific ID | `0` = default |

### Step 3: Automate with pexpect

For non-interactive automation, use Python `pexpect`:

```python
#!/usr/bin/env python3
import pexpect
import sys

AK = "<access-key>"
SK = "<secret-key>"
ENDPOINT = "sms.ap-southeast-3.myhuaweicloud.com"

child = pexpect.spawn('sudo bash ./setup.sh', encoding='utf-8', timeout=300)
child.logfile_read = sys.stdout

prompts = [
    (r'\[y/N\].*warning', 'y\r\n'),           # 1. Warnings
    (r'\[y/N\].*agreement', 'y\r\n'),          # 2. License agreement
    (r'Access Key ID.*:', f'{AK}\r\n'),        # 3. AK
    (r'Secret Access Key.*:', f'{SK}\r\n'),    # 4. SK
    (r'endpoint.*:', f'{ENDPOINT}\r\n'),       # 5. Endpoint
    (r'project.*\[0\].*:', '\r\n'),            # 6. Enterprise project (default 0)
]

for pattern, response in prompts:
    child.expect(pattern, timeout=60)
    child.sendline(response)

child.expect(pexpect.EOF, timeout=300)
```

### Step 4: Verify installation

```bash
# Check agent process is running
ps aux | grep -v grep | grep -E 'linuxmain|SMS'

# Check agent logs
tail -f /var/log/sms/agent.log
```

## Verify Source Server Registration

From the HuaweiCloud side (not the source server):

```bash
# List all registered source servers
hcloud SMS ListServers --cli-region=<sms-region> --cli-output=json

# Find your server by IP or name
# Expected: state = "waiting", connected = true

# Show detailed info and pre-migration checks
hcloud SMS ShowServer --source_id=<source-id> --cli-region=<sms-region> --cli-output=json
```

### Pre-migration checks

The `ShowServer` response includes a `checks` array. All checks must have `result: "OK"`:

| Check | Description |
|-------|-------------|
| `OS_VERSION` | Source OS is supported |
| `DISK_USED_SIZE` | Disk usage is within limits |
| `CPU` | CPU architecture supported |
| `MEMORY` | Sufficient memory |
| `PARAVIRTUALIZATION` | Paravirtualization support |
| `FIRMWARE` | Firmware type detected (UEFI/BIOS) |
| `BOOT_LOADER` | Boot loader configuration |
| `RSYNC` | rsync available (file-level migration) |
| `RAW_DEVICES` | No raw device issues |
| `DISK_INFO` | Disk information valid |
| `PARTITION_STYLE` | Partition style supported (GPT/MBR) |
| `FILE_SYSTEM` | File system types supported |
| `DISK_PERFORMANCES` | Disk performance within limits |

If any check fails, resolve the issue on the source server before proceeding.

## Important Notes

- The agent runs as a daemon process (`linuxmain` on Linux)
- The agent communicates with the SMS service via HTTPS
- The source server must maintain internet connectivity to the SMS endpoint throughout the migration
- If the agent loses connection, the migration task will fail
- The agent can be uninstalled after migration: `sudo bash /usr/local/hostguard/Uninstall.sh` (path may vary)
- Agent version is reported in the `ShowServer` response (`agent_version` field)

## Troubleshooting Agent Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Agent not connecting | Firewall blocking HTTPS | Allow outbound 443 to SMS endpoint |
| `state: "error"` | Agent crash or network issue | Restart agent, check logs |
| Pre-migration check fails | OS/disk incompatibility | Check specific check name, resolve on source |
| fstab warning | LABEL= or UUID= references | Non-blocking, accept with `y` during install |

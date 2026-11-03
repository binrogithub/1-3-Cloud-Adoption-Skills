# huaweicloud-vpn-s2c-create

AI-assisted skill for creating IPsec site-to-cloud VPN tunnels in Huawei Cloud.

## Purpose

This skill creates an IPsec VPN tunnel between a remote peer (on-premises or another cloud) and a Huawei Cloud VPC, so the peer can reach resources inside the VPC through an encrypted tunnel. It is designed as a **runbook** — human-readable and agent-executable.

## Features

- **Interactive parameter gathering** — asks for all parameters, never assumes or reuses existing resources
- **Two peer modes**:
  - **Cloud peer** — creates an ECS with strongSwan in another Huawei Cloud region/VPC and initiates the tunnel automatically
  - **On-premises / local peer** — generates a strongSwan config file for the user to deploy on their own machine
- **Validation** — checks IKE/IPsec SA status and ping through the tunnel
- **Cleanup** — destroys all created resources in reverse order
- **Gotcha handling** — 12 critical rules discovered during real testing (lowercase dh_group, mandatory gateway_ip, NAT gateway for ECS, etc.)

## Installation

### OpenCode

```bash
cp -r huaweicloud-vpn-s2c-create ~/.opencode/skills/
```

### Hermes

```bash
cp -r huaweicloud-vpn-s2c-create ~/.hermes/skills/
```

### Claude Code

```bash
cp -r huaweicloud-vpn-s2c-create ~/.claude/skills/
```

## Usage

With an AI coding tool (OpenCode, Hermes, or Claude Code), simply ask:

```
Create an IPsec site-to-cloud VPN in Huawei Cloud using the huaweicloud-vpn-s2c-create skill.
Region: la-north-2. VPC: vpc-myvpn, CIDR 192.168.0.0/16.
Peer mode: on-prem local, peer IP 203.0.113.5, peer subnet 10.0.0.0/24.
PSK: MySecretPSK123!
```

The AI will read the skill runbook and execute the steps automatically.

## Requirements

- **KooCLI** (`hcloud`) installed and configured with AK/SK + region
- **hcloud MCP** server (optional, for discovery) or direct KooCLI access
- **SSH keypair** — generate one locally and register via `KPS CreateKeypair`
- **Python 3** or **jq** for JSON parsing

## Files

| File | Description |
|------|-------------|
| `SKILL.md` | Main runbook — step-by-step VPN creation workflow |
| `references/vpn-api-operations.md` | KooCLI VPN API reference (CreateVgw, CreateCgw, CreateVpnConnection, etc.) |
| `references/strongswan-config.md` | strongSwan configuration templates for the peer side |
| `references/troubleshooting.md` | Common issues and fixes |
| `scripts/cleanup.sh` | Resource cleanup script (deletes in reverse order) |

## Tested With

- **Model**: GLM-5.2 via Huawei Cloud MaaS
- **Region**: la-north-2
- **Result**: 1 prompt, all resources created correctly, all gotchas handled

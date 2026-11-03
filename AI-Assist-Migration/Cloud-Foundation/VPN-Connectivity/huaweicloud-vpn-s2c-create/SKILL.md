---
name: huaweicloud-vpn-s2c-create
description: Create an IPsec site-to-cloud VPN in Huawei Cloud (on-prem or another cloud → a Huawei VPC) interactively via KooCLI. Asks for all parameters, supports two peer modes (cloud ECS+strongSwan or on-prem local strongSwan config), validates SA+ping, and cleans up. Never assumes or reuses resources without confirming.
license: MIT
compatibility: opencode
metadata:
  audience: infrastructure-engineers
  workflow: vpn-s2c-create-huaweicloud
---

# Huawei Cloud IPsec Site-to-Cloud VPN — Creation Runbook

This is a **runbook**: follow the steps in order. Each step shows the exact CLI command to run. An agent can execute these automatically; a human can run them manually in a terminal.

**Goal**: Create an IPsec VPN tunnel between a remote peer (on-premises or another cloud) and a Huawei Cloud VPC, so the peer can reach resources inside the VPC (e.g. ECS instances) through an encrypted tunnel.

**Tool**: KooCLI (`hcloud` command). All commands are `hcloud <Service> <Operation> --param=value`. JSON output may have a warning prefix — strip with `s[s.find('{'):]` before parsing.

**Credentials**: AK/SK come from env vars (`HCLOUD_AK`, `HCLOUD_SK`) or KooCLI profile. Never hardcode them. The PSK is asked from the user and used only in the current session.

---

## Critical Rules (read these first)

These are gotchas discovered during real testing. Violating them causes failures:

1. **`dh_group` and `pfs` must be lowercase** — use `group14`, NOT `Group14`. The API rejects capitalized values.
2. **`CreateSubnet` requires `gateway_ip`** — the help says optional but it is mandatory. Always pass `--subnet.gateway_ip=<first-usable-ip>` (e.g. `192.168.2.1` for `192.168.2.0/24`).
3. **ECS needs a NAT gateway for internet** — a subnet without SNAT cannot resolve DNS or install packages. Create a NAT gateway + SNAT rule before relying on cloud-init `apt-get`.
4. **VPN connection status "DOWN" is normal** — without health-check, the cloud-side status stays DOWN even when the tunnel is fully UP. Validate with SA + ping, not with the status field.
5. **Always check flavor availability** — some regions (e.g. sa-brazil-1) have all small flavors abandoned or sold out. Query `ListFlavors` and filter `cond:operation:status != abandon` before choosing.
6. **Ubuntu images use `root` as SSH user** — not `ubuntu`. Use `root@<eip>` for SSH.
7. **strongSwan stroke plugin** — on Ubuntu 22.04, the `stroke` plugin is NOT loaded by default. You must explicitly add `stroke` to the charon `load` line in `/etc/strongswan.conf` (see `references/strongswan-config.md`).
8. **`ha_role` for active-active** — use `master` for the first connection (EIP1). For the second connection (EIP2), **omit** `ha_role` entirely (`slave` is rejected).
9. **Never hardcode credentials** — AK/SK from env vars or KooCLI profile. PSK asked from user.
10. **NEVER reuse existing resources** — if a resource with the same name already exists, use a different name (append a number like `-2` or a short timestamp). This prevents accidentally using infrastructure from other projects. The only exception is the keypair: if a keypair with the same name and same public key already exists, you may reuse it.
11. **Use a unique prefix for all resource names** — ask the user for a project prefix (e.g. `vpnlab`, `myvpn`) and use it for every resource: VPC, subnet, SG, ECS, NAT, EIP, VGW, CGW, connection. This avoids name collisions with other projects.
12. **If creation fails with "name already exists"** — do NOT silently reuse the existing resource. Instead, retry with a different name (append `-2`, `-3`, etc.) or ask the user for a different prefix.

---

## Prerequisites

- **KooCLI** (`hcloud`) installed and configured with AK/SK + region
- **hcloud MCP** server (optional, for discovery) or direct KooCLI access
- **SSH keypair** — generate one locally and register via `KPS CreateKeypair`, or use an existing one
- **Python 3** or **jq** for JSON parsing

---

## Step 1: Gather Parameters

Ask the user for each parameter. Don't assume defaults without confirming.

### 1a. Cloud side (where the VPN gateway lives)

| Parameter | What to ask | Example |
|-----------|-------------|---------|
| Region | "Which Huawei Cloud region for the VPN gateway?" | `la-north-2` |
| VPC mode | "Create a new VPC or use an existing one?" | new / existing |
| VPC name | "Name for the new VPC?" | `vpc-vpn-a` |
| VPC CIDR | "CIDR for the VPC?" | `192.168.0.0/16` |
| Subnet name | "Name for the subnet?" | `subnet-vpn-a` |
| Subnet CIDR | "CIDR for the subnet (within VPC CIDR)?" | `192.168.2.0/24` |
| AZ | "Availability zone?" | Run `NovaListAvailabilityZones` and offer choices |
| HA mode | "HA mode: active-active or active-standby?" | `active-active` (recommended) |
| Gateway flavor | "VPN gateway flavor?" | `Professional1` (active-active), `Basic` (active-standby) |
| EIP type | "EIP type for the gateway?" | `5_bgp` (BGP, recommended) |
| EIP bandwidth | "Bandwidth size (Mbit/s)?" | `5` |
| Local subnets | "Which local subnets reachable through the tunnel?" | `192.168.0.0/16` |

If the user chooses an existing VPC: list VPCs with `VPC ListVpcs`, let them pick, then list subnets with `VPC ListSubnets`.

### 1b. IKE/IPsec policy

Ask the user (offer defaults, allow override):

| Parameter | Default | Valid values |
|-----------|---------|-------------|
| IKE version | `v2` | `v1`, `v2` |
| IKE auth algorithm | `sha2-256` | `sha1`, `sha2-256`, `md5` |
| IKE encryption | `aes-128` | `aes-128`, `aes-256`, `3des` |
| IKE DH group | `group14` | **lowercase**: `group1`, `group2`, `group5`, `group14`, ... |
| IKE lifetime | `86400` | seconds |
| IPsec auth | `sha2-256` | same as IKE |
| IPsec encryption | `aes-128` | same as IKE |
| IPsec PFS | `group14` | **lowercase**: same as DH group |
| IPsec lifetime | `3600` | seconds |
| Encapsulation | `tunnel` | `tunnel`, `transport` |
| Transform protocol | `esp` | `esp`, `ah` |

### 1c. Tunnel addresses

Link-local /30 addresses for the tunnel endpoints:

| Parameter | Default | Notes |
|-----------|---------|-------|
| Tunnel local | `169.254.70.1/30` | VGW side |
| Tunnel peer | `169.254.70.2/30` | Customer side |

For a second connection (EIP2 in active-active), use a different /30 (e.g. `169.254.71.1/30` - `169.254.71.2/30`).

### 1d. PSK

Ask: "Enter the Pre-Shared Key (PSK) for the IPsec tunnel." Used only in the current session.

### 1e. Peer mode

Ask: "What is the peer side?"

- **Option A: Another Huawei Cloud region/VPC** — the skill creates an ECS with strongSwan in the peer region/VPC and initiates the tunnel automatically.
- **Option B: On-premises / local** — the skill generates a strongSwan config file for the user to deploy on their own machine.

---

## Step 2: Verify Flavor & Image Availability

Before creating anything, check the chosen region has usable resources:

```bash
# List non-abandoned flavors (1 vCPU, smallest RAM)
hcloud ECS ListFlavors --cli-region=<region> 2>/dev/null | \
  python3 -c "
import sys,json
s=sys.stdin.read(); d=json.loads(s[s.find('{'):])
fs=[]
for f in d.get('flavors',[]):
    es=f.get('os_extra_specs',{})
    st=es.get('cond:operation:status','')
    if st!='abandon' and f.get('vcpus')=='1':
        fs.append((int(f.get('ram','999999')), f['name']))
fs.sort()
for ram,n in fs[:6]: print(f'ram={ram} {n}')
if not fs: print('NO small flavors available!')
"

# List Ubuntu 22.04 images
hcloud IMS ListImages --cli-region=<region> --__imagetype=gold --__platform=Ubuntu --__support_kvm=true --architecture=x86 2>/dev/null | \
  python3 -c "
import sys,json
s=sys.stdin.read(); d=json.loads(s[s.find('{'):])
for i in d.get('images',[]):
    if '22.04' in i.get('name',''): print(i['name'][:50], i['id']); break
"
```

If no small flavors are available, warn the user and suggest `la-north-2` (which has `s6.small.1`).

---

## Step 3: Create Cloud-Side Resources

### 3a. VPC + Subnet + Security Group

```bash
# Create the VPC
hcloud VPC CreateVpc --cli-region=<region> --vpc.name=<name> --vpc.cidr=<cidr>

# Create the subnet — gateway_ip is MANDATORY despite help saying optional
hcloud VPC CreateSubnet --cli-region=<region> \
  --subnet.vpc_id=<vpc_id> --subnet.name=<name> --subnet.cidr=<cidr> \
  --subnet.gateway_ip=<first_ip> --subnet.availability_zone=<az>

# Create the security group
hcloud VPC CreateSecurityGroup --cli-region=<region> --security_group.name=<name>

# Allow ICMP from the peer subnet (so we can ping through the tunnel)
hcloud VPC CreateSecurityGroupRule --cli-region=<region> \
  --security_group_rule.security_group_id=<sg_id> \
  --security_group_rule.direction=ingress --security_group_rule.action=allow \
  --security_group_rule.protocol=icmp --security_group_rule.ethertype=IPv4 \
  --security_group_rule.remote_ip_prefix=<peer_cidr> --security_group_rule.priority=1

# Allow SSH from anywhere (for debugging)
hcloud VPC CreateSecurityGroupRule --cli-region=<region> \
  --security_group_rule.security_group_id=<sg_id> \
  --security_group_rule.direction=ingress --security_group_rule.action=allow \
  --security_group_rule.protocol=tcp --security_group_rule.multiport=22 \
  --security_group_rule.ethertype=IPv4 \
  --security_group_rule.remote_ip_prefix=0.0.0.0/0 --security_group_rule.priority=2
```

### 3b. Target ECS (optional, for ping validation)

```bash
# Create an ECS in the VPC to serve as a ping target
hcloud ECS CreatePostPaidServers --cli-region=<region> \
  --server.name=<name> --server.flavorRef=<flavor> --server.imageRef=<image> \
  --server.vpcid=<vpc_id> --server.nics.1.subnet_id=<subnet_id> \
  --server.security_groups.1.id=<sg_id> --server.availability_zone=<az> \
  --server.key_name=<keypair> --server.root_volume.volumetype=SSD \
  --server.root_volume.size=40 --server.extendparam.chargingMode=0

# Poll until ACTIVE (check every 10s)
hcloud ECS ShowServer --cli-region=<region> --server_id=<ecs_id>
# Extract private IP from: server.addresses.<vpc_name>[0].addr
```

### 3c. VPN Gateway

```bash
# Create the VPN gateway with two EIPs (active-active)
hcloud VPN CreateVgw --cli-region=<region> \
  --vpn_gateway.name=<name> --vpn_gateway.vpc_id=<vpc_id> \
  --vpn_gateway.connect_subnet=<subnet_id> \
  --vpn_gateway.local_subnets.1=<local_cidr> \
  --vpn_gateway.network_type=public --vpn_gateway.attachment_type=vpc \
  --vpn_gateway.ha_mode=<active-active|active-standby> \
  --vpn_gateway.flavor=<Professional1|Basic> --vpn_gateway.ip_version=ipv4 \
  --vpn_gateway.eip1.type=5_bgp --vpn_gateway.eip1.bandwidth_size=<bw> \
  --vpn_gateway.eip1.bandwidth_name=<bw_name> --vpn_gateway.eip1.charge_mode=bandwidth \
  --vpn_gateway.eip2.type=5_bgp --vpn_gateway.eip2.bandwidth_size=<bw> \
  --vpn_gateway.eip2.bandwidth_name=<bw_name2> --vpn_gateway.eip2.charge_mode=bandwidth

# Poll until ACTIVE (check every 10s)
hcloud VPN ShowVgw --cli-region=<region> --vgw_id=<vgw_id>
# Extract EIP1 and EIP2 addresses from: vpn_gateway.eip1.ip_address, vpn_gateway.eip2.ip_address
```

Note: For active-standby, only `eip1` is needed. For active-active, both `eip1` and `eip2` are required.

---

## Step 4: Create Peer-Side Resources

### Option A: Cloud Peer (another Huawei region/VPC)

1. Ask for peer region, VPC CIDR, subnet CIDR, AZ
2. Check flavor availability in peer region (Step 2)
3. Create VPC-B, subnet-B, SG-B (allow UDP 500/4500 from 0.0.0.0/0, TCP 22, ICMP)
4. Create EIP-B (public IP for the peer ECS)
5. Create NAT gateway + SNAT rule in VPC-B (so ECS-B can install strongSwan via apt-get)
6. Create ECS-B with cloud-init that installs strongSwan and configures the tunnel
7. SSH to ECS-B and fix DNS + stroke plugin if cloud-init didn't complete

The strongSwan config on ECS-B targets EIP1 of the VPN gateway:

```
conn huawei
    left=%defaultroute
    leftid=<EIP_B>           # This ECS's public EIP
    leftsubnet=<peer_cidr>   # e.g. 10.200.0.0/24
    right=<EIP1>             # VPN gateway EIP1
    rightid=<EIP1>
    rightsubnet=<local_cidr> # e.g. 192.168.0.0/16
    ike=aes128-sha2_256-modp2048
    esp=aes128-sha2_256-modp2048
    auto=start
```

See `references/strongswan-config.md` for the full config including the stroke plugin fix and DNS fix.

### Option B: On-Premises / Local Peer

1. Ask for the peer's public IP (or detect with `curl ifconfig.me`)
2. Ask for the peer's local subnet CIDR (e.g. `10.201.0.0/24`)
3. Generate a strongSwan config file for the user (see `references/strongswan-config.md`)
4. Print instructions for the user to install strongSwan and start the tunnel

---

## Step 5: Create Customer Gateway + VPN Connection

### 5a. Customer Gateway

```bash
# Register the peer's public IP as a customer gateway
hcloud VPN CreateCgw --cli-region=<region> \
  --customer_gateway.name=<name> \
  --customer_gateway.id_type=ip \
  --customer_gateway.id_value=<peer_public_ip>
```

### 5b. VPN Connection

```bash
# Create the VPN connection (first tunnel, using EIP1)
hcloud VPN CreateVpnConnection --cli-region=<region> \
  --vpn_connection.name=<name> \
  --vpn_connection.vgw_id=<vgw_id> \
  --vpn_connection.vgw_ip=<eip1_id> \
  --vpn_connection.cgw_id=<cgw_id> \
  --vpn_connection.style=static \
  --vpn_connection.peer_subnets.1=<peer_cidr> \
  --vpn_connection.psk="<PSK>" \
  --vpn_connection.tunnel_local_address=169.254.70.1/30 \
  --vpn_connection.tunnel_peer_address=169.254.70.2/30 \
  --vpn_connection.ikepolicy.ike_version=v2 \
  --vpn_connection.ikepolicy.authentication_algorithm=sha2-256 \
  --vpn_connection.ikepolicy.encryption_algorithm=aes-128 \
  --vpn_connection.ikepolicy.dh_group=group14 \
  --vpn_connection.ikepolicy.lifetime_seconds=86400 \
  --vpn_connection.ipsecpolicy.authentication_algorithm=sha2-256 \
  --vpn_connection.ipsecpolicy.encryption_algorithm=aes-128 \
  --vpn_connection.ipsecpolicy.pfs=group14 \
  --vpn_connection.ipsecpolicy.lifetime_seconds=3600 \
  --vpn_connection.ipsecpolicy.encapsulation_mode=tunnel \
  --vpn_connection.ipsecpolicy.transform_protocol=esp \
  --vpn_connection.ha_role=master
```

For a second connection (EIP2 in active-active): use `--vpn_connection.vgw_ip=<eip2_id>` and **omit** `--vpn_connection.ha_role` (do not use `slave` — it is rejected).

---

## Step 6: Validate the Tunnel

### 6a. Check SA on the peer side

```bash
# For cloud peer (SSH to ECS-B — remember: user is root, not ubuntu)
ssh -i <key> root@<eip_b> "ipsec statusall"

# For local peer (run on the peer machine)
ipsec statusall
```

Look for:
- `ESTABLISHED` — IKE SA is up
- `INSTALLED, TUNNEL` — ESP child SA is up
- `ESP in UDP` — NAT traversal is being used (behind NAT)

If the SA is not established, see `references/troubleshooting.md`.

### 6b. Ping through the tunnel

```bash
# From cloud peer (ECS-B)
ssh -i <key> root@<eip_b> "ping -c 5 <ecs_a_private_ip>"

# From local peer (add source IP first, then ping)
ip addr add <peer_ip>/32 dev lo
ip route add <vpc_cidr> via <default_gw> dev eth0
sysctl -w net.ipv4.conf.all.rp_filter=0
ping -I <peer_ip> -c 5 <ecs_a_private_ip>
```

First packet loss (20% on a 5-ping test) is normal during tunnel setup.

### 6c. Check cloud-side status

```bash
hcloud VPN ShowVpnConnection --cli-region=<region> --vpn_connection_id=<conn_id>
```

Status may show `DOWN` even when the tunnel is UP. This is normal without health-check. The SA + ping are the real validation.

---

## Step 7: Export Peer Configuration (optional)

Huawei can export the customer-side config for a specific device vendor:

```bash
hcloud VPN ExportVpnConnectionPeerConfiguration --cli-region=<region> \
  --vpn_connection_id=<conn_id> \
  --vendor=<vendor> --type=<series> --model=<model> --version=<version>
```

---

## Step 8: Cleanup (optional)

Ask: "Destroy all VPN resources created in this session?"

If yes, run `scripts/cleanup.sh`:

```bash
bash scripts/cleanup.sh --region=<region> --prefix=<name-prefix> --yes
```

This deletes in reverse order: VPN connections → customer gateways → VPN gateway (auto-deletes EIPs) → ECS → NAT gateway + SNAT rules → standalone EIPs → security groups → subnets → VPCs → keypairs.

OBS buckets are NOT deleted (free when empty).

---

## API Quick Reference

| Operation | Purpose |
|-----------|---------|
| `VPN CreateVgw` | Create VPN gateway |
| `VPN ShowVgw` | Show gateway details (status, EIPs) |
| `VPN ListVgws` / `VPN DeleteVgw` | List / delete gateways |
| `VPN CreateCgw` | Create customer gateway |
| `VPN ListCgws` / `VPN DeleteCgw` | List / delete customer gateways |
| `VPN CreateVpnConnection` | Create VPN connection |
| `VPN ShowVpnConnection` | Show connection status |
| `VPN ListVpnConnections` / `VPN DeleteVpnConnection` | List / delete connections |
| `VPN ExportVpnConnectionPeerConfiguration` | Export customer-side config |

Full parameter details: `references/vpn-api-operations.md`
strongSwan templates: `references/strongswan-config.md`
Common issues & fixes: `references/troubleshooting.md`

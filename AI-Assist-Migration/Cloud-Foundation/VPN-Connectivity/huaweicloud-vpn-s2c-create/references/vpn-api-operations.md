# KooCLI VPN API Operations Reference

All operations use the `VPN` service via KooCLI (`hcloud VPN <operation>`). JSON output may have a multi-version warning prefix — parse with `s[s.find('{'):]`.

## VPN Gateway (Vgw)

### CreateVgw

```
POST /v5/{project_id}/vpn-gateways
```

**Required parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `--cli-region` | string | Region |
| `--vpn_gateway.name` | string | Gateway name |
| `--vpn_gateway.vpc_id` | string | VPC ID where the gateway attaches |
| `--vpn_gateway.connect_subnet` | string | Subnet ID for the gateway connection |
| `--vpn_gateway.local_subnets.1` | string | Local CIDR(s) reachable through tunnel (e.g. `192.168.0.0/16`) |
| `--vpn_gateway.network_type` | string | `public` (default) or `private` |
| `--vpn_gateway.attachment_type` | string | `vpc` (default) or `er` (Enterprise Router) |
| `--vpn_gateway.ha_mode` | string | `active-active` or `active-standby` |
| `--vpn_gateway.flavor` | string | `Professional1` (active-active), `Basic` (active-standby) |
| `--vpn_gateway.ip_version` | string | `ipv4` (default) or `ipv6` |
| `--vpn_gateway.eip1.type` | string | EIP type: `5_bgp` (BGP), `5_sbgp` (static BGP) |
| `--vpn_gateway.eip1.bandwidth_size` | int | Bandwidth in Mbit/s (e.g. `5`) |
| `--vpn_gateway.eip1.bandwidth_name` | string | Bandwidth name |
| `--vpn_gateway.eip1.charge_mode` | string | `bandwidth` or `traffic` |

For active-active, also provide `eip2.*` with the same structure (different `bandwidth_name`).

**Response:** `vpn_gateway.id` — use for polling and connection creation.

### ShowVgw

```
GET /v5/{project_id}/vpn-gateways/{vgw_id}
```

| Parameter | Type |
|-----------|------|
| `--cli-region` | string |
| `--vgw_id` | string |

**Response fields:**
- `vpn_gateway.status` — `ACTIVE`, `PENDING_CREATE`, `PENDING_UPDATE`, `PENDING_DELETE`, `ERROR`
- `vpn_gateway.eip1.id` / `vpn_gateway.eip1.ip_address` — EIP1 ID and address
- `vpn_gateway.eip2.id` / `vpn_gateway.eip2.ip_address` — EIP2 ID and address (active-active only)
- `vpn_gateway.ha_mode` — HA mode
- `vpn_gateway.flavor` — Flavor

### ListVgws / DeleteVgw

```
hcloud VPN ListVgws --cli-region=<region>
hcloud VPN DeleteVgw --cli-region=<region> --vgw_id=<id>
```

`DeleteVgw` deletes the gateway and its EIPs automatically.

## Customer Gateway (Cgw)

### CreateCgw

```
POST /v5/{project_id}/customer-gateways
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `--cli-region` | string | Region |
| `--customer_gateway.name` | string | Gateway name |
| `--customer_gateway.id_type` | string | `ip` or `fqdn` |
| `--customer_gateway.id_value` | string | Peer public IP (for `ip`) or FQDN (for `fqdn`) |

**Optional:** `--customer_gateway.bgp_asn` (integer) for BGP.

**Response:** `customer_gateway.id`

### ListCgws / ShowCgw / DeleteCgw

```
hcloud VPN ListCgws --cli-region=<region>
hcloud VPN ShowCgw --cli-region=<region> --customer_gateway_id=<id>
hcloud VPN DeleteCgw --cli-region=<region> --customer_gateway_id=<id>
```

## VPN Connection

### CreateVpnConnection

```
POST /v5/{project_id}/vpn-connections
```

**Required parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `--cli-region` | string | Region |
| `--vpn_connection.name` | string | Connection name |
| `--vpn_connection.vgw_id` | string | VPN gateway ID |
| `--vpn_connection.vgw_ip` | string | **EIP ID** (not IP address) — use `eip1.id` or `eip2.id` from ShowVgw |
| `--vpn_connection.cgw_id` | string | Customer gateway ID |
| `--vpn_connection.style` | string | `static` (policy-based) or `bgp` (BGP route-based) |
| `--vpn_connection.peer_subnets.1` | string | Peer CIDR (e.g. `10.200.0.0/24`) |
| `--vpn_connection.psk` | string | Pre-Shared Key |
| `--vpn_connection.tunnel_local_address` | string | Local tunnel IP with mask (e.g. `169.254.70.1/30`) |
| `--vpn_connection.tunnel_peer_address` | string | Peer tunnel IP with mask (e.g. `169.254.70.2/30`) |

**IKE policy:**

| Parameter | Default | Valid values |
|-----------|---------|-------------|
| `--vpn_connection.ikepolicy.ike_version` | v2 | `v1`, `v2` |
| `--vpn_connection.ikepolicy.authentication_algorithm` | sha2-256 | `sha1`, `sha2-256`, `md5` |
| `--vpn_connection.ikepolicy.encryption_algorithm` | aes-128 | `aes-128`, `aes-256`, `3des`, `aes-192` |
| `--vpn_connection.ikepolicy.dh_group` | group14 | **lowercase**: `group1`, `group2`, `group5`, `group14`, `group15`, `group16`, `group19`, `group20`, `group21` |
| `--vpn_connection.ikepolicy.lifetime_seconds` | 86400 | seconds (3600-86400) |

**IPsec policy:**

| Parameter | Default | Valid values |
|-----------|---------|-------------|
| `--vpn_connection.ipsecpolicy.authentication_algorithm` | sha2-256 | same as IKE |
| `--vpn_connection.ipsecpolicy.encryption_algorithm` | aes-128 | same as IKE |
| `--vpn_connection.ipsecpolicy.pfs` | group14 | **lowercase**: same as DH group |
| `--vpn_connection.ipsecpolicy.lifetime_seconds` | 3600 | seconds (30-86400) |
| `--vpn_connection.ipsecpolicy.encapsulation_mode` | tunnel | `tunnel`, `transport` |
| `--vpn_connection.ipsecpolicy.transform_protocol` | esp | `esp`, `ah` |

**HA role (active-active only):**

| Parameter | Value | Notes |
|-----------|-------|-------|
| `--vpn_connection.ha_role` | `master` | For the first connection (EIP1) |
| (omit) | — | For the second connection (EIP2). **Do NOT use `slave`** — it is rejected with `VPN.0001 invalid request: connection haRole is invalid` |

**Response:** `vpn_connection.id`

### ShowVpnConnection

```
GET /v5/{project_id}/vpn-connections/{vpn_connection_id}
```

| Parameter | Type |
|-----------|------|
| `--cli-region` | string |
| `--vpn_connection_id` | string |

**Response fields:**
- `vpn_connection.status` — `DOWN` (normal without health-check), `UP`, `ERROR`
- `vpn_connection.vgw_ip` — EIP ID used
- `vpn_connection.style` — `STATIC` or `BGP`
- `vpn_connection.peer_subnets` — array of peer CIDRs

**IMPORTANT**: Status `DOWN` does NOT mean the tunnel is down. Without health-check enabled, the cloud cannot detect the peer status. Always validate with SA + ping on the peer side.

### ListVpnConnections / DeleteVpnConnection

```
hcloud VPN ListVpnConnections --cli-region=<region>
hcloud VPN DeleteVpnConnection --cli-region=<region> --vpn_connection_id=<id>
```

## Export Peer Configuration

```
POST /v5/{project_id}/vpn-connections/{vpn_connection_id}/export-peer-configuration
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `--cli-region` | string | Region |
| `--vpn_connection_id` | string | Connection ID |
| `--vendor` | string | Device vendor (e.g. `Cisco`, `Juniper`, `Huawei`) |
| `--type` | string | Device series |
| `--model` | string | Device model |
| `--version` | string | Device version |

Generates a configuration file for the customer-side device.

## Helper Operations

### Availability Zones

```bash
hcloud ECS NovaListAvailabilityZones --cli-region=<region>
# Response: availabilityZoneInfo[].zoneName
```

### Flavors (with status)

```bash
hcloud ECS ListFlavors --cli-region=<region>
# Filter: os_extra_specs.cond:operation:status != "abandon"
# Check: vcpus, ram, name
```

### Images

```bash
hcloud IMS ListImages --cli-region=<region> --__imagetype=gold --__platform=Ubuntu --__support_kvm=true --architecture=x86
# Filter: name contains "22.04" or "24.04"
```

### EIP

```bash
# Create
hcloud EIP CreatePublicip --cli-region=<region> --publicip.type=5_bgp \
  --bandwidth.name=<name> --bandwidth.size=5 \
  --bandwidth.charge_mode=bandwidth --bandwidth.share_type=PER

# List / Delete
hcloud EIP ListPublicips --cli-region=<region>
hcloud EIP DeletePublicip --cli-region=<region> --publicip_id=<id>
```

### NAT Gateway (for ECS internet access)

```bash
# Create NAT gateway
hcloud NAT CreateNatGateway --cli-region=<region> \
  --nat_gateway.name=<name> --nat_gateway.router_id=<vpc_id> \
  --nat_gateway.internal_network_id=<subnet_id> --nat_gateway.spec=1

# Create SNAT rule
hcloud NAT CreateNatGatewaySnatRule --cli-region=<region> \
  --snat_rule.nat_gateway_id=<nat_id> --snat_rule.network_id=<subnet_id> \
  --snat_rule.source_type=0 --snat_rule.floating_ip_id=<eip_id>

# Delete
hcloud NAT DeleteNatGatewaySnatRule --cli-region=<region> --snat_rule_id=<rule_id> --nat_gateway_id=<nat_id>
hcloud NAT DeleteNatGateway --cli-region=<region> --nat_gateway_id=<nat_id>
```

### Keypair

```bash
# Create (register public key)
hcloud KPS CreateKeypair --cli-region=<region> --keypair.name=<name> --keypair.public_key="<pubkey>"

# List
hcloud KPS ListKeypairs --cli-region=<region>
```

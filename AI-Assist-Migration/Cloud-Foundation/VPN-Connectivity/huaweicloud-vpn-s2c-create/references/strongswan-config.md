# strongSwan Configuration Templates

This reference covers strongSwan configuration for both peer modes: cloud ECS peer and on-premises/local peer behind NAT.

## Common Issues on Ubuntu 22.04

### 1. Stroke Plugin Not Loaded

By default, Ubuntu 22.04's strongSwan does NOT load the `stroke` plugin, which is required for `ipsec statusall` to work. The `stroke` .so exists at `/usr/lib/ipsec/plugins/libstrongswan-stroke.so` but no config file enables it.

**Fix:** Explicitly add `stroke` to the charon `load` line in `/etc/strongswan.conf`:

```
charon {
    load = aesni aes rc2 sha2 sha1 md5 mgf1 random nonce x509 revocation constraints pubkey pkcs1 pkcs7 pkcs8 pkcs12 pgp dnskey sshkey pem openssl fips-prf gmp agent xcbc hmac gcm drbg attr kernel-netlink resolve socket-default connmark updown eap-mschapv2 xauth-generic counters stroke
    plugins {
        include strongswan.d/charon/*.conf
    }
}
include strongswan.d/*.conf
```

After editing, restart: `systemctl restart strongswan-starter` (or `ipsec restart`).

**Symptom without fix:** `ipsec statusall` returns `connecting to 'unix:///var/run/charon.ctl' failed: No such file or directory`.

### 2. DNS Not Resolving

On Huawei Cloud Ubuntu ECS, `systemd-resolved` may not have upstream DNS servers configured, causing `Temporary failure resolving 'repo.huaweicloud.com'`.

**Fix:**

```bash
systemctl stop systemd-resolved
rm -f /etc/resolv.conf
cat > /etc/resolv.conf <<EOF
nameserver 8.8.8.8
nameserver 8.8.4.4
EOF
```

### 3. No Internet Access (NAT Gateway Required)

ECS instances in a subnet without a NAT gateway cannot reach the internet. This blocks `apt-get install strongswan` and DNS resolution.

**Fix:** Create a NAT gateway + SNAT rule (see `vpn-api-operations.md` → NAT Gateway).

## Template A: Cloud Peer (ECS in another Huawei VPC)

This template is for an ECS instance with a public EIP in a separate VPC. The ECS initiates the tunnel to the VPN gateway.

### ipsec.conf

```
config setup
    uniqueids=no

conn %default
    authby=secret
    keyexchange=ikev2
    type=tunnel

conn huawei
    left=%defaultroute
    leftid=<EIP_PEER>           # This ECS's public EIP
    leftsubnet=<PEER_CIDR>      # e.g. 10.200.0.0/24
    right=<EIP_VGW>             # VPN gateway EIP1
    rightid=<EIP_VGW>           # Same as right
    rightsubnet=<LOCAL_CIDR>    # e.g. 192.168.0.0/16
    ike=aes128-sha2_256-modp2048
    esp=aes128-sha2_256-modp2048
    ikelifetime=86400s
    lifetime=3600s
    auto=start
```

### ipsec.secrets

```
<EIP_PEER> <EIP_VGW> : PSK "<PSK>"
```

### Cloud-init script (for ECS creation)

```bash
#!/bin/bash
set -x
# Fix DNS
systemctl stop systemd-resolved 2>/dev/null || true
rm -f /etc/resolv.conf
echo "nameserver 8.8.8.8" > /etc/resolv.conf
echo "nameserver 8.8.4.4" >> /etc/resolv.conf
# Install strongSwan
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y strongswan
# Write config
cat > /etc/ipsec.conf <<'IPSEC'
config setup
    uniqueids=no
conn %default
    authby=secret
    keyexchange=ikev2
    type=tunnel
conn huawei
    left=%defaultroute
    leftid=<EIP_PEER>
    leftsubnet=<PEER_CIDR>
    right=<EIP_VGW>
    rightid=<EIP_VGW>
    rightsubnet=<LOCAL_CIDR>
    ike=aes128-sha2_256-modp2048
    esp=aes128-sha2_256-modp2048
    ikelifetime=86400s
    lifetime=3600s
    auto=start
IPSEC
cat > /etc/ipsec.secrets <<'SEC'
<EIP_PEER> <EIP_VGW> : PSK "<PSK>"
SEC
chmod 600 /etc/ipsec.secrets
# Fix stroke plugin
cat > /etc/strongswan.conf <<'CONF'
charon {
    load = aesni aes rc2 sha2 sha1 md5 mgf1 random nonce x509 revocation constraints pubkey pkcs1 pkcs7 pkcs8 pkcs12 pgp dnskey sshkey pem openssl fips-prf gmp agent xcbc hmac gcm drbg attr kernel-netlink resolve socket-default connmark updown eap-mschapv2 xauth-generic counters stroke
    plugins {
        include strongswan.d/charon/*.conf
    }
}
include strongswan.d/*.conf
CONF
# Start
systemctl enable strongswan-starter
systemctl restart strongswan-starter
sleep 8
ipsec up huawei || true
```

**Note:** Cloud-init may run before the NAT gateway is ready. If `apt-get` fails, SSH in after the ECS is ACTIVE and run the install manually.

## Template B: On-Premises / Local Peer (behind NAT)

This template is for a machine behind NAT (e.g. a local server, a Docker container on a laptop). NAT traversal (NAT-T, UDP 4500) is used automatically.

### ipsec.conf

```
config setup
    uniqueids=no

conn %default
    authby=secret
    keyexchange=ikev2
    type=tunnel

conn huawei
    left=%defaultroute
    leftid=<PUBLIC_IP>          # Your public IP (as seen by the internet)
    leftsubnet=<PEER_CIDR>      # e.g. 10.201.0.0/24
    right=<EIP_VGW>             # VPN gateway EIP (EIP1 or EIP2)
    rightid=<EIP_VGW>           # Same as right
    rightsubnet=<LOCAL_CIDR>    # e.g. 192.168.0.0/16
    ike=aes128-sha2_256-modp2048
    esp=aes128-sha2_256-modp2048
    ikelifetime=86400s
    lifetime=3600s
    auto=start
```

### ipsec.secrets

```
<PUBLIC_IP> <EIP_VGW> : PSK "<PSK>"
```

### Setup instructions for the user

```bash
# 1. Install strongSwan
sudo apt-get update && sudo apt-get install -y strongswan

# 2. Write config files (see above)
sudo tee /etc/ipsec.conf <<'EOF'
<ipsec.conf content>
EOF
sudo tee /etc/ipsec.secrets <<'EOF'
<ipsec.secrets content>
EOF
sudo chmod 600 /etc/ipsec.secrets

# 3. Fix stroke plugin
sudo tee /etc/strongswan.conf <<'EOF'
charon {
    load = aesni aes rc2 sha2 sha1 md5 mgf1 random nonce x509 revocation constraints pubkey pkcs1 pkcs7 pkcs8 pkcs12 pgp dnskey sshkey pem openssl fips-prf gmp agent xcbc hmac gcm drbg attr kernel-netlink resolve socket-default connmark updown eap-mschapv2 xauth-generic counters stroke
    plugins {
        include strongswan.d/charon/*.conf
    }
}
include strongswan.d/*.conf
EOF

# 4. Start the tunnel
sudo systemctl restart strongswan-starter
sleep 5
sudo ipsec statusall

# 5. (Optional) Ping through the tunnel
# Add a source IP in your peer subnet:
sudo ip addr add <PEER_IP>/32 dev lo
# Route the VPC CIDR via your default gateway:
sudo ip route add <LOCAL_CIDR> via <DEFAULT_GW> dev eth0
# Disable reverse path filtering:
sudo sysctl -w net.ipv4.conf.all.rp_filter=0
# Ping:
ping -I <PEER_IP> -c 5 <TARGET_IP>
```

### Finding your public IP

```bash
curl -s ifconfig.me
# or
curl -s https://api.ipify.org
```

## Algorithm Mapping

The strongSwan `ike=` / `esp=` syntax maps to the Huawei API as follows:

| strongSwan | Huawei API |
|------------|-----------|
| `aes128` | `encryption_algorithm=aes-128` |
| `aes256` | `encryption_algorithm=aes-256` |
| `sha2_256` | `authentication_algorithm=sha2-256` |
| `sha1` | `authentication_algorithm=sha1` |
| `modp2048` | `dh_group=group14` / `pfs=group14` |
| `modp1024` | `dh_group=group2` / `pfs=group2` |
| `modp1536` | `dh_group=group5` / `pfs=group5` |

**DH group mapping:**

| modp | group |
|------|-------|
| modp768 | group1 |
| modp1024 | group2 |
| modp1536 | group5 |
| modp2048 | group14 |
| modp3072 | group15 |
| modp4096 | group16 |
| modp256 | group19 (ECP256) |
| modp384 | group20 (ECP384) |
| modp521 | group21 (ECP521) |

## Verifying the SA

```bash
# Full status
ipsec statusall

# Look for:
#   ESTABLISHED  — IKE SA is up
#   INSTALLED, TUNNEL — ESP child SA is up
#   ESP in UDP — NAT traversal is being used

# Kernel XFRM state (SA)
ip xfrm state

# Kernel XFRM policy
ip xfrm policy
```

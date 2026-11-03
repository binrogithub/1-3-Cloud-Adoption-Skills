# Troubleshooting Guide

## Problem: `dh_group` / `pfs` rejected

**Error:** `VPN.0001 invalid request` or similar validation error when creating the VPN connection.

**Cause:** The `dh_group` and `pfs` values must be **lowercase** (e.g. `group14`, not `Group14`).

**Fix:** Use lowercase:
```
--vpn_connection.ikepolicy.dh_group=group14
--vpn_connection.ipsecpolicy.pfs=group14
```

---

## Problem: `CreateSubnet` fails with "gateway_ip required"

**Error:** `[USE_ERROR]The following parameters are required: subnet.gateway_ip`

**Cause:** The API help says `gateway_ip` is optional, but it is actually mandatory.

**Fix:** Always pass `--subnet.gateway_ip=<first-usable-ip>`. For CIDR `192.168.2.0/24`, use `192.168.2.1`.

---

## Problem: `ha_role=slave` rejected

**Error:** `VPN.0001 invalid request: connection haRole is invalid`

**Cause:** In active-active mode, `slave` is not a valid `ha_role`. Only `master` is accepted for the first connection. For the second connection (EIP2), `ha_role` must be omitted entirely.

**Fix:**
- First connection (EIP1): `--vpn_connection.ha_role=master`
- Second connection (EIP2): **omit** `--vpn_connection.ha_role`

---

## Problem: No usable ECS flavors in region

**Symptom:** All small flavors (s6.small.1, t6.small.1) have `cond:operation:status=abandon`, and large flavors are sold out.

**Cause:** Some regions (e.g. sa-brazil-1, la-south-2, ap-southeast-1) have limited flavor availability for certain accounts.

**Fix:**
1. Check flavor availability before choosing a region:
   ```bash
   hcloud ECS ListFlavors --cli-region=<region> | \
     python3 -c "import sys,json; s=sys.stdin.read(); d=json.loads(s[s.find('{'):]); [print(f['name']) for f in d['flavors'] if f.get('os_extra_specs',{}).get('cond:operation:status')!='abandon' and f.get('vcpus')=='1']"
   ```
2. If no small flavors: use `la-north-2` (has `s6.small.1` available), or use a larger flavor if budget allows.

---

## Problem: SSH to ECS times out

**Symptom:** `ssh root@<eip>` hangs or times out.

**Causes & Fixes:**

1. **Cloud-init still running** — wait 60-120s after ECS becomes ACTIVE, then retry.
2. **Security group missing port 22** — add an ingress rule:
   ```bash
   hcloud VPC CreateSecurityGroupRule --cli-region=<region> \
     --security_group_rule.security_group_id=<sg_id> \
     --security_group_rule.direction=ingress --security_group_rule.action=allow \
     --security_group_rule.protocol=tcp --security_group_rule.multiport=22 \
     --security_group_rule.ethertype=IPv4 \
     --security_group_rule.remote_ip_prefix=0.0.0.0/0 --security_group_rule.priority=22
   ```
3. **EIP not bound** — verify the EIP is associated with the ECS NIC.
4. **Wrong SSH user** — Ubuntu images on Huawei Cloud use `root`, not `ubuntu`.

---

## Problem: `ipsec statusall` fails with "No such file or directory"

**Error:** `connecting to 'unix:///var/run/charon.ctl' failed: No such file or directory`

**Cause:** The `stroke` plugin is not loaded by charon. On Ubuntu 22.04, strongSwan's modular loading does not include `stroke` by default.

**Fix:** Explicitly add `stroke` to the charon `load` line in `/etc/strongswan.conf`:

```
charon {
    load = ... counters stroke
    ...
}
```

Then restart: `systemctl restart strongswan-starter`

See `strongswan-config.md` for the full config.

---

## Problem: DNS not resolving on ECS

**Error:** `Temporary failure resolving 'repo.huaweicloud.com'`

**Cause:** `systemd-resolved` has no upstream DNS servers, or the subnet has no route to the internet.

**Fix:**

1. **Check internet access:** `ping -c 3 8.8.8.8` (IP, no DNS)
2. **If ping works but DNS fails:** Fix resolv.conf:
   ```bash
   systemctl stop systemd-resolved
   rm -f /etc/resolv.conf
   echo "nameserver 8.8.8.8" > /etc/resolv.conf
   echo "nameserver 8.8.4.4" >> /etc/resolv.conf
   ```
3. **If ping also fails:** Create a NAT gateway + SNAT rule for the subnet (see `vpn-api-operations.md`).

---

## Problem: SA not established

**Symptom:** `ipsec statusall` shows no `ESTABLISHED` SA, or only `connecting`.

**Debug steps:**

1. **Check UDP 500/4500 reachability:**
   ```bash
   # On the peer, can we reach the VGW EIP?
   nc -zuv <EIP_VGW> 500
   nc -zuv <EIP_VGW> 4500
   ```

2. **Check security group rules:** The peer-side SG must allow UDP 500 and 4500 from `0.0.0.0/0` (or the VGW EIP).

3. **Check PSK match:** Both sides must have the same PSK. Verify `ipsec.secrets` on the peer matches the `--vpn_connection.psk` used in `CreateVpnConnection`.

4. **Check IKE/IPsec policy match:** Both sides must use the same algorithms. Compare:
   - IKE version (v1 vs v2)
   - Authentication algorithm (sha2-256)
   - Encryption algorithm (aes-128)
   - DH group (group14 / modp2048)
   - Lifetime

5. **Check charon logs:**
   ```bash
   grep -iE "charon|ike|error|fail" /var/log/syslog | tail -30
   ```

6. **Force re-initiate:**
   ```bash
   ipsec up huawei
   ```

---

## Problem: SA established but ping fails

**Symptom:** `ipsec statusall` shows `ESTABLISHED` + `INSTALLED`, but `ping <target>` gets 100% packet loss.

**Causes & Fixes:**

1. **Security group on target ECS doesn't allow ICMP from peer CIDR:**
   ```bash
   hcloud VPC CreateSecurityGroupRule --cli-region=<region> \
     --security_group_rule.security_group_id=<target_sg_id> \
     --security_group_rule.direction=ingress --security_group_rule.action=allow \
     --security_group_rule.protocol=icmp --security_group_rule.ethertype=IPv4 \
     --security_group_rule.remote_ip_prefix=<peer_cidr> --security_group_rule.priority=1
   ```

2. **Wrong routing on local peer (behind NAT):**
   - The source IP must be in the peer subnet (e.g. `10.201.0.1`)
   - The route to the VPC CIDR must go via the **default gateway** (not `lo`)
   - Disable reverse path filtering: `sysctl -w net.ipv4.conf.all.rp_filter=0`

   ```bash
   ip addr add 10.201.0.1/32 dev lo
   ip route add 192.168.0.0/16 via <default_gw> dev eth0
   sysctl -w net.ipv4.conf.all.rp_filter=0
   ping -I 10.201.0.1 -c 5 <target_ip>
   ```

3. **First packet loss is normal:** The first ping packet may be lost while the tunnel route is being installed. 20% loss on a 5-ping test is acceptable.

---

## Problem: VPN connection status shows "DOWN"

**Symptom:** `ShowVpnConnection` returns `status=DOWN` even though the SA is established and ping works.

**Cause:** This is **normal** behavior. Without health-check/NQA enabled, the cloud side cannot detect the peer status. The connection status stays `DOWN`.

**Fix:** This is not an error. Validate the tunnel using SA + ping on the peer side. If you want the cloud to show `UP`, enable health check:
```bash
hcloud VPN UpdateVpnConnection --cli-region=<region> \
  --vpn_connection_id=<id> --vpn_connection.enable_health_check=true
```

---

## Problem: KooCLI JSON parsing fails

**Symptom:** `json.loads()` fails with `Extra data` or `Expecting value`.

**Cause:** KooCLI outputs a multi-version warning line before the JSON for some APIs:
```
ListVpcs is a multi-version API, where the version (v3) is default...
{
  "vpcs": [...]
}
```

**Fix:** Strip everything before the first `{`:
```python
import json
s = raw_output
d = json.loads(s[s.find('{'):])
```

---

## Problem: Cloud-init fails to install strongSwan

**Symptom:** ECS is ACTIVE but `ipsec` command not found.

**Cause:** Cloud-init ran before the NAT gateway was ready, or DNS wasn't configured.

**Fix:** SSH in after the ECS is ACTIVE and install manually:
```bash
ssh root@<eip> "
echo 'nameserver 8.8.8.8' > /etc/resolv.conf
apt-get update && apt-get install -y strongswan
# Then write ipsec.conf, ipsec.secrets, strongswan.conf
# See strongswan-config.md
"
```

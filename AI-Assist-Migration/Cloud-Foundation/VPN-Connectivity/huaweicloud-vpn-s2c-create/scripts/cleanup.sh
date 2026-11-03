#!/usr/bin/env bash
# Cleanup script for huaweicloud-vpn-s2c-create
# Destroys all VPN resources created in a session, in reverse creation order.
#
# Usage:
#   bash cleanup.sh                          # interactive: asks for region + name prefix
#   bash cleanup.sh --region=la-north-2 --prefix=vpnlab --yes   # non-interactive
#
# Resources deleted (in order):
#   1. VPN connections
#   2. Customer gateways
#   3. VPN gateway (auto-deletes its EIPs)
#   4. ECS instances (matching prefix)
#   5. NAT gateway + SNAT rules
#   6. Standalone EIPs (matching prefix)
#   7. Security groups (matching prefix)
#   8. Subnets (matching prefix)
#   9. VPCs (matching prefix)
#
# OBS buckets are NOT deleted (free when empty).
set -euo pipefail

REGION=""
PREFIX=""
YES=false

for arg in "$@"; do
  case "$arg" in
    --region=*) REGION="${arg#*=}" ;;
    --prefix=*) PREFIX="${arg#*=}" ;;
    --yes) YES=true ;;
  esac
done

if [ -z "$REGION" ]; then
  read -rp "Region to clean up [la-north-2]: " REGION
  REGION=${REGION:-la-north-2}
fi
if [ -z "$PREFIX" ]; then
  read -rp "Resource name prefix to match [vpnlab]: " PREFIX
  PREFIX=${PREFIX:-vpnlab}
fi
if [ "$YES" = false ]; then
  echo "This will delete ALL resources with '$PREFIX' in their name in region $REGION."
  read -rp "Are you sure? [y/N] " confirm
  [ "$confirm" = "y" ] || [ "$confirm" = "Y" ] || { echo "Aborted."; exit 0; }
fi

# JSON helper: parse hcloud output (strip multi-version warning)
parse_stdin() { python3 -c "import sys,json; s=sys.stdin.read(); i=s.find('{'); d=json.loads(s[i:]); $1" 2>/dev/null; }

echo "===== Cleanup in $REGION (prefix: $PREFIX) ====="

echo "--- [1] VPN connections ---"
hcloud VPN ListVpnConnections --cli-region="$REGION" 2>/dev/null | \
  parse_stdin "print('\n'.join(c['id'] for c in d.get('vpn_connections',[]) if '$PREFIX' in c.get('name','')))" | \
  while read -r id; do
    [ -z "$id" ] && continue
    echo "  deleting connection $id"
    hcloud VPN DeleteVpnConnection --cli-region="$REGION" --vpn_connection_id="$id" 2>&1 | head -1
  done

echo "--- [2] Customer gateways ---"
hcloud VPN ListCgws --cli-region="$REGION" 2>/dev/null | \
  parse_stdin "print('\n'.join(c['id'] for c in d.get('customer_gateways',[]) if '$PREFIX' in c.get('name','')))" | \
  while read -r id; do
    [ -z "$id" ] && continue
    echo "  deleting customer gateway $id"
    hcloud VPN DeleteCgw --cli-region="$REGION" --customer_gateway_id="$id" 2>&1 | head -1
  done

echo "--- [3] VPN gateways (auto-deletes EIPs) ---"
hcloud VPN ListVgws --cli-region="$REGION" 2>/dev/null | \
  parse_stdin "print('\n'.join(v['id'] for v in d.get('vpn_gateways',[]) if '$PREFIX' in v.get('name','')))" | \
  while read -r id; do
    [ -z "$id" ] && continue
    echo "  deleting VPN gateway $id"
    hcloud VPN DeleteVgw --cli-region="$REGION" --vgw_id="$id" 2>&1 | head -1
    sleep 5  # gateway deletion is async
  done

echo "--- [4] ECS instances ---"
hcloud ECS ListServersDetails --cli-region="$REGION" 2>/dev/null | \
  parse_stdin "print('\n'.join(s['id'] for s in d.get('servers',[]) if '$PREFIX' in s.get('name','')))" | \
  while read -r id; do
    [ -z "$id" ] && continue
    echo "  deleting ECS $id"
    hcloud ECS DeleteServers --cli-region="$REGION" --servers.1.id="$id" --delete_publicip=true --delete_volume=true 2>&1 | head -1
  done
sleep 15  # ECS deletion is async

echo "--- [5] NAT gateways ---"
hcloud NAT ListNatGateways --cli-region="$REGION" 2>/dev/null | \
  parse_stdin "print('\n'.join(n['id'] for n in d.get('nat_gateways',[]) if '$PREFIX' in n.get('name','')))" | \
  while read -r id; do
    [ -z "$id" ] && continue
    echo "  deleting NAT gateway $id"
    # delete SNAT rules first (ListNatGatewaySnatRules lists ALL rules in project; filter by nat_gateway_id)
    hcloud NAT ListNatGatewaySnatRules --cli-region="$REGION" 2>/dev/null | \
      parse_stdin "print('\n'.join(r['id'] for r in d.get('snat_rules',[]) if r.get('nat_gateway_id')=='$id'))" | \
      while read -r rule_id; do
        [ -z "$rule_id" ] && continue
        echo "    deleting SNAT rule $rule_id"
        hcloud NAT DeleteNatGatewaySnatRule --cli-region="$REGION" --nat_gateway_id="$id" --snat_rule_id="$rule_id" 2>&1 | head -1
      done
    sleep 8
    hcloud NAT DeleteNatGateway --cli-region="$REGION" --nat_gateway_id="$id" 2>&1 | head -1
    sleep 10
  done

echo "--- [6] Standalone EIPs (matching prefix in bandwidth name) ---"
hcloud EIP ListPublicips --cli-region="$REGION" 2>/dev/null | \
  parse_stdin "print('\n'.join(p['id'] for p in d.get('publicips',[]) if '$PREFIX' in str(p.get('bandwidth',{}).get('name',''))))" | \
  while read -r id; do
    [ -z "$id" ] && continue
    echo "  deleting EIP $id"
    hcloud EIP DeletePublicip --cli-region="$REGION" --publicip_id="$id" 2>&1 | head -1
  done

echo "--- [7] Security groups ---"
hcloud VPC ListSecurityGroups --cli-region="$REGION" 2>/dev/null | \
  parse_stdin "print('\n'.join(s['id'] for s in d.get('security_groups',[]) if '$PREFIX' in s.get('name','')))" | \
  while read -r id; do
    [ -z "$id" ] && continue
    echo "  deleting security group $id"
    hcloud VPC DeleteSecurityGroup --cli-region="$REGION" --security_group_id="$id" 2>&1 | head -1
  done

echo "--- [8] Subnets ---"
hcloud VPC ListSubnets --cli-region="$REGION" 2>/dev/null | \
  parse_stdin "print('\n'.join(s['id']+' '+s.get('vpc_id','') for s in d.get('subnets',[]) if '$PREFIX' in s.get('name','')))" | \
  while read -r id vpc_id; do
    [ -z "$id" ] && continue
    echo "  deleting subnet $id"
    hcloud VPC DeleteSubnet --cli-region="$REGION" --vpc_id="$vpc_id" --subnet_id="$id" 2>&1 | head -1
  done

echo "--- [9] VPCs ---"
hcloud VPC ListVpcs --cli-region="$REGION" 2>/dev/null | \
  parse_stdin "print('\n'.join(v['id'] for v in d.get('vpcs',[]) if '$PREFIX' in v.get('name','')))" | \
  while read -r id; do
    [ -z "$id" ] && continue
    echo "  deleting VPC $id"
    hcloud VPC DeleteVpc --cli-region="$REGION" --vpc_id="$id" 2>&1 | head -1
  done

echo "--- [10] Keypairs ---"
hcloud KPS ListKeypairs --cli-region="$REGION" 2>/dev/null | \
  parse_stdin "print('\n'.join(k.get('name','') for k in d.get('keypairs',[]) if '$PREFIX' in k.get('name','')))" | \
  while read -r name; do
    [ -z "$name" ] && continue
    echo "  deleting keypair $name"
    hcloud KPS DeleteKeypair --cli-region="$REGION" --keypair_name="$name" 2>&1 | head -1
  done

echo "===== Cleanup done ====="
echo "Note: OBS buckets are NOT deleted (free when empty)."
echo "Note: Some deletions are async — wait 30-60s and re-run if resources remain."

# Future VPN Terraform - Placeholder
# This directory contains placeholder Terraform for inter-region VPN connectivity.
# Do NOT apply these resources in the experimental phase.
# Deploy only when switching from Internet to VPN for presentation.

# ============================================================
# VPN Architecture (Placeholder)
# ============================================================
#
# Source Region: cn-north-4 (or your source region)
# Target Region: la-south-2 (Santiago)
#
# Resources needed:
# - VPN Gateway in source VPC
# - VPN Gateway in target VPC
# - VPN Connection (IKEv2, IPsec)
# - Route table updates in both VPCs
# - Security group updates (replace public CIDR with VPN CIDR)
# - pg_hba.conf updates on source ECS PostgreSQL
#
# Source CIDR: 192.168.0.0/24 (source subnet)
# Target CIDR: 10.0.0.0/24 (target subnet)
#
# ============================================================
# Pre-requisites
# ============================================================
# - Source VPC and Subnet must exist
# - Target VPC and Subnet must exist
# - Both VPN Gateways must be created before the VPN Connection
# - PSK must be generated securely and shared between gateways
#
# ============================================================
# Security Group Updates After VPN
# ============================================================
#
# Source Security Group:
#   REMOVE: Ingress TCP 5432 from DRS public CIDR
#   ADD:    Ingress TCP 5432 from 10.0.0.0/24 (target subnet via VPN)
#
# Target Security Group:
#   REMOVE: Ingress TCP 5432 from DRS public CIDR
#   ADD:    Ingress TCP 5432 from 192.168.0.0/24 (source subnet via VPN)
#
# ============================================================
# pg_hba.conf Updates After VPN
# ============================================================
#
# On source ECS PostgreSQL:
#   REMOVE: host demomigration drs_replicator <DRS_PUBLIC_CIDR> md5
#   REMOVE: host replication   drs_replicator <DRS_PUBLIC_CIDR> md5
#   ADD:    host demomigration drs_replicator 10.0.0.0/24 md5
#   ADD:    host replication   drs_replicator 10.0.0.0/24 md5
#
# ============================================================
# Public Access Removal Checklist
# ============================================================
#
# [ ] Remove ECS EIP (or restrict to SSH-only)
# [ ] Remove source SG rule: TCP 5432 from DRS public CIDR
# [ ] Remove target SG rule: TCP 5432 from DRS public CIDR
# [ ] Remove pg_hba.conf entries with public CIDR
# [ ] Reload PostgreSQL on source ECS
# [ ] Switch DRS task network mode from Public to VPC/Private
# [ ] Verify DRS connectivity over VPN
# [ ] Verify no public PostgreSQL access exists
# [ ] Run full validation over VPN path

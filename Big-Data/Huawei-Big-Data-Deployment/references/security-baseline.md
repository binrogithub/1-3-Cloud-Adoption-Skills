# Security Baseline

Security model: workshop/simple.

This model is intentionally simple, but it should still avoid unsafe defaults.

## Defaults

- Public access: disabled
- Bastion: enabled
- NAT Gateway: disabled
- DWS: private-only
- MRS: private access through VPC/bastion
- SSH: restricted by `allowed_ssh_cidr`
- Credentials: never committed to GitHub

## Security group rules

Recommended:

- Allow SSH only from `allowed_ssh_cidr` to bastion
- Allow internal subnet traffic between big data services
- Avoid exposing MRS Manager, DWS, or database ports publicly

## IAM

Use an IAM agency for MRS/DLI/OBS interactions.

## KMS

Use KMS in full-platform pattern or when user asks for encryption.

## GitHub safety

Do not commit:

- `.tfvars` with real values
- private keys
- cloud credentials
- generated state files
- `.terraform/`

Commit only:

- `.tfvars.example`
- modules
- README files
- scripts

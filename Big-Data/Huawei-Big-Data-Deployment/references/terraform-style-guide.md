# Terraform Style Guide

## Structure

Prefer reusable modules:

```text
modules/
  vpc/
  security/
  obs/
  iam-agency/
  bastion/
  mrs/
  dws/
  dli/
  cdm/
  kms/
environments/
  dev/
  test/
  prod/
  demo/
  workshop/
```

## Naming

Use:

```text
{project}-{env}-{service}-{region}
```

Example:

```text
health-demo-workshop-mrs-la-north-2
```

## Variables

Use variables for:

- project
- env
- region
- availability zone
- VPC CIDR
- subnet CIDR
- allowed SSH CIDR
- node flavors
- disk type
- disk size
- cluster sizes

## Comments

Use TODO comments when a provider argument must be validated:

```hcl
# TODO: Verify exact argument name and supported values for current provider version and target region.
```

## Credentials

Never hardcode:

- access_key
- secret_key
- passwords
- private keys

Use environment variables or secure secret management.

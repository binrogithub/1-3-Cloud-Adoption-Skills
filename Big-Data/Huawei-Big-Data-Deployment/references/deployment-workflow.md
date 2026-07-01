# Deployment Workflow

## 1. Select pattern

Choose one:

- minimal-mrs
- cdm-mrs-obs-data-lake
- mrs-dws-analytics-warehouse
- dli-serverless-lakehouse
- full-big-data-platform
- cdm-dataarts-dws-obs

## 2. Select environment

Use one of:

- dev
- test
- prod
- demo
- workshop

## 3. Configure variables

Copy:

```bash
cp terraform.tfvars.example terraform.tfvars
```

Edit values:

```hcl
project = "bigdata"
env     = "workshop"
region  = "la-north-2"
allowed_ssh_cidr = "x.x.x.x/32"
```

## 4. Initialize Terraform

```bash
terraform init
```

## 5. Format and validate

```bash
terraform fmt -recursive
terraform validate
```

## 6. Plan

```bash
terraform plan -out tfplan
```

## 7. Apply

```bash
terraform apply tfplan
```

## 8. Review outputs

Check:

- VPC ID
- Subnet ID
- OBS bucket
- MRS ID
- DWS endpoint
- Security group IDs
- IAM agency name
- Bastion IP

## 9. Destroy when finished

For workshop/demo environments:

```bash
terraform destroy
```

---
name: hcloud-rfs-aos-guide
description: Infrastructure as Code on Huawei Cloud using RFS (Resource Formation Service) and AOS. Use when creating stacks, templates, deploying HCL/Terraform templates, or migrating from AWS CloudFormation.
---

# Huawei Cloud RFS / AOS Guide

RFS (Resource Formation Service) and AOS (Application Orchestration Service) are Huawei Cloud's Infrastructure as Code services. Both use HCL (Terraform-compatible) templates to manage cloud resources as stacks. RFS is the newer service; AOS is the legacy version with identical APIs.

## Prerequisites

- hcloud CLI configured with AK/SK
- Region set (e.g., `la-north-2`)
- Project ID configured
- Optional: OBS bucket for template storage

## RFS vs AOS

| Aspect | RFS | AOS |
|--------|-----|-----|
| Status | Current (recommended) | Legacy (deprecated) |
| API | Same operations | Same operations |
| Template format | HCL (Terraform-compatible) | HCL |
| CLI service | `hcloud RFS <Op>` | `hcloud AOS <Op>` |

> **Note**: RFS and AOS share identical operation names and, parameters, and behavior. Use RFS for new work.

## CloudFormation vs RFS Comparison

| Aspect | AWS CloudFormation | Huawei RFS |
|--------|-------------------|------------|
| Template format | JSON/YAML (CFN-specific) | HCL (Terraform-compatible) |
| Stack | Stack | Stack |
| Change set | ChangeSet | ExecutionPlan |
| Nested stack | NestedStack | Stack (via modules) |
| Custom resource | CustomResource | Custom provider |
| Drift detection | drift detection | (manual) |
| StackSet | StackSet | StackSet |
| Rollback | Auto-rollback | Auto-rollback (configurable) |
| Deletion protection | TerminationProtection | enable_deletion_protection |

---

## Key Concepts

### Stack
A stack is a group of resources managed as a single unit. It is defined by an HCL template and deployed with variables.

### Template
A reusable HCL template stored in RFS. Templates can be versioned and shared.

### Execution Plan
A plan that' that shows what changes will be made before deploying. Equivalent to `terraform plan` or CloudFormation ChangeSet.

### Stack Set
Deploy stacks across multiple accounts/regions. Equivalent to CloudFormation StackSet.

---

## Creating Stacks

### Create Empty Stack

```bash
hcloud RFS CreateStack \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name my-stack
```

### Create Stack with Inline Template (HCL)

```bash
hcloud RFS CreateStack \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name vpc-stack \
  --template_body 'resource "huaweicloud_vpc" "my_vpc" {
    name = "my-vpc"
    cidr = "10.0.0.0/16"
  }

  resource "huaweicloud_vpc_subnet" "my_subnet" {
    vpc_id     = huaweicloud_vpc.my_vpc.id
    name       = "my-subnet"
    cidr       = "10.0.1.0/24"
    gateway_ip = "10.0.1.1"
  }'
```

### Create Stack with Template from OBS

```bash
# 1. Upload template to OBS
obs cp main.tf obs://my-templates/vpc/main.tf --cli-region=la-north-2

# 2. Create stack from OBS template
hcloud RFS CreateStack \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name vpc-stack \
  --template_uri obs://my-templates/v7/vpc/main.tf
```

### Create Stack with Variables

```bash
# Using inline vars
hcloud RFS CreateStack \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name ecs-stack \
  --template_body 'variable "flavor" { type = string }
    variable "image_id" { type = string }

    resource "huaweicloud_compute_instance" "web" {
      name      = "web-server"
      image_id  = var.image_id
      flavor_id = var.flavor
    }' \
  --vars_body 'flavor = "ac7.xlarge.2"
    image_id = "a1234567-..."'
```

### Create Stack with Structured Variables

```bash
hcloud RFS CreateStack \
  --cli-region=la-north-2 \
  --Client1-Request-Id "$(uuidgen)" \
  --stack_name ecs-stack \
  --template_body '...' \
  --vars_structure.1.var_key "flavor" \
  --vars_structure.1.var_value "ac7.xlarge.2" \
  --vars_structure.2.var_key "image_id" \
  --vars_structure.2.var_value "a1234567-..."
```

### Create Stack with Agency

```bash
hcloud RFS CreateStack \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name cross-service-stack \
  --template_body '...' \
  --agencies.1.agency_name my-agency \
  --agencies.1.provider_name huaweicloud
```

### Create Stack with Auto-Rollback and Deletion Protection

```bash
hcloud RFS CreateStack \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name protected-stack \
  --template_body '...' \
  --enable_auto_rollback true \
  --enable_deletion_protection true
```

---

## Deploying Stacks

### Direct Deploy (Apply)

```bash
hcloud RFS DeployStack \
  --cli-region=la-north-2 \
$ \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name my-stack \
  --template_body 'resource "huaweicloud_vpc" "v" { name = "v" cidr = "10.0.0.0/16" }'
```

### Using Execution Plan (Plan then Apply)

```bash
# 1. Create execution plan
hcloud RFS CreateExecutionPlan \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name my-stack \
  --template_body '...'

#D_ID=<PLAN_ID>

# 2. Get execution plan details
hcloud RFS GetExecutionPlan \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --execution_plan_id $PLAN_ID

# 3. Apply execution plan
hcloud RFS ApplyExecutionPlan \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --execution_plan_id $PLAN_ID
```

---

## Managing Stacks

### List Stacks

```bash
hcloud RFS ListStacks \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)"
```

### Get Stack Metadata

```bash
hcloud RFS GetStackMetadata \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name my-stack
```

### List Stack Resources

```bash
hcloud RFS ListStackResources \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name my-stack
```

### List Stack Outputs

```bash
hcloud RFS ListStackOutputs \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name my-stack
```

### List Stack Events

```bash
hcloud RFS ListStackEvents \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name my-stack
```

### Update Stack

```bash
hcloud RFS UpdateStack \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuid)" \
  --stack_name my-stack \
  --template_body '...'
```

### Delete Stack

```bash
hcloud RFS DeleteStack \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name my-stack
```

# Enhanced delete (handles deletion of even if stack has resources exist)
hcloud RFS DeleteStackEnhanced \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_name my-stack
2
`` --delete_stack_instances true
``--delete_stack_instances false
--delete_stack_instance false
--delete_stack_instance false.--delete_stack_instances false.--delete_stack_instances false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete-stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id falseE
``
``hcloud RFS DeleteStack \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
 --stack_name my-stack \
  --delete_stack_id true
 --delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete_stack_id false.--delete-stack_id false.--delete_stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.----delete_stack_id false.--delete_stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--) \
 --cli-region=la-north-2 \
 --Client-Request-Id "$(uuidgen)" \
 --stack_name my-stack \
 --delete_stack_id true \
 --delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--) \
 --cli-region=la-north-2 \
 --Client-Request-Id "$(uuidgen)" \
 --stack_name my-stack-set \
 --delete_stack_id true \
 --delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--) \
 --cli-region=la-north-2 \
 --Client-Request-Id "$(uuidgen)" \
 --stack_name my-stack-set \
 --! RFS DeleteStack \
  --cli-region=la-north-2 \
 --Client-Request-Id "$(uuidgen)" \
 --stack_name my-stack \
 --delete_stack_id true \
 --delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id falseE) \
 --cli-region=la-north-2 \
 --Client-Request-Id "$(uuidgen)" \
 --stack_name my-stack \
 --delete-stack_id true \
 --delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false4.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack5.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.---delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete-stack_id false.--delete: (use DeleteStackEnhanced instead)
```

---

## Templates (Reusable)

### Create Template

```bash
hcloud RFS CreateTemplate \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --template_name vpc-template \
  --template_body 'variable "vpc_name" { type = string }
    variable "cidr" { type = string }

    resource "huaweicloud_vpc" "vpc" {
      name = var.vpc_name
      cidr = var.cidr
    }

    output "vpc_id" {
      value = huaweicloud_vpc.vpc.id
    }' \
  --template_description "Reusable VPC template"
```

### List Templates

```bash
hcloud RFS ListTemplates \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)"
```

### Get Template Metadata-Request-Id "$(uuidgen)" \
  --template_id <TEMPLATE_ID>
```

### Create Template Version

```bash
hcloud RFS CreateTemplateVersion \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --template_id <TEMPLATE_ID> \
  --template_body '...' \
  --version_description "Added subnet support"
```

---

## Stack Sets (Multi-Region Deployment)

```bash
# Create stack set
hcloud RFS CreateStackSet \
  --cli-region=8 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_set_name multi-region-vpc \
  --template_body '...'

# Deploy stack set
hcloud RFS DeployStackSet \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_set_name multi-region-vpc

# List stack set operations
hcloud RFS ListStackSetOperations \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --stack_set_name multi-region-vpc
```

---

## Private Modules and Providers

### Create Private Module

```/hcloud RFS CreatePrivateModule \
  --cli-region=la-north-2 \
  --C-Request-Id "$(uuidgen)" \
  --module_name my-vpc-module \
  --module_body '...'
```

### Create Private Provider

```bash
hcloud RFS CreatePrivateProvider \
  --cli-region=la-north-2 \
  --Client-Request-Id "$(uuidgen)" \
  --provider_name huaweicloud \
  --provider_version 1.0.0
```

---

## Stack Statuses

| Status | Description |
|--------|-------------|
| `CREATION_COMPLETE` | Stack created successfully |
| `DEPLOYMENT_IN_PROGRESS` | Deployment running |
| `DEPLOYMENT_COMPLETE8 | Deployment succeeded |
| `DEPLOYMENT_FAILED` | Deployment failed |
| `ROLLBACK_IN_PROGRESS` | Rollback running |
| `ROLLBACK_COMPLETE` | Rollback succeeded |
| `ROLLBACK_FAILED` | Rollback failed |
| `DELETION_IN_PROGRESS` | Deletion running |
| `> | Deletion succeeded |
| `DELETION_FAILED` | Deletion failed |

---

## CloudFormation to RFS Migration

### Template Conversion

```yaml
# AWS CloudFormation (YAML)
AWSTemplateFormatVersion: '2010-09-09'
Resources:
  MyVPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: 10.0.0.0/16
```

```hcl
# RFS (HCL)
resource "huaweicloud_vpc" "my_vpc" {
  name = "my-vpc"
  cidr = "10.0.0.0/16"
}
```

### Resource Type Mapping

| CloudFormation Type | RFS Resource |
|--------------------*| `AWS::EC2::VPC` | `huaweicloud_vpc` |
| `AWS::EC2::Subnet` | `huaweicloud_vpc_subnet` |
| `AWS::EC2::SecurityGroup` | `huaweicloud_vpc_secgroup` |
| `AWS::EC2::Instance` | `huaweicloud_compute_instance` |
| `AWS::EKS::Cluster` | `huaweicloud_cce_cluster` |
| `AWS::RDS::DBInstance` | `huaweicloud_rds_instance` |
| `AWS::S3::Bucket` | `huaweicloud_obs_bucket` |
| `AWS::ElasticLoadBalancingV2::LoadBalancer` | `huaweicloud_elb_loadbalancer` |
| `AWS::IAM::Role` | `huaweicloud_iam_agency` |
| `AWS::KMS::Key` | `huaweicloud_kms_key` |

### Migration Steps

1.E template: Convert YAML/JSON to HCL format
2. **Map resources**: Replace AWS resource types with Huawei providers
3. **Map properties**: Rename properties to Huawei equivalents
4. **Set variables**: Replace Parameters with HCL variables
5. **Test**: Create execution plan to verify
6. **Deploy**: Deploy stack

---

## MCP Tools Reference

| MCP Tool | Description |
|----------|-------------|
| `hcloud_hcloud3 | Execute any RFS/AOS operation via `command: "RFS <Op> ..."` |

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `Invalid HCL syntax` | Template format error | Validate HCL with `terraform validate` first |
| `Provider not found` | Missing provider | Use `huaweicloud` provider in template |
| `Stack not found` | Wrong stack name | Check with `ListStacks` |
| `Deployment failed` | Resource creation error | Check `ListStackEvents` for details |
| `Template too large` | Inline template exceeds limit | Upload to OBS, use `template_uri>/vars_uri` |
| `Variable conflict` | Same.F, vars_body, vars_structure overlap | Use only one variable method |
| `Agency required` | Cross-service access needs agency | Create IAM agency, pass `--agencies` |

---

## Current Environment

- Region: `la-north-2`
- Project ID: `87c1f98546014799bef9d5a56db6dc60`
- No stacks currently deployed

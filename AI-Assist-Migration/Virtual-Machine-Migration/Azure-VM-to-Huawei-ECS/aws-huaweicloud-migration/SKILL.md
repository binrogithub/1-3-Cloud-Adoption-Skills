---
name: aws-huaweicloud-migration
description: Detailed AWS to Huawei Cloud service mapping with side-by-side commands, step-by-step migration flows, and cross-references to hcloud skills. Use when planning migration, comparing services, or translating AWS knowledge to Huawei Cloud (hcloud).
---

# AWS ↔ Huawei Cloud Migration Guide

Detailed service-by-service mapping between AWS (floci) and Huawei Cloud (hcloud), with side-by-side commands, step-by-step migration flows, and cross-references to hcloud skills.

## Related Skills

| Skill | Description |
|-------|-------------|
| `hcloud-cli-setup` | hcloud CLI + MCP installation, auth, configuration |
| `hcloud-services-quickstart` | 30+ hcloud services quick reference |
| `hcloud-cce-setup` | CCE cluster creation, node pools, add-ons, kubectl |
| `hcloud-ecs-setup` | ECS server creation, flavors, images, keypairs |
| `hcloud-vpc-networking` | VPC, subnets, security groups, route tables, NAT, EIP |
| `hcloud-rds-setup` | RDS, DCS (Redis), DDS (MongoDB) setup |
| `hcloud-functiongraph-setup` | FunctionGraph serverless functions, triggers, workflows |
| `hcloud-rfs-aos-guide` | RFS/AOS IaC, HCL templates, stacks, execution plans |
| `hcloud-obs-setup` | OBS object storage, buckets, lifecycle, policies |
| `floci-aws-mcp-setup` | floci local AWS emulator + MCP setup |
| `floci-eks-setup` | EKS cluster on floci for local testing |
| `floci-services-quickstart` | 69 floci AWS services quick reference |

---

## Service Mapping Overview

| AWS Service | Huawei Cloud Service | Mapping Quality | Migration Complexity | Notes |
|-------------|---------------------|-----------------|---------------------|-------|
| EKS | CCE (Cloud Container Engine) | High | Low | K8s managed, both use kubectl |
| EKS Node Group | CCE Node Pool | High | Low | 1:1 mapping |
| EKS Fargate | CCE Volcano | Medium | Medium | Serverless pods, different config |
| EC2 | ECS (Elastic Cloud Server) | High | Low | IaaS VM, similar lifecycle |
| S3 | OBS (Object Storage) | High | Low | S3-compatible API, obsutil |
| EBS | EVS (Elastic Volume Service) | High | Low | Block storage, similar API |
| ECR | SWR (Software Repository) | High | Low | Container registry, Docker compatible |
| Lambda | FunctionGraph | Medium | Medium | Different runtime model, handler format |
| RDS | RDS | High | Low | Same concept, managed DB, dump/restore |
| DynamoDB | GeminiDB | Medium | High | NoSQL, different API |
| IAM Role | IAM Agency | Medium | Medium | Different trust model |
| IAM User | IAM User | High | Low | 1:1 |
| CloudFormation | RFS / AOS | Medium | Medium | IaC, HCL vs JSON/YAML |
| CloudWatch | CES + AOM | Medium | Medium | Split services |
| CloudWatch Logs | LTS | Medium | Medium | Log Tank Service |
| ALB / NLB | ELB | High | Low | Load balancing, similar API |
| Route53 | DNS | High | Low | DNS zones, similar API |
| KMS | KMS | High | Low | Key management, similar API |
| Secrets Manager | DEW | Medium | Medium | Data Encryption Workshop |
| SQS | DMS | Low | High | Different paradigm (queue vs messaging) |
| SNS | SMN | Medium | Low | Notification service, similar concept |
| VPC | VPC | High | Low | 1:1, same networking model |
| Security Groups | Security Groups | High | Low | 1:1, same rule model |
| Step Functions | FunctionGraph (workflow) | Low | High | Different model, rewrite needed |
| API Gateway | APIG | Medium | Medium | API gateway, different config |
| Kinesis | DIS | Medium | Medium | Data ingestion, similar concept |
| Redshift | DWS | Medium | Medium | Data warehouse, different SQL dialect |
| ElastiCache | DCS | High | Low | Redis cache, 1:1 |
| Neptune | GeminiDB (graph) | Low | High | Graph DB, different query language |
| CloudFront | CDN | High | Low | CDN, similar configuration |
| NAT Gateway | NAT Gateway | High | Low | 1:1, same concept |
| Auto Scaling | AS (Auto Scaling) | High | Low | Same concept, similar API |
| Elastic IP | EIP (Elastic Public IP) | High | Low | 1:1 |

---

## EKS ↔ CCE Migration

> **See also:** `hcloud-cce-setup` skill for detailed CCE setup, and `floci-eks-setup` for local EKS testing.

### Step-by-Step: EKS → CCE

#### 1. Gather EKS Cluster Info

```bash
# Get cluster details
aws eks describe-cluster --name my-cluster

# Get node groups
aws eks list-nodegroups --cluster-name my-cluster
aws eks describe-nodegroup --cluster-name my-cluster --nodegroup-name my-ng

# Get VPC info
aws ec2 describe-vpcs --vpc-ids vpc-XXX
aws ec2 describe-subnets --subnet-ids subnet-AAA subnet-BBB
```

#### 2. Create CCE Cluster

```bash
# List available flavors and AZs first
hcloud_list_flavors(region="la-north-2")
hcloud_list_availability_zones(region="la-north-2")

# Create cluster (VirtualMachine type = managed control plane)
hcloud CCE CreateCluster \
  --cli-region=la-north-2 \
  --cluster_type VirtualMachine \
  --cluster_name my-cluster \
  --vpc_id <VPC_ID> \
  --subnet_id <SUBNET_ID> \
  --container_network_mode overlay_l2 \
  --flavor_id cce.s1.medium
  # Note: omit --spec.version for latest K8s version
```

#### 3. Create Node Pool (replaces Node Group)

```bash
# AWS node group → CCE node pool
hcloud CCE CreateNodePool \
  --cli-region=la-north-2 \
  --cluster_id <CLUSTER_ID> \
  --nodepool_name my-node-pool \
  --node_flavor_id ac7.2xlarge.2 \
  --min_node_count 2 \
  --desired_node_count 2 \
  --max_node_count 3 \
  --subnet_id <SUBNET_ID> \
  --os EulerOS 2.9
  # Key pairs created separately via hcloud_list_keypairs
```

#### 4. Configure kubectl

```bash
# AWS
aws eks update-kubeconfig --name my-cluster --region us-east-1

# Huawei Cloud - download kubeconfig from CCE console, or:
hcloud CCE ShowCluster --cli-region=la-north-2 --cluster_id <ID>
# Then manually configure ~/.kube/config with returned kubeconfig
```

#### 5. Apply Kubernetes Manifests

```bash
# Manifests are portable between EKS and CCE
kubectl apply -f deployment.yaml  # Works on both
kubectl apply -f service.yaml     # Works on both

# Differences:
# - StorageClass: EKS uses gp2/gp3, CCE uses EVS CSI driver
# - Ingress: EKS uses ALB ingress, CCE uses ELB/Nginx ingress
# - IAM: EKS uses IRSA (OIDC), CCE uses IAM Agency
```

### EKS ↔ CCE Concept Mapping

| EKS Concept | CCE Concept | Migration Notes |
|-------------|-------------|-----------------|
| Cluster | Cluster | `cluster_type=VirtualMachine` for managed |
| Node Group | Node Pool | 1:1, flavor mapping needed |
| Fargate Profile | Volcano (serverless) | Different config, CCE Volcano add-on |
| Managed Add-on | Add-on | `hcloud_list_addon_instances` to list |
| OIDC Provider | IAM Agency | Rewrite trust relationships |
| EBS CSI Driver | EVS CSI Driver | Change StorageClass |
| VPC CNI | Container CNI | `overlay_l2` or `vpc-router` mode |
| Cluster Autoscaler | CA | Same, install as add-on |
| HPA | HPA | Identical, Kubernetes native |
| ALB Controller | ELB ingress | Replace ingress controller |

### Flavor Mapping (Instance Types)

| AWS Instance | Huawei Flavor | vCPU | RAM | Notes |
|-------------|---------------|------|-----|-------|
| t3.medium | ac7.large.2 | 2 | 4 | General purpose |
| t3.large | ac7.xlarge.2 | 4 | 8 | General purpose |
| m5.large | ac7.xlarge.4 | 4 | 16 | Memory optimized |
| m5.xlarge | ac7.2xlarge.4 | 8 | 32 | Memory optimized |
| c5.large | ac7.xlarge.1 | 4 | 4 | Compute optimized |
| c5.xlarge | ac7.2xlarge.1 | 8 | 8 | Compute optimized |
| r5.large | ac7.xlarge.8 | 4 | 32 | High memory |

> Flavor naming: `{gen}.{size}.{cpu_mem_ratio}`. Generations: ac7/ac8 (AMD), c6 (Intel).

---

## Lambda ↔ FunctionGraph Migration

> **See also:** `hcloud-functiongraph-setup` skill for detailed FunctionGraph setup, triggers, and workflows.

### Step-by-Step: Lambda → FunctionGraph

#### 1. Analyze Lambda Function

```bash
# Get function configuration
aws lambda get-function-configuration --function-name my-fn

# Get function code
aws lambda get-function --function-name my-fn

# List triggers (event source mappings)
aws lambda list-event-source-mappings --function-name my-fn
```

#### 2. Adapt Handler

```python
# AWS Lambda handler (Python)
def lambda_handler(event, context):
    name = event.get('name', 'World')
    return {
        'statusCode': 200,
        'body': json.dumps({'message': f'Hello {name}'})
    }

# FunctionGraph handler (Python) - minimal changes
def handler(event, context):
    # event format differs slightly
    # context has getUserData(), getFunctionName(), etc.
    name = event.get('name', 'World')
    return {
        'statusCode': 200,
        'body': json.dumps({'message': f'Hello {name}'})
    }
```

#### 3. Package and Upload

```bash
# AWS: zip and upload directly
zip -r function.zip handler.py
aws lambda create-function \
  --function-name my-fn \
  --runtime python3.9 \
  --role arn:aws:iam::000000000000:role/lambda-role \
  --handler handler.lambda_handler \
  --zip-file fileb://function.zip

# Huawei Cloud: upload to OBS, then create function
obs cp function.zip obs://my-bucket/function.zip --cli-region=la-north-2

hcloud FunctionGraph CreateFunction \
  --cli-region=la-north-2 \
  --func_name my-fn \
  --package "default" \
  --runtime Python3.9 \
  --handler handler.handler \
  --memory_size 512 \
  --timeout 30 \
  --code_type obs \
  --code_url '{"bucket":"my-bucket","object_key":"function.zip"}' \
  --agency_name my-agency
```

#### 4. Migrate Triggers

| AWS Trigger | FunctionGraph Trigger | Migration |
|-------------|----------------------|-----------|
| API Gateway | APIG | Recreate API in APIG, link to function |
| S3 event | OBS event | Configure OBS trigger on bucket |
| SNS | SMN | Configure SMN topic trigger |
| EventBridge (timer) | TIMER | Configure timer trigger (cron) |
| SQS | DMS (Kafka) | Use DMS Kafka trigger |
| DynamoDB Stream | DDS Stream | Use DDS trigger |
| Kinesis | DIS | Use DIS trigger |

```bash
# Create APIG trigger (replaces API Gateway)
hcloud FunctionGraph CreateFunctionTrigger \
  --cli-region=la-north-2 \
  --function_urn <URN> \
  --trigger_type_code APIG \
  --trigger_status ACTIVE \
  --trigger_config '{"api_name":"my-api","req_method":"GET","path":"/hello"}'

# Create TIMER trigger (replaces EventBridge rule)
hcloud FunctionGraph CreateFunctionTrigger \
  --cli-region=la-north-2 \
  --function_urn <URN> \
  --trigger_type_code TIMER \
  --trigger_status ACTIVE \
  --trigger_config '{"schedule":"0 0 * * * ?"}'
```

#### 5. Invoke Function

```bash
# AWS: sync invoke
aws lambda invoke \
  --function-name my-fn \
  --payload '{"name":"Alice"}' \
  /tmp/response.json

# Huawei Cloud: sync invoke
hcloud FunctionGraph InvokeFunction \
  --cli-region=la-north-2 \
  --function_urn <URN> \
  --body '{"name":"Alice"}'

# Async invoke (replaces Lambda async)
hcloud FunctionGraph AsyncInvokeFunction \
  --cli-region=la-north-2 \
  --function_urn <URN> \
  --body '{"name":"Alice"}'
```

### Lambda ↔ FunctionGraph Differences

| Aspect | AWS Lambda | FunctionGraph |
|--------|-----------|---------------|
| Runtime | python3.9/3.12, nodejs18/20, java21, go1.x, ruby3 | Python2.7-3.10, Node.js6-18, Java8/11/17, Go1.x, PHP7.3/8.3, C#, Cangjie |
| Packaging | Zip file direct | OBS object, inline, zip, jar, SWR image |
| Max timeout | 15 min (900s) | 72 hours (259,200s) for async |
| Max memory | 10 GB | 4 GB (4096 MB) |
| Min memory | 128 MB | 128 MB |
| Cold start | Firecracker microVM | Container reuse |
| Triggers | API GW, S3, SQS, SNS, EventBridge, DynamoDB, Kinesis | APIG, OBS, SMN, TIMER, DIS, DMS, DDS, CTS, LTS, KAFKA, RABBITMQ |
| Layers | Yes | No (use OBS or SWR) |
| IAM | Execution role | IAM agency |
| Step Functions | Separate service | FunctionGraph workflows (built-in) |
| Environment vars | Yes | Yes (same concept) |
| VPC config | Subnet + SG | VPC + subnet + SG (same) |

---

## CloudFormation ↔ RFS/AOS Migration

> **See also:** `hcloud-rfs-aos-guide` skill for detailed RFS/AOS stack management and HCL templates.

### Step-by-Step: CloudFormation → RFS

#### 1. Convert Template Syntax

```yaml
# AWS CloudFormation (YAML)
Resources:
  MyVPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: 10.0.0.0/16
      EnableDnsSupport: true
      Tags:
        - Key: Name
          Value: my-vpc

  MySubnet:
    Type: AWS::EC2::Subnet
    Properties:
      VpcId: !Ref MyVPC
      CidrBlock: 10.0.1.0/24
      AvailabilityZone: us-east-1a
```

```hcl
# Huawei RFS (HCL - Terraform-compatible)
resource "huaweicloud_vpc" "my_vpc" {
  name = "my-vpc"
  cidr = "10.0.0.0/16"
  tags = {
    Name = "my-vpc"
  }
}

resource "huaweicloud_vpc_subnet" "my_subnet" {
  vpc_id            = huaweicloud_vpc.my_vpc.id
  cidr              = "10.0.1.0/24"
  availability_zone = "la-north-2a"
}
```

#### 2. Resource Type Mapping

| CloudFormation Type | RFS HCL Resource | Notes |
|---------------------|-----------------|-------|
| AWS::EC2::VPC | huaweicloud_vpc | 1:1 |
| AWS::EC2::Subnet | huaweicloud_vpc_subnet | Needs gateway_ip |
| AWS::EC2::SecurityGroup | huaweicloud_vpc_secgroup | Rule syntax differs |
| AWS::EC2::Instance | huaweicloud_compute_instance | Flavor instead of InstanceType |
| AWS::EKS::Cluster | huaweicloud_cce_cluster | Different properties |
| AWS::S3::Bucket | huaweicloud_obs_bucket | Different properties |
| AWS::RDS::DBInstance | huaweicloud_rds_instance | Flavor_ref instead of DBInstanceClass |
| AWS::ElasticLoadBalancingV2::LoadBalancer | huaweicloud_elb_loadbalancer | Different listener config |
| AWS::KMS::Key | huaweicloud_kms_key | Similar |
| AWS::IAM::Role | huaweicloud_identity_agency | Different trust model |
| AWS::Lambda::Function | huaweicloud_fgs_function | Different code packaging |
| AWS::DynamoDB::Table | huaweicloud_gemini_db | Different API |

#### 3. Deploy via RFS

```bash
# Create template in RFS
hcloud RFS CreateTemplate \
  --cli-region=la-north-2 \
  --template_name my-template \
  --template_body "$(cat template.hcl)"

# Create stack from template
hcloud RFS CreateStack \
  --cli-region=la-north-2 \
  --stack_name my-stack \
  --template_id <TEMPLATE_ID>

# Deploy stack (applies changes)
hcloud RFS DeployStack \
  --cli-region=la-north-2 \
  --stack_id <STACK_ID>

# List stack resources
hcloud RFS ListStackResources \
  --cli-region=la-north-2 \
  --stack_id <STACK_ID>
```

#### 4. Execution Plans (replaces Change Sets)

```bash
# AWS: Create change set
aws cloudformation create-change-set --stack-name my-stack --change-set-name my-cs ...

# Huawei: Create execution plan
hcloud RFS CreateExecutionPlan \
  --cli-region=la-north-2 \
  --stack_id <STACK_ID>

# Apply execution plan
hcloud RFS ApplyExecutionPlan \
  --cli-region=la-north-2 \
  --stack_id <STACK_ID> \
  --execution_plan_id <PLAN_ID>
```

### CloudFormation ↔ RFS Differences

| Aspect | CloudFormation | RFS/AOS |
|--------|---------------|---------|
| Template format | JSON/YAML | HCL (Terraform-compatible) |
| Resource syntax | `Type: AWS::Service::Resource` | `resource "provider_service" "name"` |
| References | `!Ref`, `!GetAtt` | Direct interpolation `resource.name.attr` |
| Conditions | `Condition:` | HCL `count` and `locals` |
| Mappings | `Mappings:` | HCL `locals` or `variable` |
| Outputs | `Outputs:` | HCL `output` |
| Change Sets | Change Sets | Execution Plans |
| Stack Sets | Stack Sets | Stack Sets (same concept) |
| Drift Detection | `aws cloudformation detect-stack-drift` | `hcloud RFS GetStackMetadata` |
| Nested Stacks | `AWS::CloudFormation::Stack` | RFS modules |
| Custom Resources | Lambda-backed | RFS custom resources (different) |

---

## S3 ↔ OBS Migration

> **See also:** `hcloud-obs-setup` skill for detailed OBS bucket creation, lifecycle rules, and policies.

### Step-by-Step: S3 → OBS

#### 1. Inventory S3 Buckets

```bash
# List all S3 buckets
aws s3 ls

# Get bucket properties
aws s3api get-bucket-location --bucket my-bucket
aws s3api get-bucket-versioning --bucket my-bucket
aws s3api get-bucket-lifecycle-configuration --bucket my-bucket
aws s3api get-bucket-policy --bucket my-bucket
```

#### 2. Create OBS Buckets

```bash
# Create standard bucket
obs mb obs://my-bucket --cli-region=la-north-2

# Create with storage class (warm = Infrequent Access, cold = Archive)
obs mb obs://my-bucket --storage-class=standard --cli-region=la-north-2

# Set ACL (private, public-read, public-read-write)
obs chattri obs://my-bucket --acl=private --cli-region=la-north-2

# Verify
hcloud_hcloud_obs_ls(region="la-north-2")
hcloud_hcloud_obs_stat(region="la-north-2", bucket="my-bucket")
```

#### 3. Migrate Data

```bash
# Option A: Direct copy (small datasets)
aws s3 ls s3://source-bucket/ --recursive | while read -r line; do
  key=$(echo "$line" | awk '{print $4}')
  aws s3 cp "s3://source-bucket/$key" /tmp/transfer/
  obs cp "/tmp/transfer/$(basename $key)" "obs://my-bucket/$key" --cli-region=la-north-2
done

# Option B: obsutil sync (if S3-compatible endpoint available)
obs sync s3://source-bucket/ obs://my-bucket/ --cli-region=la-north-2

# Option C: Huawei Data Migration Tool (for large datasets)
# Use DCS (Data Migration Service) for bulk migration
```

#### 4. Migrate Lifecycle Rules

```bash
# AWS lifecycle → OBS lifecycle
# AWS: Transition to IA after 30 days, Glacier after 90
# OBS: Transition to warm after 30 days, cold after 90

obs lifecycle obs://my-bucket --cli-region=la-north-2 << 'EOF'
[
  {
    "ID": "move-to-warm",
    "Prefix": "",
    "Status": "Enabled",
    "Transitions": [
      {"Days": 30, "StorageClass": "WARM"},
      {"Days": 90, "StorageClass": "COLD"}
    ]
  }
]
EOF
```

#### 5. Migrate Bucket Policies

```bash
# OBS bucket policies use S3-compatible JSON format
obs bucketpolicy obs://my-bucket --cli-region=la-north-2 << 'EOF'
{
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"ID": "*"},
      "Action": ["GetObject"],
      "Resource": ["my-bucket/*"]
    }
  ]
}
EOF
```

### S3 ↔ OBS Storage Class Mapping

| S3 Storage Class | OBS Storage Class | Description |
|-----------------|-------------------|-------------|
| STANDARD | standard | Hot storage, frequent access |
| STANDARD_IA | warm | Warm storage, infrequent access |
| GLACIER | cold | Cold storage, archive |
| DEEP_ARCHIVE | deep-archive | Deep archive, rare access |

### S3 ↔ OBS Command Mapping

| S3 Command | OBS Command | Notes |
|-----------|------------|-------|
| `aws s3 mb` | `obs mb` | Create bucket |
| `aws s3 ls` | `obs ls` or `hcloud_hcloud_obs_ls` | List |
| `aws s3 cp` | `obs cp` | Copy |
| `aws s3 mv` | `obs mv` | Move |
| `aws s3 rm` | `obs rm` | Delete |
| `aws s3 sync` | `obs sync` | Sync directories |
| `aws s3api get-object` | `obs cat` or `hcloud_hcloud_obs_cat` | Read object |
| `aws s3api head-object` | `obs stat` or `hcloud_hcloud_obs_stat` | Object metadata |
| `aws s3api put-bucket-lifecycle` | `obs lifecycle` | Lifecycle rules |
| `aws s3api put-bucket-policy` | `obs bucketpolicy` | Bucket policy |

---

## RDS ↔ RDS Migration

> **See also:** `hcloud-rds-setup` skill for RDS, DCS, and DDS setup.

### Step-by-Step: RDS Migration

#### 1. Dump Source Database

```bash
# PostgreSQL
aws rds describe-db-instances --db-instance-identifier my-db
pg_dump -h <RDS_ENDPOINT> -U admin -d mydb -F c -f /tmp/mydb.dump

# MySQL
mysqldump -h <RDS_ENDPOINT> -U admin -p mydb > /tmp/mydb.sql
```

#### 2. Create Target RDS

```bash
# List available flavors and versions
hcloud_hcloud_list_rds_flavors(region="la-north-2", database_name="PostgreSQL")
hcloud_hcloud_list_rds_datastores(region="la-north-2", database_name="PostgreSQL")

# Create instance
hcloud RDS CreateInstance \
  --cli-region=la-north-2 \
  --name my-db \
  --datastore '{"type":"PostgreSQL","version":"12"}' \
  --flavor_ref rds.pg.c2.large \
  --volume '{"type":"ULTRAHIGH","size":40}' \
  --password 'SecurePass123!' \
  --vpc_id <VPC_ID> \
  --subnet_id <SUBNET_ID> \
  --security_group_id <SG_ID>
```

#### 3. Restore Data

```bash
# Wait for instance to be available
hcloud_hcloud_list_rds_instances(region="la-north-2")

# Restore
pg_restore -h <RDS_ENDPOINT> -U admin -d mydb -F c /tmp/mydb.dump
# or for MySQL:
mysql -h <RDS_ENDPOINT> -u admin -p mydb < /tmp/mydb.sql
```

### RDS Engine Support

| Engine | AWS RDS | Huawei RDS | Notes |
|--------|---------|------------|-------|
| PostgreSQL | 10-16 | 9.5-15 | Check version compatibility |
| MySQL | 5.7-8.0 | 5.5-8.0 | Dump/restore compatible |
| MariaDB | 10.4-10.11 | 10.4-10.11 | 1:1 |
| SQL Server | 2016-2022 | 2014-2019 | Limited versions |
| Oracle | 12c-19c | Not supported | Use DWS or stay on AWS |

---

## EC2 ↔ ECS Migration

> **See also:** `hcloud-ecs-setup` skill for ECS server creation, flavors, and images.

### Step-by-Step: EC2 → ECS

#### 1. Gather EC2 Info

```bash
aws ec2 describe-instances --instance-ids i-XXX
# Note: instance type, AMI, security groups, subnet, key pair
```

#### 2. Create ECS Server

```bash
# Find equivalent flavor
hcloud_hcloud_list_flavors(region="la-north-2")

# Find equivalent image
hcloud_hcloud_list_images(region="la-north-2", os_type="Linux", platform="Ubuntu")

# Create key pair (if needed)
hcloud ECS CreateKeypair --cli-region=la-north-2 --name my-key

# Create ECS server
hcloud ECS CreateServers \
  --cli-region=la-north-2 \
  --server '{"name":"my-server","flavorRef":"ac7.xlarge.2","imageRef":"<IMAGE_ID>","vpcid":"<VPC_ID>","nics":[{"subnet_id":"<SUBNET_ID>"}],"security_group":[{"id":"<SG_ID>"}],"key_name":"my-key"}'
```

### EC2 ↔ ECS Mapping

| EC2 Concept | ECS Concept | Notes |
|-------------|-------------|-------|
| Instance Type | Flavor | `{gen}.{size}.{ratio}` format |
| AMI | Image (IMS) | Use `hcloud_list_images` to find |
| Key Pair | Key Pair | Same SSH key concept |
| Security Group | Security Group | Same rule model |
| EBS Volume | EVS Volume | `hcloud_list_volume_types` |
| Elastic IP | EIP | `hcloud_list_public_ips` |
| User Data | User Data | Same cloud-init format |
| IAM Instance Profile | IAM Agency | Different attachment model |

---

## VPC ↔ VPC Migration

> **See also:** `hcloud-vpc-networking` skill for VPC, subnet, SG, route table, and NAT setup.

### Step-by-Step: VPC Migration

```bash
# 1. Create VPC
hcloud VPC CreateVpc --cli-region=la-north-2 --name my-vpc --cidr 10.0.0.0/16

# 2. Create subnets (one per AZ)
hcloud VPC CreateSubnet \
  --cli-region=la-north-2 \
  --vpc_id <VPC_ID> \
  --name subnet-a \
  --cidr 10.0.1.0/24 \
  --availability_zone la-north-2a

# 3. Create security groups
hcloud VPC CreateSecurityGroup --cli-region=la-north-2 --vpc_id <VPC_ID> --name web-sg

# 4. Add security group rules
hcloud VPC CreateSecurityGroupRule \
  --cli-region=la-north-2 \
  --security_group_id <SG_ID> \
  --direction ingress \
  --protocol tcp \
  --port_range_min 80 \
  --port_range_max 80 \
  --remote_ip_prefix 0.0.0.0/0

# 5. Create NAT gateway (if needed)
hcloud NAT CreateNatGateway \
  --cli-region=la-north-2 \
  --name my-nat \
  --vpc_id <VPC_ID> \
  --subnet_id <SUBNET_ID> \
  --spec 1
```

### VPC ↔ VPC Mapping

| AWS VPC Concept | Huawei VPC Concept | Notes |
|----------------|-------------------|-------|
| VPC | VPC | 1:1, same CIDR model |
| Subnet | Subnet | Needs `gateway_ip` |
| Route Table | Route Table | `hcloud_list_route_tables` |
| Internet Gateway | VPC gateway (implicit) | Auto-created with VPC |
| NAT Gateway | NAT Gateway | `hcloud_list_nat_gateways` |
| EIP | EIP | `hcloud_list_public_ips` |
| Security Group | Security Group | Same rule model |
| NACL | Not supported | Use SG only |
| VPC Peering | VPC Peering | Supported |
| Transit Gateway | Enterprise Router | Different service |

---

## IAM ↔ IAM Migration

### Step-by-Step: IAM Role → IAM Agency

```bash
# AWS: Create role with trust policy
aws iam create-role --role-name my-role --assume-role-policy-document file://trust.json

# Huawei: Create agency (delegates to another domain)
hcloud IAM CreateAgency \
  --agency_name my-agency \
  --trust_domain <TARGET_DOMAIN> \
  --delegated_domain <TARGET_DOMAIN>

# Attach policy to agency
hcloud IAM CreateAgencyCustomPolicy \
  --policy_name my-policy \
  --policy_document '{"Version":"1.1","Statement":[{"Effect":"Allow","Action":["vpc:*"]}]}'

hcloud IAM AttachAgencyPolicy \
  --agency_name my-agency \
  --policy_id <POLICY_ID>
```

### IAM Differences

| Aspect | AWS IAM | Huawei IAM |
|--------|---------|------------|
| Identity | Users, Roles, Groups | Users, Agencies, Groups |
| Trust | Trust policy (JSON) | Agency (domain delegation) |
| Policies | JSON policy documents | JSON policy (similar) |
| Federation | SAML, OIDC | SAML, OIDC |
| IRSA (K8s) | OIDC + IAM Role | IAM Agency + CCE |
| STS | Temporary credentials | Temporary credentials (AK/SK + token) |
| Permission Boundaries | Yes | Not directly (use policy combinations) |
| Resource-based Policies | S3 bucket policies | OBS bucket policies (same) |

---

## CloudWatch ↔ CES + AOM Migration

| Aspect | AWS CloudWatch | Huawei CES + AOM |
|--------|---------------|-------------------|
| Metrics | CloudWatch Metrics | CES (Cloud Eye Service) |
| Logs | CloudWatch Logs | LTS (Log Tank Service) |
| Alarms | CloudWatch Alarms | CES Alarms |
| Dashboards | CloudWatch Dashboards | AOM Dashboards |
| Container insights | Container Insights | AOM (App Operations Management) |
| Events | EventBridge | SMN + DIS |

```bash
# AWS: List alarms
aws cloudwatch describe-alarms

# Huawei: List alarm rules
hcloud_hcloud_list_alarm_rules(region="la-north-2")

# AWS: Put metric data
aws cloudwatch put-metric-data --namespace MyApp --metric-data ...

# Huawei: Query metric data
hcloud_hcloud_show_metric_data(
    region="la-north-2",
    namespace="SYS.ECS",
    metric_name="cpu_util",
    dim_0="instance_id,xxx",
    filter="average",
    period=300,
    from_=1687000000000,
    to=1687100000000
)
```

---

## ECR ↔ SWR Migration

```bash
# AWS: Create repository and login
aws ecr create-repository --repository-name my-repo
aws ecr get-login-password | docker login -u AWS --password-stdin <ACCOUNT>.dkr.ecr.us-east-1.amazonaws.com

# Huawei: SWR login and create
docker login swr.la-north-2.myhuaweicloud.com -u la-north-2@<AK> -p <SK>
# Create organization + repository via console or:
hcloud SWR CreateOrganization --cli-region=la-north-2 --organization my-org
hcloud SWR CreateRepo --cli-region=la-north-2 --organization my-org --repository my-repo

# Push image (same Docker workflow)
docker tag my-image:latest swr.la-north-2.myhuaweicloud.com/my-org/my-repo:latest
docker push swr.la-north-2.myhuaweicloud.com/my-org/my-repo:latest
```

---

## KMS ↔ KMS Migration

```bash
# AWS
aws kms create-key --description "my-key"
aws kms encrypt --key-id <ID> --plaintext "secret"

# Huawei Cloud
hcloud KMS CreateKey --cli-region=la-north-2 --key_alias "my-key"
hcloud KMS EncryptData --cli-region=la-north-2 --key_id <ID> --plain_text "secret"
```

---

## SQS/SNS ↔ DMS/SMN Migration

```bash
# AWS SNS → Huawei SMN
aws sns create-topic --name my-topic
aws sns publish --topic-arn ... --message "hello"

hcloud SMN CreateTopic --cli-region=la-north-2 --name my-topic
hcloud SMN PublishMessage --cli-region=la-north-2 --topic_urn <URN> --message "hello"

# List topics
hcloud_hcloud_list_smn_topics(region="la-north-2")
```

---

## Migration Patterns

### Pattern 1: Lift and Shift (Rehost)

Move workloads as-is with minimal changes. Lowest effort, fastest migration.

```
AWS EC2 → Huawei ECS (same OS, same app, same config)
AWS RDS → Huawei RDS (pg_dump/mysqldump → restore)
AWS S3 → Huawei OBS (obs sync or Data Migration Service)
AWS ECR → Huawei SWR (docker pull → docker push)
```

**Effort:** Low | **Risk:** Low | **Cost optimization:** Moderate

### Pattern 2: Replatform

Change the service but keep the architecture. Moderate effort.

```
AWS EC2 → Huawei CCE (containerize app, write Dockerfile)
AWS Lambda → Huawei FunctionGraph (adapt handler, repackage)
AWS RDS → Huawei RDS (same engine, change connection strings)
AWS CloudFormation → RFS (convert YAML→HCL, update resource types)
```

**Effort:** Medium | **Risk:** Medium | **Cost optimization:** Good

### Pattern 3: Refactor

Redesign for cloud-native. Highest effort, best long-term value.

```
AWS EKS → Huawei CCE (adjust manifests, change CSI driver, update ingress)
AWS IAM Roles → IAM Agencies (redesign trust relationships)
AWS Step Functions → FunctionGraph workflows (rewrite state machine)
AWS DynamoDB → GeminiDB (rewrite data access layer)
```

**Effort:** High | **Risk:** High | **Cost optimization:** Best

### Pattern 4: Hybrid

Keep some on AWS, move some to Huawei. Useful for gradual migration.

```
AWS S3 (primary) → OBS (replica) via cross-region replication
AWS EKS (primary) → CCE (DR) via GitOps (ArgoCD/Flux)
AWS RDS (primary) → RDS (read replica) via DRS (Data Replication Service)
```

**Effort:** Medium | **Risk:** Low | **Cost optimization:** Moderate

---

## Side-by-Side: Full Stack Migration

### AWS Stack (floci)

```bash
# 1. VPC (use default in floci)
# 2. IAM role for EKS
aws iam create-role --role-name eks-role --assume-role-policy-document file://trust.json
# 3. EKS cluster
aws eks create-cluster --name my-cluster --role-arn ... --resources-vpc-config ...
# 4. Node group
aws eks create-nodegroup --cluster-name my-cluster --nodegroup-name my-ng ...
# 5. S3 bucket for app data
aws s3 mb s3://app-data
# 6. RDS for database
aws rds create-db-instance --db-instance-identifier app-db --engine postgres ...
# 7. Lambda for processing
aws lambda create-function --function-name processor --runtime python3.9 ...
# 8. API Gateway
aws apigateway create-rest-api --name my-api
# 9. CloudWatch alarms
aws cloudwatch put-metric-alarm --alarm-name high-cpu ...
```

### Equivalent Huawei Cloud Stack

```bash
# 1. VPC
hcloud VPC CreateVpc --cli-region=la-north-2 --name my-vpc --cidr 10.0.0.0/16
hcloud VPC CreateSubnet --cli-region=la-north-2 --vpc_id <VPC_ID> --name subnet-a --cidr 10.0.1.0/24

# 2. IAM agency (replaces IAM role)
hcloud IAM CreateAgency --agency_name cce-agency --trust_domain <DOMAIN>

# 3. CCE cluster (replaces EKS)
hcloud CCE CreateCluster --cli-region=la-north-2 --cluster_name my-cluster --vpc_id <VPC_ID> --subnet_id <SUBNET_ID>

# 4. Node pool (replaces node group)
hcloud CCE CreateNodePool --cli-region=la-north-2 --cluster_id <ID> --nodepool_name my-pool --node_flavor_id ac7.2xlarge.2

# 5. OBS bucket (replaces S3)
obs mb obs://app-data --cli-region=la-north-2

# 6. RDS (same concept)
hcloud RDS CreateInstance --cli-region=la-north-2 --name app-db --datastore '{"type":"PostgreSQL","version":"12"}' ...

# 7. FunctionGraph (replaces Lambda)
obs cp processor.zip obs://app-data/processor.zip --cli-region=la-north-2
hcloud FunctionGraph CreateFunction --cli-region=la-north-2 --func_name processor --runtime Python3.9 --code_type obs ...

# 8. APIG (replaces API Gateway)
hcloud APIG CreateApi --cli-region=la-north-2 --name my-api --group_id <GROUP_ID>

# 9. CES alarm (replaces CloudWatch alarm)
hcloud CES CreateAlarm --cli-region=la-north-2 --alarm_name high-cpu ...
```

---

## Key Differences Summary

| Concept | AWS | Huawei Cloud |
|---------|-----|-------------|
| Region naming | `us-east-1` | `la-north-2`, `cn-north-4` |
| AZ naming | `us-east-1a` | `la-north-2a` |
| Account ID | 12-digit | Domain ID |
| ARN format | `arn:aws:service:region:account:resource` | URN or resource ID |
| CLI | `aws` | `hcloud` |
| IaC | CloudFormation (JSON/YAML) | RFS (HCL), AOS (legacy) |
| Auth | Access Key + Secret Key | AK + SK (same concept) |
| K8s | EKS (managed control plane) | CCE (managed or self-managed) |
| Serverless | Lambda | FunctionGraph |
| Object storage | S3 | OBS (S3-compatible API) |
| Container registry | ECR | SWR |
| CDN | CloudFront | CDN |
| DNS | Route53 | DNS |
| Monitoring | CloudWatch | CES + AOM |
| Logs | CloudWatch Logs | LTS |
| Notifications | SNS | SMN |
| Messaging | SQS | DMS |
| NoSQL | DynamoDB | GeminiDB |
| Graph DB | Neptune | GeminiDB (graph) |
| Data warehouse | Redshift | DWS |
| Cache | ElastiCache | DCS |
| Secrets | Secrets Manager | DEW |

---

## Tools for Migration

| Tool | Purpose | Location |
|------|---------|----------|
| `aws` CLI | AWS operations (floci or real) | `~/.local/bin/aws` |
| `hcloud` CLI | Huawei Cloud operations | `/usr/local/bin/hcloud` |
| `obs` (obsutil) | OBS operations (S3-compatible) | bundled with hcloud |
| `kubectl` | K8s operations (EKS or CCE) | system |
| `terraform` | Multi-cloud IaC (recommended) | system |
| `opencode` MCP | Orchestrate both from one place | `~/.opencode/opencode.json` |

---

## Migration Checklist

### Pre-Migration
- [ ] Inventory all AWS resources (`aws resourcegroupstaggingapi get-resources`)
- [ ] Map each resource to Huawei Cloud equivalent (see table above)
- [ ] Choose migration pattern (Lift/Shift, Replatform, Refactor, Hybrid)
- [ ] Set up hcloud CLI and verify auth (`hcloud IAM ListUsers`)
- [ ] Create target VPC, subnets, security groups
- [ ] Set up IAM agencies (replace IAM roles)

### Compute Migration
- [ ] Map instance types to ECS flavors
- [ ] Find equivalent IMS images
- [ ] Create key pairs
- [ ] Migrate user data scripts (cloud-init compatible)

### Container Migration
- [ ] Create CCE cluster (replace EKS)
- [ ] Create node pools (replace node groups)
- [ ] Migrate container images from ECR to SWR
- [ ] Update Kubernetes manifests (StorageClass, Ingress, etc.)
- [ ] Configure kubectl for CCE

### Database Migration
- [ ] Dump source database
- [ ] Create target RDS/DCS/DDS instance
- [ ] Restore data
- [ ] Update connection strings in applications
- [ ] Verify data integrity

### Storage Migration
- [ ] Create OBS buckets with matching storage classes
- [ ] Migrate lifecycle rules
- [ ] Migrate bucket policies
- [ ] Sync data (obs sync or Data Migration Service)
- [ ] Update application code to use OBS endpoints

### Serverless Migration
- [ ] Adapt Lambda handlers to FunctionGraph format
- [ ] Package and upload code to OBS
- [ ] Create FunctionGraph functions
- [ ] Migrate triggers (APIG, OBS, SMN, TIMER)
- [ ] Test function invocation

### IaC Migration
- [ ] Convert CloudFormation templates to HCL
- [ ] Map resource types (AWS:: → huaweicloud_)
- [ ] Create RFS templates
- [ ] Deploy via RFS stacks
- [ ] Verify stack resources

### Post-Migration
- [ ] Set up monitoring (CES alarms, AOM dashboards)
- [ ] Configure logging (LTS)
- [ ] Set up backup policies
- [ ] Configure DR/HA
- [ ] Update DNS records
- [ ] Run end-to-end tests
- [ ] Decommission AWS resources (after verification)

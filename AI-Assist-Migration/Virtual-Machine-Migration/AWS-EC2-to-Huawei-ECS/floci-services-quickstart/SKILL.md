---
name: floci-services-quickstart
description: Quick reference for all 69 floci AWS services with CRUD examples for the 15 most used. Use when working with floci services, looking up service availability, or needing quick command examples.
---

# Floci Services Quickstart

Quick reference for all 69 AWS services emulated by floci, with working CRUD examples for the 15 most used.

## Prerequisites

- Floci running (`floci start && floci wait`)
- AWS CLI configured (`endpoint_url=http://localhost:4566`, creds `test/test`)
- See `floci-aws-mcp-setup` skill for initial setup

## All 69 Services

### In-process (emulated in Java/Quarkus)

| Service | CLI | Status | Notes |
|---------|-----|--------|-------|
| S3 | `s3api` | running | Object storage |
| DynamoDB | `dynamodb` | running | NoSQL |
| SQS | `sqs` | running | Message queue |
| SNS | `sns` | running | Pub/sub |
| IAM | `iam` | running | No validation, any ARN accepted |
| KMS | `kms` | running | Key management |
| SecretsManager | `secretsmanager` | running | Secrets |
| Step Functions | `stepfunctions` | running | State machines |
| CloudFormation | `cloudformation` | running | IaC |
| Route53 | `route53` | running | DNS |
| API Gateway | `apigateway` | running | REST API |
| API Gateway v2 | `apigatewayv2` | running | HTTP API |
| CloudWatch | `cloudwatch` | running | Alarms |
| CloudWatch Logs | `logs` | running | Log groups |
| EventBridge | `events` | running | Event bus |
| Scheduler | `scheduler` | running | Scheduled rules |
| SSM | `ssm` | running | Parameter store |
| AppConfig | `appconfig` | running | Feature flags |
| ACM | `acm` | running | Certificates |
| WAFv2 | `wafv2` | running | Web ACL |
| Cognito | `cognito-idp` | running | User pools |
| Kinesis | `kinesis` | running | Streams |
| Firehose | `firehose` | running | Delivery streams |
| SES | `ses` | running | Email |
| Athena | `athena` | running | SQL (DuckDB sidecar) |
| Glue | `glue` | running | Data catalog |
| EMR | `elasticmapreduce` | running | Clusters |
| CloudTrail | `cloudtrail` | running | Audit |
| Config | `configservice` | running | Compliance |
| CloudFront | `cloudfront` | running | CDN |
| AppSync | `appsync` | running | GraphQL |
| Transfer | `transfer` | running | SFTP |
| Lightsail | `lightsail` | running | VPS |
| Backup | `backup` | running | Backups |
| Pricing | `pricing` | running | Price list |
| Cost Explorer | `ce` | running | Cost analysis |
| CUR | `cur` | running | Cost report |
| BCM | `bcm-data-exports` | running | Billing |
| Textract | `textract` | running | OCR |
| Transcribe | `transcribe` | running | Speech-to-text |
| S3 Vectors | `s3vectors` | running | Vector store |
| Cloud Map | `servicediscovery` | running | Service discovery |
| Tagging | `tagging` | running | Resource tags |
| Pipes | `pipes` | running | Event pipes |
| Batch | `batch` | running | Batch jobs |

### Docker-backed (real containers)

| Service | CLI | Status | Container |
|---------|-----|--------|-----------|
| Lambda | `lambda` | running | Docker per function |
| RDS | `rds` | running | Postgres/MySQL/MariaDB |
| ElastiCache | `elasticache` | running | Valkey/Redis |
| Neptune | `neptune` | running | Gremlin/Neo4j |
| DocumentDB | `docdb` | running | MongoDB |
| MSK | `kafka` | running | Redpanda/Kafka |
| Amazon MQ | `mq` | running | RabbitMQ |
| ECS | `ecs` | running | Docker tasks |
| EC2 | `ec2` | running | Limited (metadata only) |
| EKS | `eks` | running | k3s cluster |
| ECR | `ecr` | running | registry:2 |
| CodeBuild | `codebuild` | running | Build containers |
| OpenSearch | `es` | running | Search cluster |
| Bedrock | `bedrock-runtime` | **404** | Not implemented |

### Verify all services

```bash
curl -s http://localhost:4566/_localstack/health | python3 -m json.tool
```

---

## S3 — Object Storage

```bash
# Create bucket
aws s3 mb s3://my-bucket

# Upload file
echo "hello" > /tmp/test.txt
aws s3 cp /tmp/test.txt s3://my-bucket/test.txt

# List
aws s3 ls s3://my-bucket/
aws s3api list-objects-v2 --bucket my-bucket

# Download
aws s3 cp s3://my-bucket/test.txt /tmp/downloaded.txt

# Delete
aws s3 rm s3://my-bucket/test.txt
aws s3 rb s3://my-bucket
```

### MCP equivalent
```
aws_aws_call(service="s3api", operation="create-bucket", params={Bucket: "my-bucket"})
aws_aws_call(service="s3api", operation="list-buckets")
```

## DynamoDB — NoSQL

```bash
# Create table
aws dynamodb create-table \
  --table-name Users \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# Put item
aws dynamodb put-item \
  --table-name Users \
  --item '{"id": {"S": "1"}, "name": {"S": "Alice"}, "age": {"N": "30"}}'

# Get item
aws dynamodb get-item \
  --table-name Users \
  --key '{"id": {"S": "1"}}'

# Scan
aws dynamodb scan --table-name Users

# Query
aws dynamodb query \
  --table-name Users \
  --key-condition-expression 'id = :id' \
  --expression-attribute-values '{":id": {"S": "1"}}'

# Delete
aws dynamodb delete-item --table-name Users --key '{"id": {"S": "1"}}'
aws dynamodb delete-table --table-name Users
```

## SQS — Message Queue

```bash
# Create queue
aws sqs create-queue --queue-name my-queue

# Send message
aws sqs send-message \
  --queue-url http://localhost:4566/000000000000/my-queue \
  --message-body '{"action": "process", "data": "hello"}'

# Receive
aws sqs receive-message \
  --queue-url http://localhost:4566/000000000000/my-queue \
  --max-number-of-messages 5

# Delete message (after processing)
aws sqs delete-message \
  --queue-url http://localhost:4566/000000000000/my-queue \
  --receipt-handle <HANDLE>

# Delete queue
aws sqs delete-queue --queue-url http://localhost:4566/000000000000/my-queue
```

## SNS — Pub/Sub

```bash
# Create topic
aws sns create-topic --name my-topic

# Subscribe (SQS endpoint)
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:000000000000:my-topic \
  --protocol sqs \
  --notification-endpoint http://localhost:4566/000000000000/my-queue

# Publish
aws sns publish \
  --topic-arn arn:aws:sns:us-east-1:000000000000:my-topic \
  --message "Hello from SNS"

# Delete
aws sns delete-topic --topic-arn arn:aws:sns:us-east-1:000000000000:my-topic
```

## IAM — Identity & Access

```bash
# Create user
aws iam create-user --user-name app-user

# Create role
cat > /tmp/trust.json << 'EOF'
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}
EOF
aws iam create-role --role-name lambda-role --assume-role-policy-document file:///tmp/trust.json

# Attach policy
aws iam attach-role-policy --role-name lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AWSLambdaBasicExecutionRole

# List
aws iam list-users
aws iam list-roles --query 'Roles[].RoleName'
aws iam list-attached-role-policies --role-name lambda-role

# Delete
aws iam detach-role-policy --role-name lambda-role \
  --policy-arn arn:aws:iam::aws:policy/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name lambda-role
aws iam delete-user --user-name app-user
```

## KMS — Key Management

```bash
# Create key
aws kms create-key --description "my-test-key"

# List keys
aws kms list-keys

# Encrypt
aws kms encrypt \
  --key-id <KEY_ID> \
  --plaintext "secret data" \
  --query CiphertextBlob --output text

# Decrypt
aws kms decrypt \
  --ciphertext-blob <CIPHERTEXT> \
  --query Plaintext --output text

# Delete (schedule)
aws kms schedule-key-deletion --key-id <KEY_ID> --pending-window-in-days 7
```

## Secrets Manager

```bash
# Create secret
aws secretsmanager create-secret \
  --name my-secret \
  --secret-string '{"username":"admin","password":"s3cret"}'

# Get secret
aws secretsmanager get-secret-value --secret-id my-secret

# List
aws secretsmanager list-secrets

# Delete
aws secretsmanager delete-secret --secret-id my-secret --force-delete-without-recovery
```

## Step Functions

```bash
# Create state machine
cat > /tmp/asm.json << 'EOF'
{"Comment":"Hello World","StartAt":"Pass","States":{"Pass":{"Type":"Pass","End":true}}}
EOF

aws stepfunctions create-state-machine \
  --name my-statemachine \
  --definition file:///tmp/asm.json \
  --role-arn arn:aws:iam::000000000000:role/lambda-role

# Start execution
aws stepfunctions start-execution \
  --state-machine-arn arn:aws:states:us-east-1:000000000000:stateMachine:my-statemachine

# List
aws stepfunctions list-state-machines

# Delete
aws stepfunctions delete-state-machine \
  --state-machine-arn arn:aws:states:us-east-1:000000000000:stateMachine:my-statemachine
```

## Route53 — DNS

```bash
# Create hosted zone
aws route53 create-hosted-zone --name example.com --caller-reference $(date +%s)

# List zones
aws route53 list-hosted-zones

# Create record
aws route53 change-resource-record-sets \
  --hosted-zone-id <ZONE_ID> \
  --change-batch '{"Changes":[{"Action":"CREATE","ResourceRecordSet":{"Name":"www.example.com","Type":"A","TTL":300,"ResourceRecords":[{"Value":"1.2.3.4"}]}}]}'

# Delete zone
aws route53 delete-hosted-zone --id <ZONE_ID>
```

## API Gateway

```bash
# Create REST API
aws apigateway create-rest-api --name my-api

# Get root resource
aws apigateway get-resources --rest-api-id <API_ID> --query 'items[?path==`/`].id' --output text

# Create resource
aws apigateway create-resource \
  --rest-api-id <API_ID> \
  --parent-id <ROOT_ID> \
  --path-part hello

# List APIs
aws apigateway get-rest-apis

# Delete
aws apigateway delete-rest-api --rest-api-id <API_ID>
```

## CloudFormation

```bash
# Create stack
cat > /tmp/template.yaml << 'EOF'
Resources:
  MyBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: cf-test-bucket
EOF

aws cloudformation create-stack \
  --stack-name my-stack \
  --template-body file:///tmp/template.yaml

# Wait
aws cloudformation describe-stacks --stack-name my-stack --query 'Stacks[].StackStatus'

# Delete
aws cloudformation delete-stack --stack-name my-stack
```

## ECR — Container Registry

```bash
# Create repository
aws ecr create-repository --repository-name my-repo

# List
aws ecr describe-repositories

# Get login (floci ECR at localhost:5100)
aws ecr get-login-password | docker login localhost:5100 -u AWS --password-stdin

# Push image
docker tag my-image:latest localhost:5100/my-repo:latest
docker push localhost:5100/my-repo:latest

# Delete
aws ecr delete-repository --repository-name my-repo --force
```

## ECS — Container Orchestration

```bash
# Create cluster
aws ecs create-cluster --cluster-name my-ecs-cluster

# Register task definition
aws ecs register-task-definition \
  --family my-task \
  --container-definitions '[{"name":"nginx","image":"nginx","memory":256,"cpu":128}]'

# Run task
aws ecs run-task \
  --cluster my-ecs-cluster \
  --task-definition my-task

# List
aws ecs list-clusters
aws ecs list-task-definitions

# Delete
aws ecs delete-cluster --cluster-name my-ecs-cluster
aws ecs deregister-task-definition --task-definition my-task:1
```

## CloudWatch

```bash
# Create alarm
aws cloudwatch put-metric-alarm \
  --alarm-name my-alarm \
  --metric-name CPUUtilization \
  --namespace AWS/EC2 \
  --statistic Average \
  --period 60 \
  --evaluation-periods 1 \
  --threshold 80 \
  --comparison-operator GreaterThanThreshold

# List
aws cloudwatch describe-alarms

# Put metric
aws cloudwatch put-metric-data \
  --namespace MyApp \
  --metric-data MetricName=Requests,Value=100,Unit=Count

# Delete
aws cloudwatch delete-alarms --alarm-names my-alarm
```

## Clean Up Everything

```bash
# S3
for b in $(aws s3 ls | awk '{print $3}'); do aws s3 rb s3://$b --force; done

# DynamoDB
for t in $(aws dynamodb list-tables --query 'TableNames' --output text); do \
  aws dynamodb delete-table --table-name $t; done

# SQS
for q in $(aws sqs list-queues --query 'QueueUrls' --output text); do \
  aws sqs delete-queue --queue-url $q; done

# SNS
for t in $(aws sns list-topics --query 'Topics[].TopicArn' --output text); do \
  aws sns delete-topic --topic-arn $t; done

# CloudFormation
for s in $(aws cloudformation list-stacks --query 'StackSummaries[].StackName' --output text); do \
  aws cloudformation delete-stack --stack-name $s; done

# Lambda
for f in $(aws lambda list-functions --query 'Functions[].FunctionName' --output text); do \
  aws lambda delete-function --function-name $f; done
```

## MCP vs CLI Quick Reference

| Task | CLI | MCP |
|------|-----|-----|
| List S3 buckets | `aws s3api list-buckets` | `aws_aws_call(service="s3api", operation="list-buckets")` |
| List DynamoDB tables | `aws dynamodb list-tables` | `aws_aws_call(service="dynamodb", operation="list-tables")` |
| List Lambda functions | `aws lambda list-functions` | `aws_aws_call(service="lambda", operation="list-functions")` |
| List IAM roles | `aws iam list-roles` | `aws_aws_call(service="iam", operation="list-roles")` |
| List EKS clusters | `aws eks list-clusters` | `aws_aws_call(service="eks", operation="list-clusters")` |
| List all S3 buckets (CCAPI) | — | `aws_aws_resource_list(typeName="AWS::S3::Bucket")` |
| Get IAM role (CCAPI) | — | `aws_aws_resource_get(typeName="AWS::IAM::Role", identifier="my-role")` |

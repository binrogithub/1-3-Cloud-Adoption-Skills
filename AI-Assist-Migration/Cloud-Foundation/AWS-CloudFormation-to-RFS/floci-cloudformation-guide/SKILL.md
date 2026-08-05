---
name: floci-cloudformation-guide
description: Infrastructure as Code with CloudFormation on floci. Templates, stacks, drift detection, nested stacks, and cross-stack references. Use when learning IaC, testing CFN templates, or provisioning multi-resource stacks locally.
---

# CloudFormation on Floci

Deploy infrastructure as code with CloudFormation templates on floci. Learn IaC patterns without AWS costs.

## Prerequisites

- **Floci** running (`floci start && floci wait`)
- **AWS CLI** configured for floci

Verify:
```bash
aws cloudformation list-stacks  # Should return empty
```

## Template Anatomy

```yaml
# Template structure
AWSTemplateFormatVersion: '2010-09-09'
Description: My stack description

Parameters:          # Input values (prompted or passed)
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, prod]

Mappings:            # Static lookup tables
  RegionMap:
    us-east-1:
      AMI: ami-12345678

Conditions:          # Conditional logic
  IsProd: !Equals [!Ref Environment, prod]

Resources:           # The actual infrastructure (REQUIRED)
  MyBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub "my-bucket-${Environment}"

Outputs:             # Exported values for cross-stack references
  BucketName:
    Value: !Ref MyBucket
    Export:
      Name: MyBucketName
```

## Step 1: Simple Stack (S3 + DynamoDB)

```bash
cat > /tmp/simple-stack.yaml << 'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Description: Simple stack with S3 and DynamoDB

Resources:
  MyBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: cfn-simple-bucket

  MyTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: cfn-simple-table
      AttributeDefinitions:
        - AttributeName: id
          AttributeType: S
      KeySchema:
        - AttributeName: id
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST

Outputs:
  BucketName:
    Value: !Ref MyBucket
  TableName:
    Value: !Ref MyTable
EOF

aws cloudformation create-stack \
  --stack-name simple-stack \
  --template-body file:///tmp/simple-stack.yaml
```

### Wait for completion

```bash
while true; do
  STATUS=$(aws cloudformation describe-stacks --stack-name simple-stack \
    --query 'Stacks[].StackStatus' --output text)
  echo "Status: $STATUS"
  [[ "$STATUS" == "CREATE_COMPLETE" ]] && break
  [[ "$STATUS" == *"FAIL"* ]] && break
  sleep 2
done
```

### Verify resources

```bash
aws s3 ls | grep cfn-simple
aws dynamodb describe-table --table-name cfn-simple-table --query 'Table.TableName'
```

## Step 2: Stack with Parameters

```bash
cat > /tmp/param-stack.yaml << 'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Description: Stack with parameters

Parameters:
  BucketName:
    Type: String
    Description: Name for the S3 bucket
  Environment:
    Type: String
    Default: dev
    AllowedValues: [dev, staging, prod]

Resources:
  MyBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Ref BucketName
      Tags:
        - Key: Environment
          Value: !Ref Environment

Outputs:
  BucketArn:
    Value: !GetAtt MyBucket.Arn
EOF

aws cloudformation create-stack \
  --stack-name param-stack \
  --template-body file:///tmp/param-stack.yaml \
  --parameters ParameterKey=BucketName,ParameterValue=my-param-bucket \
               ParameterKey=Environment,ParameterValue=prod
```

## Step 3: Update Stack

```bash
# Change a parameter
aws cloudformation update-stack \
  --stack-name param-stack \
  --template-body file:///tmp/param-stack.yaml \
  --parameters ParameterKey=BucketName,ParameterValue=my-param-bucket \
               ParameterKey=Environment,ParameterValue=staging
```

## Step 4: Cross-Stack References

### Stack 1: Network (exports values)

```bash
cat > /tmp/network-stack.yaml << 'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Resources:
  MyBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: cfn-network-bucket
Outputs:
  BucketName:
    Value: !Ref MyBucket
    Export:
      Name: NetworkBucketName
EOF

aws cloudformation create-stack \
  --stack-name network-stack \
  --template-body file:///tmp/network-stack.yaml
```

### Stack 2: App (imports from network)

```bash
cat > /tmp/app-stack.yaml << 'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Resources:
  MyTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !ImportValue NetworkBucketName
      AttributeDefinitions:
        - AttributeName: id
          AttributeType: S
      KeySchema:
        - AttributeName: id
          KeyType: HASH
      BillingMode: PAY_PER_REQUEST
EOF

aws cloudformation create-stack \
  --stack-name app-stack \
  --template-body file:///tmp/app-stack.yaml
```

## Step 5: Nested Stacks

```bash
cat > /tmp/nested-stack.yaml << 'EOF'
AWSTemplateFormatVersion: '2010-09-09'
Resources:
  BucketStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: https://cfn-templates.s3.amazonaws.com/bucket.yaml
  TableStack:
    Type: AWS::CloudFormation::Stack
    Properties:
      TemplateURL: https://cfn-templates.s3.amazonaws.com/table.yaml
EOF
```

Note: Nested stacks require TemplateURL (S3-hosted). For floci, upload templates to S3 first.

## Step 6: Drift Detection

```bash
# Detect drift
aws cloudformation detect-stack-drift --stack-name simple-stack

# Check drift status
aws cloudformation describe-stack-drift-detection-status \
  --stack-drift-detection-id <DETECTION_ID>

# Get drift details
aws cloudformation describe-stack-resource-drifts \
  --stack-name simple-stack
```

## Step 7: Stack Outputs

```bash
# Get all outputs
aws cloudformation describe-stacks \
  --stack-name simple-stack \
  --query 'Stacks[].Outputs'

# Get specific output
aws cloudformation describe-stacks \
  --stack-name simple-stack \
  --query 'Stacks[].Outputs[?OutputKey==`BucketName`].OutputValue' \
  --output text
```

## Step 8: Change Sets (Preview Changes)

```bash
# Create change set
aws cloudformation create-change-set \
  --stack-name simple-stack \
  --change-set-name my-change \
  --change-type UPDATE \
  --template-body file:///tmp/simple-stack.yaml

# Preview changes
aws cloudformation describe-change-set \
  --stack-name simple-stack \
  --change-set-name my-change

# Execute (apply changes)
aws cloudformation execute-change-set \
  --stack-name simple-stack \
  --change-set-name my-change

# Or reject
aws cloudformation delete-change-set \
  --stack-name simple-stack \
  --change-set-name my-change
```

## Common Resource Types

| Type | AWS Service | Example |
|------|-------------|---------|
| `AWS::S3::Bucket` | S3 | Object storage |
| `AWS::DynamoDB::Table` | DynamoDB | NoSQL table |
| `AWS::SQS::Queue` | SQS | Message queue |
| `AWS::SNS::Topic` | SNS | Pub/sub topic |
| `AWS::Lambda::Function` | Lambda | Serverless function |
| `AWS::IAM::Role` | IAM | IAM role |
| `AWS::IAM::Policy` | IAM | IAM policy |
| `AWS::KMS::Key` | KMS | Encryption key |
| `AWS::SecretsManager::Secret` | Secrets Manager | Secret |
| `AWS::StepFunctions::StateMachine` | Step Functions | State machine |
| `AWS::ApiGateway::RestApi` | API Gateway | REST API |
| `AWS::CloudWatch::Alarm` | CloudWatch | Metric alarm |
| `AWS::Route53::HostedZone` | Route53 | DNS zone |
| `AWS::EC2::SecurityGroup` | EC2 | Security group |
| `AWS::RDS::DBInstance` | RDS | Database |

## Intrinsic Functions Reference

| Function | Syntax | Purpose |
|----------|--------|---------|
| `Ref` | `!Ref MyResource` | Get resource ID or parameter value |
| `GetAtt` | `!GetAtt MyBucket.Arn` | Get resource attribute |
| `Sub` | `!Sub "prefix-${Var}"` | String substitution |
| `Join` | `!Join [",", [a, b, c]]` | Join strings |
| `Select` | `!Select [0, [a, b]]` | Select from list |
| `Split` | `!Split [",", "a,b,c"]` | Split string |
| `ImportValue` | `!ImportValue ExportName` | Cross-stack import |
| `Equals` | `!Equals [!Ref Env, prod]` | Condition equality |
| `If` | `!If [IsProd, value1, value2]` | Conditional value |
| `Map` | `!FindInMap [RegionMap, !Ref AWS::Region, AMI]` | Lookup in mappings |

## Floci CFN Quirks vs Real AWS

| Aspect | Real AWS | Floci |
|--------|----------|-------|
| Stack creation | 1-30 min | ~1-5 seconds |
| Drift detection | Real comparison | API only (may not detect all drift) |
| Nested stacks | TemplateURL from S3 | Same (upload to floci S3 first) |
| Custom resources | Lambda-backed | Works if Lambda is set up |
| Rollback | Automatic on failure | Automatic |
| Change sets | Full preview | Works |
| Deletion policy | Retain/Snapshot/Delete | Works |

## Troubleshooting

### Stack stuck in CREATE_IN_PROGRESS

**Cause**: Resource creation takes time (Docker-backed services like Lambda/RDS).

**Fix**: Wait and check events:
```bash
aws cloudformation describe-stack-events --stack-name my-stack --max-items 5
```

### Stack creation failed

**Cause**: Invalid template, missing dependencies, or resource conflict.

**Fix**: Check events and rollback:
```bash
aws cloudformation describe-stack-events --stack-name my-stack
aws cloudformation delete-stack --stack-name my-stack  # Clean up failed stack
```

### Template validation error

```bash
aws cloudformation validate-template --template-body file:///tmp/my-stack.yaml
```

### Cross-stack import fails

**Cause**: Export name doesn't exist or exporting stack was deleted.

**Fix**: Verify export exists:
```bash
aws cloudformation list-exports --query 'Exports[?Name==`NetworkBucketName`]'
```

## Clean Up

```bash
# Delete all stacks
for s in $(aws cloudformation list-stacks \
  --query 'StackSummaries[?StackStatus!=`DELETE_COMPLETE`].StackName' \
  --output text); do
  aws cloudformation delete-stack --stack-name $s
done

# Clean temp files
rm -f /tmp/simple-stack.yaml /tmp/param-stack.yaml /tmp/network-stack.yaml /tmp/app-stack.yaml /tmp/nested-stack.yaml
```

## Quick Reference

### Commands

| Command | Purpose |
|---------|---------|
| `aws cloudformation list-stacks` | List all stacks |
| `aws cloudformation describe-stacks --stack-name X` | Stack details + outputs |
| `aws cloudformation create-stack --stack-name X --template-body file://T` | Create stack |
| `aws cloudformation update-stack --stack-name X --template-body file://T` | Update stack |
| `aws cloudformation delete-stack --stack-name X` | Delete stack |
| `aws cloudformation validate-template --template-body file://T` | Validate template |
| `aws cloudformation describe-stack-events --stack-name X` | Stack events |
| `aws cloudformation list-exports` | All exported values |
| `aws cloudformation create-change-set ...` | Preview changes |
| `aws cloudformation detect-stack-drift --stack-name X` | Detect drift |

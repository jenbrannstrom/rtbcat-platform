# Cat Scan CloudFormation Deployment

**Status:** ⚠️ **DRAFT / OUTLINE** - This template is not yet complete or tested.

## Overview

This CloudFormation template automates the deployment of Cat Scan to your AWS account, creating:

- **ECR Repositories** for Docker images (fake_bidder, fake_ssp, cat_scan)
- **ECS Cluster** (Fargate) for running containers
- **Task Definitions** for each service
- **EventBridge Rule** for scheduled Cat Scan analysis runs
- **IAM Roles** with appropriate S3 permissions
- **CloudWatch Log Groups** for container logs
- **S3 Bucket** for Cat Scan reports (optional)

## Prerequisites

Before deploying this stack, ensure you have:

1. **AWS CLI configured** with appropriate credentials
2. **An S3 bucket** with RTB logs (or use fake_ssp to generate logs)
3. **Docker images** built and pushed to ECR (see deployment steps below)
4. **VPC and subnets** (or let the template create them - TODO: add VPC creation)

## Deployment Steps

### 1. Build and Push Docker Images

```bash
# Navigate to project root
cd ~/Documents/fabric-module-1

# Authenticate to ECR
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-west-1.amazonaws.com

# Build images
docker build -t cat-scan/fake-bidder -f fake_bidder/Dockerfile .
docker build -t cat-scan/fake-ssp -f fake_ssp/Dockerfile .
docker build -t cat-scan/cat-scan -f cat_scan/Dockerfile .

# Tag images
docker tag cat-scan/fake-bidder:latest <account-id>.dkr.ecr.eu-west-1.amazonaws.com/cat-scan/fake-bidder:latest
docker tag cat-scan/fake-ssp:latest <account-id>.dkr.ecr.eu-west-1.amazonaws.com/cat-scan/fake-ssp:latest
docker tag cat-scan/cat-scan:latest <account-id>.dkr.ecr.eu-west-1.amazonaws.com/cat-scan/cat-scan:latest

# Push images
docker push <account-id>.dkr.ecr.eu-west-1.amazonaws.com/cat-scan/fake-bidder:latest
docker push <account-id>.dkr.ecr.eu-west-1.amazonaws.com/cat-scan/fake-ssp:latest
docker push <account-id>.dkr.ecr.eu-west-1.amazonaws.com/cat-scan/cat-scan:latest
```

### 2. Deploy CloudFormation Stack

```bash
aws cloudformation create-stack \
  --stack-name cat-scan \
  --template-body file://infra/cloudformation/cat-scan-stack.yaml \
  --parameters \
    ParameterKey=LogBucketName,ParameterValue=my-rtb-logs-bucket \
    ParameterKey=LogPrefix,ParameterValue=rtb-logs/ \
    ParameterKey=ReportBucketName,ParameterValue=cat-scan-reports-unique-name \
    ParameterKey=ScheduleExpression,ParameterValue="rate(1 hour)" \
    ParameterKey=SubnetIds,ParameterValue="subnet-abc123,subnet-def456" \
  --capabilities CAPABILITY_NAMED_IAM \
  --region eu-west-1
```

### 3. Monitor Stack Creation

```bash
# Watch stack events
aws cloudformation describe-stack-events \
  --stack-name cat-scan \
  --region eu-west-1 \
  --query 'StackEvents[*].[Timestamp,ResourceStatus,ResourceType,LogicalResourceId]' \
  --output table

# Get stack status
aws cloudformation describe-stacks \
  --stack-name cat-scan \
  --region eu-west-1 \
  --query 'Stacks[0].StackStatus'
```

### 4. View Reports

After the scheduled task runs, reports will be available in:

- S3 Console: `s3://your-report-bucket-name/`
- Static Website (if enabled): Check stack outputs for `ReportBucketWebsiteURL`

```bash
# Get report bucket website URL
aws cloudformation describe-stacks \
  --stack-name cat-scan \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`ReportBucketWebsiteURL`].OutputValue' \
  --output text
```

## Quick Create Link (Future)

Once the template is finalized and uploaded to a public S3 bucket, users will be able to deploy with one click:

```
https://console.aws.amazon.com/cloudformation/home?region=eu-west-1#/stacks/create/review
  ?stackName=cat-scan
  &templateURL=https://s3.amazonaws.com/cat-scan-public-templates/cat-scan-stack.yaml
```

## Parameters

| Parameter | Description | Default | Required |
|-----------|-------------|---------|----------|
| `LogBucketName` | S3 bucket with RTB logs | - | Yes |
| `LogPrefix` | S3 prefix for log files | - | No |
| `ReportBucketName` | S3 bucket for reports (created if new) | - | Yes |
| `ScheduleExpression` | EventBridge schedule expression | `rate(1 hour)` | No |
| `VpcId` | VPC ID for ECS tasks | - | No (TODO) |
| `SubnetIds` | Comma-separated subnet IDs | - | Yes (TODO: make optional) |

## Stack Outputs

| Output | Description |
|--------|-------------|
| `ECSClusterName` | Name of the ECS cluster |
| `CatScanECRRepository` | ECR URI for cat_scan image |
| `FakeBidderECRRepository` | ECR URI for fake_bidder image |
| `FakeSspECRRepository` | ECR URI for fake_ssp image |
| `ReportBucketName` | S3 bucket name for reports |
| `ReportBucketWebsiteURL` | Static website URL for reports |

## Troubleshooting

### Stack Creation Failed

Check CloudFormation Events tab in the AWS Console for specific errors:

```bash
aws cloudformation describe-stack-events \
  --stack-name cat-scan \
  --region eu-west-1 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
  --output table
```

Common issues:

- **InsufficientCapabilities**: Add `--capabilities CAPABILITY_NAMED_IAM` to the create-stack command
- **Image not found**: Ensure Docker images are pushed to ECR before deploying
- **Invalid subnet**: Check that subnet IDs are correct and in the same VPC

### Scheduled Task Not Running

Check EventBridge rule:

```bash
aws events describe-rule \
  --name cat-scan-cat-scan-schedule \
  --region eu-west-1
```

View ECS task failures:

```bash
aws ecs list-tasks \
  --cluster cat-scan-cluster \
  --desired-status STOPPED \
  --region eu-west-1
```

### No Reports Generated

Check CloudWatch Logs:

```bash
aws logs tail /ecs/cat-scan/cat-scan \
  --region eu-west-1 \
  --follow
```

Verify S3 permissions on the Cat Scan task role.

## Clean Up

To delete all resources:

```bash
# Delete stack
aws cloudformation delete-stack \
  --stack-name cat-scan \
  --region eu-west-1

# Wait for deletion
aws cloudformation wait stack-delete-complete \
  --stack-name cat-scan \
  --region eu-west-1

# Manually delete ECR images (if desired)
aws ecr batch-delete-image \
  --repository-name cat-scan/cat-scan \
  --image-ids imageTag=latest \
  --region eu-west-1
```

## TODO: Template Improvements

- [ ] Add VPC creation (conditional)
- [ ] Add Security Groups
- [ ] Add support for existing ECR repositories
- [ ] Add S3 bucket policy for public reports (optional)
- [ ] Add CloudFront distribution for reports (optional)
- [ ] Add fake_bidder service (optional)
- [ ] Add fake_ssp scheduled runs (optional for testing)
- [ ] Test template end-to-end
- [ ] Add deployment script
- [ ] Upload template to public S3 for Quick Create links
- [ ] Create static landing page with deploy button

## Cost Estimate

Running this stack will incur AWS charges:

- **ECS Fargate** (scheduled tasks): ~$5-10/month for hourly runs
- **S3 storage**: $0.023/GB/month
- **CloudWatch Logs**: $0.50/GB ingested
- **Data transfer**: Minimal for small volumes

**Total estimated cost:** $10-20/month for development/testing workloads.

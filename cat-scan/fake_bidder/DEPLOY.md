# Deploying fake_bidder to AWS

## Prerequisites

- Docker installed locally
- AWS CLI configured with credentials for account `328614522524`
- Region: `eu-west-1`

## Infrastructure Created

The following AWS resources have been created:

- **ECR Repository**: `328614522524.dkr.ecr.eu-west-1.amazonaws.com/cat-scan/fake-bidder`
- **ECS Cluster**: `cat-scan`
- **Task Definition**: `fake-bidder:1`
- **Security Group**: `sg-0d094ee56eadfd756` (allows port 3000)
- **IAM Role**: `ecsTaskExecutionRole`

## Deployment Steps

### 1. Build and Push Docker Image

Run the deploy script from the project root:

```bash
cd ~/Documents/fabric-module-1
./fake_bidder/deploy.sh
```

Or manually:

```bash
# Login to ECR
aws ecr get-login-password --region eu-west-1 | docker login --username AWS --password-stdin 328614522524.dkr.ecr.eu-west-1.amazonaws.com

# Build image
docker build -t cat-scan/fake-bidder:latest -f fake_bidder/Dockerfile .

# Tag and push
docker tag cat-scan/fake-bidder:latest 328614522524.dkr.ecr.eu-west-1.amazonaws.com/cat-scan/fake-bidder:latest
docker push 328614522524.dkr.ecr.eu-west-1.amazonaws.com/cat-scan/fake-bidder:latest
```

### 2. Run the Task (On-Demand)

For cost-effective testing, run tasks on-demand instead of a persistent service:

```bash
# Run a single task (stops when you're done)
aws ecs run-task \
  --cluster cat-scan \
  --task-definition fake-bidder:1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-04fa47811080e3b52],securityGroups=[sg-0d094ee56eadfd756],assignPublicIp=ENABLED}" \
  --region eu-west-1
```

To stop the task when done:

```bash
# List running tasks
aws ecs list-tasks --cluster cat-scan --region eu-west-1

# Stop a task
aws ecs stop-task --cluster cat-scan --task <TASK_ARN> --region eu-west-1
```

### Alternative: Persistent Service (24/7)

If you need the bidder running continuously:

```bash
aws ecs create-service \
  --cluster cat-scan \
  --service-name fake-bidder \
  --task-definition fake-bidder:1 \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-04fa47811080e3b52],securityGroups=[sg-0d094ee56eadfd756],assignPublicIp=ENABLED}" \
  --region eu-west-1
```

**Note:** A persistent Fargate service costs ~$10-15/month for the minimum config (256 CPU, 512 MB).

### 3. Get the Public IP

After the service starts, get the task's public IP:

```bash
# Get task ARN
TASK_ARN=$(aws ecs list-tasks --cluster cat-scan --service-name fake-bidder --region eu-west-1 --query 'taskArns[0]' --output text)

# Get ENI ID
ENI_ID=$(aws ecs describe-tasks --cluster cat-scan --tasks $TASK_ARN --region eu-west-1 --query 'tasks[0].attachments[0].details[?name==`networkInterfaceId`].value' --output text)

# Get public IP
aws ec2 describe-network-interfaces --network-interface-ids $ENI_ID --region eu-west-1 --query 'NetworkInterfaces[0].Association.PublicIp' --output text
```

### 4. Test the Service

```bash
curl -X POST http://<PUBLIC_IP>:3000/bid \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test-1",
    "imp": [{
      "id": "1",
      "banner": {"w": 300, "h": 250},
      "bidfloor": 0.5
    }]
  }'
```

## Monitoring

View logs in CloudWatch:
- Log group: `/ecs/fake-bidder`
- Log stream prefix: `ecs`

```bash
aws logs tail /ecs/fake-bidder --region eu-west-1 --follow
```

## Cleanup

To delete all resources:

```bash
# Stop and delete service
aws ecs update-service --cluster cat-scan --service fake-bidder --desired-count 0 --region eu-west-1
aws ecs delete-service --cluster cat-scan --service fake-bidder --region eu-west-1

# Delete cluster
aws ecs delete-cluster --cluster cat-scan --region eu-west-1

# Delete ECR repository
aws ecr delete-repository --repository-name cat-scan/fake-bidder --force --region eu-west-1

# Delete security group
aws ec2 delete-security-group --group-id sg-0d094ee56eadfd756 --region eu-west-1

# Delete IAM role
aws iam detach-role-policy --role-name ecsTaskExecutionRole --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
aws iam delete-role --role-name ecsTaskExecutionRole
```

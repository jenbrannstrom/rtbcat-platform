#!/bin/bash
set -e

# Configuration
AWS_REGION="eu-west-1"
AWS_ACCOUNT_ID="328614522524"
ECR_REPO="cat-scan/fake-bidder"
IMAGE_TAG="latest"

echo "=== Deploying fake_bidder to AWS ==="

# Login to ECR
echo "Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Build the Docker image
echo "Building Docker image..."
cd "$(dirname "$0")/.."
docker build -t $ECR_REPO:$IMAGE_TAG -f fake_bidder/Dockerfile .

# Tag and push
echo "Pushing to ECR..."
docker tag $ECR_REPO:$IMAGE_TAG $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG

echo "=== Image pushed successfully ==="
echo "Image URI: $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:$IMAGE_TAG"

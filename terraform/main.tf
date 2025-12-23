# Cat-Scan AWS Infrastructure
# One-click deployment for Cat-Scan QPS Optimizer

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Get latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# VPC - Use default VPC for simplicity
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Security Group
resource "aws_security_group" "catscan" {
  name        = "${var.app_name}-${var.environment}-sg"
  description = "Security group for Cat-Scan application"
  vpc_id      = data.aws_vpc.default.id

  # Dashboard (Next.js)
  ingress {
    description = "Dashboard UI"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # API (FastAPI)
  ingress {
    description = "API"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # SSH (optional, for debugging)
  dynamic "ingress" {
    for_each = var.ssh_key_name != "" ? [1] : []
    content {
      description = "SSH"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = [var.allowed_ssh_cidr]
    }
  }

  # Outbound - allow all
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name        = "${var.app_name}-${var.environment}-sg"
    Environment = var.environment
    Application = var.app_name
  }
}

# IAM Role for EC2 (for S3 access, CloudWatch logs)
resource "aws_iam_role" "catscan" {
  name = "${var.app_name}-${var.environment}-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name        = "${var.app_name}-${var.environment}-role"
    Environment = var.environment
  }
}

# S3 policy for CSV archival
resource "aws_iam_role_policy" "s3_access" {
  name = "${var.app_name}-s3-access"
  role = aws_iam_role.catscan.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.catscan.arn,
          "${aws_s3_bucket.catscan.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "catscan" {
  name = "${var.app_name}-${var.environment}-profile"
  role = aws_iam_role.catscan.name
}

# S3 Bucket for CSV archival
resource "aws_s3_bucket" "catscan" {
  bucket = "${var.app_name}-${var.environment}-data-${random_id.bucket_suffix.hex}"

  tags = {
    Name        = "${var.app_name}-${var.environment}-data"
    Environment = var.environment
    Application = var.app_name
  }
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket_versioning" "catscan" {
  bucket = aws_s3_bucket.catscan.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "catscan" {
  bucket = aws_s3_bucket.catscan.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# Block public access to S3 bucket
resource "aws_s3_bucket_public_access_block" "catscan" {
  bucket = aws_s3_bucket.catscan.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# EC2 Instance
resource "aws_instance" "catscan" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  key_name               = var.ssh_key_name != "" ? var.ssh_key_name : null
  vpc_security_group_ids = [aws_security_group.catscan.id]
  iam_instance_profile   = aws_iam_instance_profile.catscan.name
  subnet_id              = data.aws_subnets.default.ids[0]

  root_block_device {
    volume_size           = 30 # GB (minimum for Amazon Linux 2023)
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = true
  }

  user_data = base64encode(templatefile("${path.module}/user_data.sh", {
    s3_bucket   = aws_s3_bucket.catscan.id
    environment = var.environment
  }))

  tags = {
    Name        = "${var.app_name}-${var.environment}"
    Environment = var.environment
    Application = var.app_name
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Elastic IP for stable address
resource "aws_eip" "catscan" {
  instance = aws_instance.catscan.id
  domain   = "vpc"

  tags = {
    Name        = "${var.app_name}-${var.environment}-eip"
    Environment = var.environment
  }
}

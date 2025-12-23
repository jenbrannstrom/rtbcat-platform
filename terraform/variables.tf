# Cat-Scan Terraform Variables

variable "aws_region" {
  description = "AWS region to deploy to"
  type        = string
  default     = "eu-central-1" # Frankfurt - GDPR compliant
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.small" # 2GB RAM, 2 vCPU - sufficient for API + Dashboard
}

variable "environment" {
  description = "Environment name (e.g., production, staging)"
  type        = string
  default     = "production"
}

variable "app_name" {
  description = "Application name for resource naming"
  type        = string
  default     = "catscan"
}

variable "ssh_key_name" {
  description = "Name of existing EC2 key pair for SSH access"
  type        = string
  default     = "" # Optional - leave empty to disable SSH
}

variable "allowed_ssh_cidr" {
  description = "CIDR block allowed to SSH (your IP)"
  type        = string
  default     = "0.0.0.0/0" # Restrict this in production!
}

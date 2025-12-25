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

variable "domain_name" {
  description = "Domain name for HTTPS (e.g., catscan.example.com). Leave empty for HTTP-only mode."
  type        = string
  default     = ""
}

variable "enable_https" {
  description = "Enable HTTPS with Caddy reverse proxy. Requires domain_name to be set."
  type        = bool
  default     = false
}

# Cloudflare DNS Configuration
variable "cloudflare_api_token" {
  description = "Cloudflare API token with DNS edit permissions. Leave empty to skip DNS automation."
  type        = string
  default     = ""
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare Zone ID for your domain (find in dashboard overview page)."
  type        = string
  default     = ""
}

# Basic Auth for Dashboard
variable "basic_auth_user" {
  description = "Username for dashboard basic auth. Leave empty to disable."
  type        = string
  default     = ""
}

variable "basic_auth_password" {
  description = "Password for dashboard basic auth (will be hashed)."
  type        = string
  default     = ""
  sensitive   = true
}

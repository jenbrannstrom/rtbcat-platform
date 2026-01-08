# Cat-Scan GCP Infrastructure Variables
# Configure these in terraform.tfvars or via -var flags

variable "gcp_project" {
  description = "GCP Project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for resources"
  type        = string
  default     = "europe-west1"
}

variable "gcp_zone" {
  description = "GCP zone for the VM"
  type        = string
  default     = "europe-west1-b"
}

variable "app_name" {
  description = "Application name (used for resource naming)"
  type        = string
  default     = "catscan"
}

variable "environment" {
  description = "Environment (production, staging, dev)"
  type        = string
  default     = "production"
}

variable "machine_type" {
  description = "GCE machine type"
  type        = string
  default     = "e2-medium"
}

variable "boot_disk_size" {
  description = "Boot disk size in GB"
  type        = number
  default     = 30
}

variable "domain_name" {
  description = "Domain name for the application (e.g., scan.rtb.cat)"
  type        = string
  default     = ""
}

variable "enable_https" {
  description = "Enable HTTPS via Caddy (requires domain_name). When true, ports 3000/8000 are NOT exposed."
  type        = bool
  default     = true
}

variable "allowed_ssh_cidrs" {
  description = "CIDR blocks allowed for SSH access. Empty = no SSH access."
  type        = list(string)
  default     = []
}

variable "github_repo" {
  description = "GitHub repository URL for the application"
  type        = string
  default     = "https://github.com/jenbrannstrom/rtbcat-platform.git"
}

variable "github_branch" {
  description = "GitHub branch to deploy"
  type        = string
  default     = "unified-platform"
}

# Optional: Cloudflare integration
variable "cloudflare_api_token" {
  description = "Cloudflare API token for DNS management (optional)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare Zone ID for DNS records (optional)"
  type        = string
  default     = ""
}

# =============================================================================
# OAuth2 Proxy - Google Authentication (REQUIRED)
# =============================================================================
# All users must authenticate with Google before accessing the app.
# Create OAuth credentials at: https://console.cloud.google.com/apis/credentials

variable "google_oauth_client_id" {
  description = "Google OAuth Client ID (from GCP Console → APIs & Services → Credentials)"
  type        = string

  validation {
    condition     = can(regex("^[0-9]+-[a-z0-9]+\\.apps\\.googleusercontent\\.com$", var.google_oauth_client_id))
    error_message = "Google OAuth Client ID must be in format: 123456789-xxxxx.apps.googleusercontent.com"
  }
}

variable "google_oauth_client_secret" {
  description = "Google OAuth Client Secret"
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.google_oauth_client_secret) > 10
    error_message = "Google OAuth Client Secret must not be empty"
  }
}

variable "allowed_email_domains" {
  description = "Email domains allowed to access (e.g., ['rtb.cat', 'company.com']). Empty list = any Google account."
  type        = list(string)
  default     = []
}

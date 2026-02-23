variable "gcp_project" {
  description = "GCP Project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region for resources"
  type        = string
  default     = "asia-southeast1"
}

variable "gcp_zone" {
  description = "GCP zone for the VM"
  type        = string
  default     = "asia-southeast1-b"
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
  default     = 80
}

variable "domain_name" {
  description = "Domain name for the application (e.g., scan.rtb.cat)"
  type        = string
  default     = ""
}

variable "enable_https" {
  description = "Enable HTTPS via Caddy (requires domain_name)."
  type        = bool
  default     = false
}

variable "github_repo" {
  description = "GitHub repository URL for the application"
  type        = string
  default     = ""
}

variable "github_branch" {
  description = "GitHub branch to deploy"
  type        = string
  default     = "main"
}

variable "google_oauth_client_id" {
  description = "Google OAuth Client ID"
  type        = string
}

variable "google_oauth_client_secret" {
  description = "Google OAuth Client Secret"
  type        = string
  sensitive   = true
}

variable "allowed_email_domains" {
  description = "Email domains allowed to access"
  type        = list(string)
  default     = []
}

variable "allow_any_google_accounts" {
  description = "Allow any Google account when allowed_email_domains is empty (not recommended)."
  type        = bool
  default     = false
}

variable "service_account_email" {
  description = "Existing service account email for VM"
  type        = string
}

variable "gcs_bucket" {
  description = "Existing GCS bucket name"
  type        = string
  default     = ""
}

variable "artifact_registry_domain" {
  description = "Artifact Registry domain (e.g. asia-southeast1-docker.pkg.dev)"
  type        = string
  default     = "asia-southeast1-docker.pkg.dev"
}

variable "precompute_refresh_days" {
  description = "Days to refresh precompute for scheduled job"
  type        = number
  default     = 2
}

variable "precompute_refresh_max_age_hours" {
  description = "Max age for precompute refresh"
  type        = number
  default     = 36
}

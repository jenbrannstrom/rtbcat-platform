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
  description = "Domain name for the application (e.g., your-deployment.example.com)"
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

# =============================================================================
# Dedicated Serving DB for SG2
# =============================================================================

variable "enable_dedicated_serving_db" {
  description = "Create and use a dedicated Cloud SQL serving database for SG2 instead of the shared serving DB."
  type        = bool
  default     = false
}

variable "cloudsql_instance_name" {
  description = "Dedicated Cloud SQL instance name for SG2. Empty uses computed default."
  type        = string
  default     = ""
}

variable "cloudsql_database_version" {
  description = "Cloud SQL Postgres version for SG2 dedicated DB"
  type        = string
  default     = "POSTGRES_15"
}

variable "cloudsql_tier" {
  description = "Cloud SQL instance tier for SG2 dedicated DB"
  type        = string
  default     = "db-custom-1-3840"
}

variable "cloudsql_availability_type" {
  description = "Cloud SQL availability type (ZONAL or REGIONAL) for SG2 dedicated DB"
  type        = string
  default     = "ZONAL"
}

variable "cloudsql_disk_size_gb" {
  description = "Cloud SQL disk size in GB for SG2 dedicated DB"
  type        = number
  default     = 118
}

variable "cloudsql_database_name" {
  description = "Cloud SQL database name for SG2 dedicated DB"
  type        = string
  default     = "rtbcat_serving_sg2"
}

variable "serving_db_secret_id" {
  description = "Secret Manager secret id that stores SG2 DB credentials JSON. Empty uses computed default."
  type        = string
  default     = ""
}

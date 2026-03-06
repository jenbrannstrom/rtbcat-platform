# Cat-Scan GCP Infrastructure Variables
# Configure these in terraform.tfvars or via -var flags

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
  default     = ""
}

variable "github_branch" {
  description = "GitHub branch to deploy"
  type        = string
  default     = "main"
}

# =============================================================================
# OAuth2 Proxy - Google Authentication (REQUIRED)
# =============================================================================

variable "google_oauth_client_id" {
  description = "Google OAuth Client ID (from GCP Console)"
  type        = string

  validation {
    condition     = can(regex("^[0-9]+-[a-z0-9]+\\.apps\\.googleusercontent\\.com$", var.google_oauth_client_id))
    error_message = "Google OAuth Client ID must be in format: 123456789-xxxxx.apps.googleusercontent.com"
  }
}

variable "allowed_email_domains" {
  description = "Email domains allowed to access (e.g., ['rtb.cat', 'company.com'])."
  type        = list(string)
  default     = []
}

variable "allow_any_google_accounts" {
  description = "Allow any Google account when allowed_email_domains is empty (not recommended for production)."
  type        = bool
  default     = false
}

# =============================================================================
# Storage - Raw Parquet Bucket
# =============================================================================

variable "raw_parquet_bucket_name" {
  description = "GCS bucket name for raw parquet storage"
  type        = string
  default     = "rtbcat-raw-parquet"
}

variable "raw_parquet_lifecycle_days" {
  description = "Days to retain raw parquet files before lifecycle deletion"
  type        = number
  default     = 180
}

# =============================================================================
# Analytics - BigQuery
# =============================================================================

variable "bigquery_dataset_id" {
  description = "BigQuery dataset ID for analytics"
  type        = string
  default     = "rtbcat_analytics"
}

variable "bigquery_location" {
  description = "BigQuery dataset location (should match or align with GCS region)"
  type        = string
  default     = "asia-southeast1"
}

variable "bigquery_raw_facts_table_id" {
  description = "BigQuery table ID for raw facts"
  type        = string
  default     = "raw_facts"
}

# =============================================================================
# Database - Cloud SQL for Postgres
# =============================================================================

variable "cloudsql_database_version" {
  description = "Cloud SQL Postgres version"
  type        = string
  default     = "POSTGRES_15"
}

variable "cloudsql_tier" {
  description = "Cloud SQL instance tier"
  type        = string
  default     = "db-custom-1-3840"
}

variable "cloudsql_availability_type" {
  description = "Cloud SQL availability type (ZONAL or REGIONAL)"
  type        = string
  default     = "ZONAL"
}

variable "cloudsql_disk_size_gb" {
  description = "Cloud SQL disk size in GB"
  type        = number
  default     = 118
}

variable "cloudsql_database_name" {
  description = "Cloud SQL database name"
  type        = string
  default     = "rtbcat_serving"
}

variable "cloudsql_user_name" {
  description = "Cloud SQL user name"
  type        = string
  default     = "rtbcat_serving"
}

# =============================================================================
# Precompute Scheduler
# =============================================================================

variable "precompute_refresh_days" {
  description = "Number of days to refresh in scheduled precompute job"
  type        = number
  default     = 2
}

variable "precompute_refresh_max_age_hours" {
  description = "Maximum age in hours before precompute data is considered stale"
  type        = number
  default     = 36
}

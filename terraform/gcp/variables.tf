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
  description = "BigQuery dataset location (should match or align with GCS)"
  type        = string
  default     = "EU"
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
  description = "Cloud SQL instance tier (use performance-optimized tier for high I/O)"
  type        = string
  default     = "db-perf-optimized-N-2"
}

variable "cloudsql_availability_type" {
  description = "Cloud SQL availability type (ZONAL or REGIONAL)"
  type        = string
  default     = "REGIONAL"
}

variable "cloudsql_disk_size_gb" {
  description = "Cloud SQL disk size in GB"
  type        = number
  default     = 100
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
# Precompute Scheduler + Monitoring
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

variable "precompute_refresh_schedule" {
  description = "Cron schedule for Cloud Scheduler precompute refresh"
  type        = string
  default     = "0 3 * * *"
}

# =============================================================================
# Data Retention (GCS Parquet + BigQuery partitions)
# =============================================================================

variable "parquet_retention_days" {
  description = "Retention period for Parquet objects in GCS"
  type        = number
  default     = 90
}

variable "bigquery_partition_retention_days" {
  description = "Retention period for BigQuery partitions (days)"
  type        = number
  default     = 90
}

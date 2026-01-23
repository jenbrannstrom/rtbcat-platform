# Cat-Scan GCP Infrastructure
# Secure deployment with proper firewall rules
#
# SECURITY: This config does NOT expose ports 3000/8000 directly.
# All traffic goes through nginx/Caddy on ports 80/443.

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
    # Cloudflare provider commented out - uncomment if needed for DNS management
    # cloudflare = {
    #   source  = "cloudflare/cloudflare"
    #   version = "~> 4.0"
    # }
  }
}

provider "google" {
  project = var.gcp_project
  region  = var.gcp_region
}

# Random suffix for globally unique resource names
resource "random_id" "suffix" {
  byte_length = 4
}

resource "random_password" "precompute_refresh_secret" {
  length  = 32
  special = false
}

resource "random_password" "precompute_monitor_secret" {
  length  = 32
  special = false
}

locals {
  precompute_refresh_url = (var.enable_https && var.domain_name != "") ? "https://${var.domain_name}/api/precompute/refresh/scheduled" : "http://${google_compute_address.catscan.address}/api/precompute/refresh/scheduled"

  precompute_health_url = (var.enable_https && var.domain_name != "") ? "https://${var.domain_name}/api/precompute/health" : "http://${google_compute_address.catscan.address}/api/precompute/health"

  precompute_health_host = var.domain_name != "" ? var.domain_name : google_compute_address.catscan.address
  precompute_health_port = (var.enable_https && var.domain_name != "") ? 443 : 80
}

# =============================================================================
# NETWORK - VPC and Firewall
# =============================================================================

# Use default VPC for simplicity (like AWS setup)
data "google_compute_network" "default" {
  name = "default"
}

# -----------------------------------------------------------------------------
# FIREWALL RULES - SECURE CONFIGURATION
# -----------------------------------------------------------------------------
# CRITICAL: We ONLY expose 80/443. Ports 3000/8000 are NEVER exposed.
# This is what prevented attacks on AWS and what was MISSING on GCP.
# -----------------------------------------------------------------------------

# Allow HTTP (for redirect to HTTPS and Let's Encrypt challenges)
resource "google_compute_firewall" "allow_http" {
  name    = "${var.app_name}-${var.environment}-allow-http"
  network = data.google_compute_network.default.name

  allow {
    protocol = "tcp"
    ports    = ["80"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["${var.app_name}-server"]

  description = "Allow HTTP for HTTPS redirect and ACME challenges"
}

# Allow HTTPS (main application access)
resource "google_compute_firewall" "allow_https" {
  count   = var.enable_https ? 1 : 0
  name    = "${var.app_name}-${var.environment}-allow-https"
  network = data.google_compute_network.default.name

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  source_ranges = ["0.0.0.0/0"]
  target_tags   = ["${var.app_name}-server"]

  description = "Allow HTTPS traffic"
}

# Allow SSH - ONLY if explicitly configured with allowed CIDRs
# Default: No SSH access (use GCP Console serial console or IAP)
resource "google_compute_firewall" "allow_ssh" {
  count   = length(var.allowed_ssh_cidrs) > 0 ? 1 : 0
  name    = "${var.app_name}-${var.environment}-allow-ssh"
  network = data.google_compute_network.default.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # Restrict to specific IPs only
  source_ranges = var.allowed_ssh_cidrs
  target_tags   = ["${var.app_name}-server"]

  description = "Allow SSH from specific IPs only"
}

# Allow IAP (Identity-Aware Proxy) for secure SSH tunneling
# This is more secure than direct SSH - requires Google auth
resource "google_compute_firewall" "allow_iap" {
  name    = "${var.app_name}-${var.environment}-allow-iap"
  network = data.google_compute_network.default.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  # IAP's IP range
  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["${var.app_name}-server"]

  description = "Allow SSH via Identity-Aware Proxy (secure)"
}

# -----------------------------------------------------------------------------
# DANGEROUS PORTS - EXPLICITLY BLOCKED
# -----------------------------------------------------------------------------
# We create NO rules for 3000/8000. They are blocked by default.
# This comment exists to make it explicit that this is intentional.
#
# DO NOT ADD:
# - Port 3000 (Next.js) - CVE-2025-66478 RCE vulnerability
# - Port 8000 (FastAPI) - Should only be accessed via nginx
# -----------------------------------------------------------------------------

# =============================================================================
# STORAGE - Cloud Storage for backups and CSV archive
# =============================================================================

resource "google_storage_bucket" "catscan" {
  name     = "${var.app_name}-${var.environment}-data-${random_id.suffix.hex}"
  location = var.gcp_region

  # Prevent accidental deletion
  force_destroy = false

  # Enable versioning for backup recovery
  versioning {
    enabled = true
  }

  # Lifecycle rule: Delete old backups after 30 days
  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  # Lifecycle rule: Delete Parquet exports after retention window
  lifecycle_rule {
    condition {
      age            = var.parquet_retention_days
      matches_prefix = ["parquet/"]
    }
    action {
      type = "Delete"
    }
  }

  # Lifecycle rule: Delete BigQuery exports after retention window
  lifecycle_rule {
    condition {
      age            = var.bigquery_partition_retention_days
      matches_prefix = ["bigquery/"]
    }
    action {
      type = "Delete"
    }
  }

  # Block public access
  public_access_prevention = "enforced"

  uniform_bucket_level_access = true

  labels = {
    app         = var.app_name
    environment = var.environment
  }
}

# Raw parquet bucket for analytics ingestion
resource "google_storage_bucket" "raw_parquet" {
  name     = var.raw_parquet_bucket_name
  location = var.gcp_region

  force_destroy = false

  public_access_prevention    = "enforced"
  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = var.raw_parquet_lifecycle_days
    }
    action {
      type = "Delete"
    }
  }

  labels = {
    app         = var.app_name
    environment = var.environment
    purpose     = "raw-parquet"
  }
}

# =============================================================================
# ANALYTICS - BigQuery Dataset + Raw Facts Table
# =============================================================================

resource "google_project_service" "bigquery" {
  service            = "bigquery.googleapis.com"
  disable_on_destroy = false
}

resource "google_bigquery_dataset" "rtbcat_analytics" {
  dataset_id = var.bigquery_dataset_id
  location   = var.bigquery_location

  labels = {
    app         = var.app_name
    environment = var.environment
    purpose     = "analytics"
  }

  depends_on = [google_project_service.bigquery]
}

resource "google_bigquery_table" "raw_facts" {
  dataset_id = google_bigquery_dataset.rtbcat_analytics.dataset_id
  table_id   = var.bigquery_raw_facts_table_id

  schema = jsonencode([
    {
      name = "event_timestamp"
      type = "TIMESTAMP"
      mode = "REQUIRED"
    },
    {
      name = "payload"
      type = "JSON"
      mode = "NULLABLE"
    }
  ])

  time_partitioning {
    type  = "DAY"
    field = "event_timestamp"
  }
}

# =============================================================================
# IAM - Service Account
# =============================================================================

resource "google_service_account" "catscan" {
  account_id   = "${var.app_name}-${var.environment}-sa"
  display_name = "Cat-Scan ${var.environment} Service Account"
  description  = "Service account for Cat-Scan application"
}

# Grant storage access to service account
resource "google_storage_bucket_iam_member" "catscan_storage" {
  bucket = google_storage_bucket.catscan.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.catscan.email}"
}

resource "google_storage_bucket_iam_member" "raw_parquet_storage" {
  bucket = google_storage_bucket.raw_parquet.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.catscan.email}"
}

resource "google_project_iam_member" "bigquery_job_user" {
  project = var.gcp_project
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.catscan.email}"
}

resource "google_bigquery_dataset_iam_member" "bigquery_data_editor" {
  dataset_id = google_bigquery_dataset.rtbcat_analytics.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.catscan.email}"
}

resource "google_project_iam_member" "cloudsql_client" {
  project = var.gcp_project
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.catscan.email}"
}

# Grant logging access
resource "google_project_iam_member" "catscan_logging" {
  project = var.gcp_project
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.catscan.email}"
}

# =============================================================================
# DATABASE - Cloud SQL for Postgres (serving)
# =============================================================================

resource "google_project_service" "sqladmin" {
  service            = "sqladmin.googleapis.com"
  disable_on_destroy = false
}

resource "google_sql_database_instance" "rtbcat_serving" {
  name             = "${var.app_name}-${var.environment}-serving"
  region           = var.gcp_region
  database_version = var.cloudsql_database_version

  settings {
    tier              = var.cloudsql_tier
    availability_type = var.cloudsql_availability_type
    disk_type         = "PD_SSD"
    disk_size         = var.cloudsql_disk_size_gb

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
    }

    maintenance_window {
      day          = 7
      hour         = 3
      update_track = "stable"
    }
  }

  deletion_protection = var.environment == "production"

  depends_on = [google_project_service.sqladmin]
}

resource "google_sql_database" "serving_db" {
  name     = var.cloudsql_database_name
  instance = google_sql_database_instance.rtbcat_serving.name
}

resource "random_password" "serving_db_password" {
  length  = 24
  special = true
}

resource "google_sql_user" "serving_user" {
  name     = var.cloudsql_user_name
  instance = google_sql_database_instance.rtbcat_serving.name
  password = random_password.serving_db_password.result
}

# =============================================================================
# COMPUTE - GCE Instance
# =============================================================================

resource "google_compute_address" "catscan" {
  name   = "${var.app_name}-${var.environment}-ip"
  region = var.gcp_region

  description = "Static IP for Cat-Scan"
}

resource "google_compute_instance" "catscan" {
  name         = "${var.app_name}-${var.environment}"
  machine_type = var.machine_type
  zone         = var.gcp_zone

  tags = ["${var.app_name}-server"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2404-lts-amd64"
      size  = var.boot_disk_size
      type  = "pd-ssd"
    }
  }

  network_interface {
    network = data.google_compute_network.default.name

    access_config {
      nat_ip = google_compute_address.catscan.address
    }
  }

  service_account {
    email  = google_service_account.catscan.email
    scopes = ["cloud-platform"]
  }

  # Startup script - hardened setup with OAuth2 Proxy
  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    app_name                   = var.app_name
    environment                = var.environment
    domain_name                = var.domain_name
    enable_https               = var.enable_https
    github_repo                = var.github_repo
    github_branch              = var.github_branch
    gcp_region                 = var.gcp_region
    gcs_bucket                 = google_storage_bucket.catscan.name
    google_oauth_client_id     = var.google_oauth_client_id
    google_oauth_client_secret = var.google_oauth_client_secret
    allowed_email_domains      = var.allowed_email_domains
    precompute_refresh_secret  = random_password.precompute_refresh_secret.result
    precompute_monitor_secret  = random_password.precompute_monitor_secret.result
    precompute_refresh_days    = var.precompute_refresh_days
    precompute_refresh_max_age = var.precompute_refresh_max_age_hours
  })

  # Enable deletion protection in production
  deletion_protection = var.environment == "production"

  labels = {
    app         = var.app_name
    environment = var.environment
  }

  # Shielded VM for extra security
  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# COMPUTE - Parallel SG Instance (for migration, keeps EU intact)
# =============================================================================

resource "google_compute_address" "catscan_sg" {
  count  = var.create_sg_instance ? 1 : 0
  name   = "${var.app_name}-${var.environment}-sg-ip"
  region = var.gcp_region

  description = "Static IP for Cat-Scan (SG migration)"
}

resource "google_compute_instance" "catscan_sg" {
  count        = var.create_sg_instance ? 1 : 0
  name         = "${var.app_name}-${var.environment}-sg"
  machine_type = var.machine_type
  zone         = var.gcp_zone

  tags = ["${var.app_name}-server"]

  boot_disk {
    initialize_params {
      image = "ubuntu-os-cloud/ubuntu-2404-lts-amd64"
      size  = var.boot_disk_size
      type  = "pd-ssd"
    }
  }

  network_interface {
    network = data.google_compute_network.default.name

    access_config {
      nat_ip = google_compute_address.catscan_sg[0].address
    }
  }

  service_account {
    email  = google_service_account.catscan.email
    scopes = ["cloud-platform"]
  }

  # Startup script - hardened setup with OAuth2 Proxy
  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    app_name                   = var.app_name
    environment                = var.environment
    domain_name                = var.domain_name
    enable_https               = var.enable_https
    github_repo                = var.github_repo
    github_branch              = var.github_branch
    gcp_region                 = var.gcp_region
    gcs_bucket                 = google_storage_bucket.catscan.name
    google_oauth_client_id     = var.google_oauth_client_id
    google_oauth_client_secret = var.google_oauth_client_secret
    allowed_email_domains      = var.allowed_email_domains
    precompute_refresh_secret  = random_password.precompute_refresh_secret.result
    precompute_monitor_secret  = random_password.precompute_monitor_secret.result
    precompute_refresh_days    = var.precompute_refresh_days
    precompute_refresh_max_age = var.precompute_refresh_max_age_hours
  })

  deletion_protection = var.environment == "production"

  labels = {
    app         = var.app_name
    environment = var.environment
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  lifecycle {
    create_before_destroy = true
  }
}

# =============================================================================
# SECRET MANAGER - Credentials Storage
# =============================================================================
# Store credentials in Secret Manager so they persist across deployments.
# ONE-TIME SETUP: Upload credentials once, they're always available.

# Enable Secret Manager API
resource "google_project_service" "secretmanager" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "cloudscheduler" {
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "monitoring" {
  service            = "monitoring.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "logging" {
  service            = "logging.googleapis.com"
  disable_on_destroy = false
}

# BigQuery API already enabled above (line 245)

# Gmail OAuth Client (gmail-oauth-client.json)
resource "google_secret_manager_secret" "gmail_oauth_client" {
  secret_id = "${var.app_name}-gmail-oauth-client"

  replication {
    auto {}
  }

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "gmail-oauth"
  }

  depends_on = [google_project_service.secretmanager]
}

# Gmail Token (gmail-token.json) - created after first auth
resource "google_secret_manager_secret" "gmail_token" {
  secret_id = "${var.app_name}-gmail-token"

  replication {
    auto {}
  }

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "gmail-token"
  }

  depends_on = [google_project_service.secretmanager]
}

# Service Account for Authorized Buyers API
resource "google_secret_manager_secret" "ab_service_account" {
  secret_id = "${var.app_name}-ab-service-account"

  replication {
    auto {}
  }

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "service-account"
  }

  depends_on = [google_project_service.secretmanager]
}

# =============================================================================
# SERVING DB CREDENTIALS (for Postgres read-routing)
# =============================================================================

resource "google_secret_manager_secret" "serving_db_credentials" {
  secret_id = "${var.app_name}-serving-db-credentials"

  replication {
    auto {}
  }

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "database"
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret_version" "serving_db_credentials" {
  secret = google_secret_manager_secret.serving_db_credentials.id

  secret_data = jsonencode({
    instance_connection_name = google_sql_database_instance.rtbcat_serving.connection_name
    database                 = google_sql_database.serving_db.name
    username                 = google_sql_user.serving_user.name
    password                 = random_password.serving_db_password.result
  })
}

# =============================================================================
# BIGQUERY - Optional Dataset (Partition Retention)
# =============================================================================

resource "google_bigquery_dataset" "catscan" {
  count                     = var.bigquery_dataset_id != "" ? 1 : 0
  dataset_id                = var.bigquery_dataset_id
  location                  = var.gcp_region
  default_partition_expiration_ms = var.bigquery_partition_retention_days * 86400000

  labels = {
    app         = var.app_name
    environment = var.environment
  }

  depends_on = [google_project_service.bigquery]
}

# =============================================================================
# CLOUD SCHEDULER - Precompute Refresh
# =============================================================================

resource "google_cloud_scheduler_job" "precompute_refresh" {
  name        = "${var.app_name}-precompute-refresh"
  description = "Daily precompute refresh for dashboard caches"
  schedule    = var.precompute_refresh_schedule
  time_zone   = "Etc/UTC"
  region      = var.gcp_region

  http_target {
    http_method = "POST"
    uri         = local.precompute_refresh_url
    headers = {
      X-Precompute-Refresh-Secret = random_password.precompute_refresh_secret.result
    }
  }

  depends_on = [google_project_service.cloudscheduler]
}

# =============================================================================
# MONITORING - Precompute Health + Scheduler Failures
# =============================================================================

resource "google_monitoring_uptime_check_config" "precompute_health" {
  display_name = "${var.app_name}-precompute-health"
  timeout      = "10s"
  period       = "300s"

  http_check {
    path         = "/api/precompute/health"
    port         = local.precompute_health_port
    use_ssl      = var.enable_https && var.domain_name != ""
    validate_ssl = var.enable_https && var.domain_name != ""
    headers = {
      X-Precompute-Monitor-Secret = random_password.precompute_monitor_secret.result
    }
  }

  monitored_resource {
    type = "uptime_url"
    labels = {
      host = local.precompute_health_host
    }
  }

  depends_on = [google_project_service.monitoring]
}

resource "google_logging_metric" "precompute_refresh_failures" {
  name   = "${var.app_name}-precompute-refresh-failures"
  filter = "resource.type=\"cloud_scheduler_job\" AND resource.labels.job_id=\"${google_cloud_scheduler_job.precompute_refresh.name}\" AND severity>=ERROR"

  metric_descriptor {
    metric_kind = "DELTA"
    value_type  = "INT64"
  }

  depends_on = [google_project_service.logging]
}

resource "google_monitoring_alert_policy" "precompute_health_gap" {
  display_name = "${var.app_name}-precompute-health-gap"
  combiner     = "OR"

  conditions {
    display_name = "Precompute health check failing"
    condition_threshold {
      filter          = "metric.type=\"monitoring.googleapis.com/uptime_check/check_passed\" AND metric.label.check_id=\"${google_monitoring_uptime_check_config.precompute_health.uptime_check_id}\""
      comparison      = "COMPARISON_LT"
      threshold_value = 1
      duration        = "300s"
      trigger {
        count = 1
      }
    }
  }

  depends_on = [google_project_service.monitoring]
}

resource "google_monitoring_alert_policy" "precompute_refresh_failures" {
  display_name = "${var.app_name}-precompute-refresh-failures"
  combiner     = "OR"

  conditions {
    display_name = "Precompute refresh failed"
    condition_threshold {
      filter          = "metric.type=\"logging.googleapis.com/user/${google_logging_metric.precompute_refresh_failures.name}\""
      comparison      = "COMPARISON_GT"
      threshold_value = 0
      duration        = "60s"
      trigger {
        count = 1
      }
    }
  }

  depends_on = [
    google_project_service.monitoring,
    google_project_service.logging,
  ]
}

# Grant VM service account access to read secrets
resource "google_secret_manager_secret_iam_member" "gmail_oauth_client_access" {
  secret_id = google_secret_manager_secret.gmail_oauth_client.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.catscan.email}"
}

resource "google_secret_manager_secret_iam_member" "gmail_token_access" {
  secret_id = google_secret_manager_secret.gmail_token.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.catscan.email}"
}

resource "google_secret_manager_secret_iam_member" "ab_service_account_access" {
  secret_id = google_secret_manager_secret.ab_service_account.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.catscan.email}"
}

resource "google_secret_manager_secret_iam_member" "serving_db_credentials_access" {
  secret_id = google_secret_manager_secret.serving_db_credentials.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.catscan.email}"
}

# =============================================================================
# DNS - Cloudflare (Optional)
# =============================================================================
# NOTE: Cloudflare provider removed to avoid initialization errors when not used.
# If you want to manage DNS via Terraform, uncomment and configure cloudflare_api_token.
# For now, manage DNS manually in your DNS provider.
#
# provider "cloudflare" {
#   api_token = var.cloudflare_api_token
# }
#
# resource "cloudflare_record" "catscan" {
#   count   = var.cloudflare_api_token != "" && var.cloudflare_zone_id != "" ? 1 : 0
#   zone_id = var.cloudflare_zone_id
#   name    = var.domain_name
#   content = google_compute_address.catscan.address
#   type    = "A"
#   ttl     = 1
#   proxied = false
# }

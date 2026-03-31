# Cat-Scan GCP Infrastructure
# Secure deployment with proper firewall rules
#
# SECURITY: This config does NOT expose ports 3000/8000 directly.
# All traffic goes through nginx/Caddy on ports 80/443.
#
# NOTE: Secret versions are managed externally via gcloud / GSM console.
# Terraform manages the secret *resources* and IAM, not the secret *data*.

terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project
  region  = var.gcp_region
}

locals {
  gmail_import_url       = (var.enable_https && var.domain_name != "") ? "https://${var.domain_name}/api/gmail/import/scheduled" : "http://${google_compute_address.catscan.address}/api/gmail/import/scheduled"
  precompute_refresh_url = (var.enable_https && var.domain_name != "") ? "https://${var.domain_name}/api/precompute/refresh/scheduled" : "http://${google_compute_address.catscan.address}/api/precompute/refresh/scheduled"
}

# =============================================================================
# NETWORK - VPC and Firewall
# =============================================================================

data "google_compute_network" "default" {
  name = "default"
}

# -----------------------------------------------------------------------------
# FIREWALL RULES - SECURE CONFIGURATION
# -----------------------------------------------------------------------------
# CRITICAL: We ONLY expose 80/443. Ports 3000/8000 are NEVER exposed.
# -----------------------------------------------------------------------------

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

resource "google_compute_firewall" "allow_ssh" {
  count   = length(var.allowed_ssh_cidrs) > 0 ? 1 : 0
  name    = "${var.app_name}-${var.environment}-allow-ssh"
  network = data.google_compute_network.default.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = var.allowed_ssh_cidrs
  target_tags   = ["${var.app_name}-server"]

  description = "Allow SSH from specific IPs only"
}

resource "google_compute_firewall" "allow_iap" {
  name    = "${var.app_name}-${var.environment}-allow-iap"
  network = data.google_compute_network.default.name

  allow {
    protocol = "tcp"
    ports    = ["22"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["${var.app_name}-server"]

  description = "Allow SSH via Identity-Aware Proxy (secure)"
}

# =============================================================================
# STORAGE - Raw Parquet Bucket
# =============================================================================

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
  dataset_id          = google_bigquery_dataset.rtbcat_analytics.dataset_id
  table_id            = var.bigquery_raw_facts_table_id
  deletion_protection = true

  schema = jsonencode([
    { name = "metric_date", type = "DATE", mode = "NULLABLE" },
    { name = "billing_id", type = "STRING", mode = "NULLABLE" },
    { name = "creative_id", type = "STRING", mode = "NULLABLE" },
    { name = "creative_size", type = "STRING", mode = "NULLABLE" },
    { name = "creative_format", type = "STRING", mode = "NULLABLE" },
    { name = "buyer_account_id", type = "STRING", mode = "NULLABLE" },
    { name = "reached_queries", type = "INTEGER", mode = "NULLABLE" },
    { name = "impressions", type = "INTEGER", mode = "NULLABLE" },
    { name = "spend_buyer_currency", type = "FLOAT", mode = "NULLABLE" },
    { name = "active_view_viewable", type = "INTEGER", mode = "NULLABLE" },
    { name = "active_view_measurable", type = "INTEGER", mode = "NULLABLE" },
    { name = "report_type", type = "STRING", mode = "NULLABLE" },
    { name = "country", type = "STRING", mode = "NULLABLE" },
    { name = "bid_filtering_reason", type = "STRING", mode = "NULLABLE" },
    { name = "bids", type = "INTEGER", mode = "NULLABLE" },
    { name = "hour", type = "INTEGER", mode = "NULLABLE" },
    { name = "publisher_id", type = "STRING", mode = "NULLABLE" },
    { name = "publisher_name", type = "STRING", mode = "NULLABLE" },
    { name = "bid_requests", type = "INTEGER", mode = "NULLABLE" },
    { name = "inventory_matches", type = "INTEGER", mode = "NULLABLE" },
    { name = "successful_responses", type = "INTEGER", mode = "NULLABLE" },
    { name = "bids_in_auction", type = "INTEGER", mode = "NULLABLE" },
    { name = "auctions_won", type = "INTEGER", mode = "NULLABLE" },
    { name = "clicks", type = "INTEGER", mode = "NULLABLE" },
  ])

  time_partitioning {
    type  = "DAY"
    field = "metric_date"
  }

  clustering = ["buyer_account_id"]

  lifecycle {
    ignore_changes = [schema]
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

resource "google_storage_bucket_iam_member" "raw_parquet_storage" {
  bucket = google_storage_bucket.raw_parquet.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.catscan.email}"
}

resource "google_project_iam_member" "cloudsql_client" {
  project = var.gcp_project
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.catscan.email}"
}

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
    tier                        = var.cloudsql_tier
    availability_type           = var.cloudsql_availability_type
    deletion_protection_enabled = var.environment == "production"
    disk_type                   = "PD_SSD"
    disk_size                   = var.cloudsql_disk_size_gb

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

  lifecycle {
    ignore_changes = [settings[0].disk_size]
  }
}

resource "google_sql_database" "serving_db" {
  name     = var.cloudsql_database_name
  instance = google_sql_database_instance.rtbcat_serving.name
}

resource "google_sql_user" "serving_user" {
  name     = var.cloudsql_user_name
  instance = google_sql_database_instance.rtbcat_serving.name

  lifecycle {
    ignore_changes = [password]
  }
}

# =============================================================================
# COMPUTE - GCE Instance (primary SG)
# =============================================================================

resource "google_compute_address" "catscan" {
  name   = "${var.app_name}-${var.environment}-sg-ip"
  region = var.gcp_region

  description = "Static IP for Cat-Scan (SG migration)"
}

resource "google_compute_instance" "catscan" {
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
      nat_ip = google_compute_address.catscan.address
    }
  }

  service_account {
    email  = google_service_account.catscan.email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    app_name                   = var.app_name
    environment                = var.environment
    domain_name                = var.domain_name
    enable_https               = var.enable_https
    github_repo                = var.github_repo
    github_branch              = var.github_branch
    gcp_region                 = var.gcp_region
    gcs_bucket                 = var.raw_parquet_bucket_name
    google_oauth_client_id     = var.google_oauth_client_id
    allowed_email_domains      = var.allowed_email_domains
    allow_any_google_accounts  = var.allow_any_google_accounts
    oauth_client_secret_id     = "${var.app_name}-oauth-client-secret"
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
    ignore_changes = [
      metadata_startup_script,
      metadata,
      boot_disk[0].initialize_params[0].image,
    ]
  }
}

# =============================================================================
# SECRET MANAGER - Credentials Storage
# =============================================================================
# Secret *resources* and IAM are managed here.
# Secret *versions* (data) are managed externally via gcloud.

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

resource "google_secret_manager_secret" "precompute_refresh_secret" {
  secret_id = "${var.app_name}-precompute-refresh-secret"

  replication {
    auto {}
  }

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "scheduler"
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "precompute_monitor_secret" {
  secret_id = "${var.app_name}-precompute-monitor-secret"

  replication {
    auto {}
  }

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "scheduler"
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "gmail_import_secret" {
  secret_id = "${var.app_name}-gmail-import-secret"

  replication {
    auto {}
  }

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "scheduler"
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "creative_cache_refresh_secret" {
  secret_id = "${var.app_name}-creative-cache-refresh-secret"

  replication {
    auto {}
  }

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "scheduler"
  }

  depends_on = [google_project_service.secretmanager]
}

resource "google_secret_manager_secret" "oauth_client_secret" {
  secret_id = "${var.app_name}-oauth-client-secret"

  replication {
    auto {}
  }

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "oauth"
  }

  depends_on = [google_project_service.secretmanager]
}

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

resource "google_secret_manager_secret_iam_member" "precompute_refresh_secret_access" {
  secret_id = google_secret_manager_secret.precompute_refresh_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.catscan.email}"
}

resource "google_secret_manager_secret_iam_member" "precompute_monitor_secret_access" {
  secret_id = google_secret_manager_secret.precompute_monitor_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.catscan.email}"
}

resource "google_secret_manager_secret_iam_member" "gmail_import_secret_access" {
  secret_id = google_secret_manager_secret.gmail_import_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.catscan.email}"
}

resource "google_secret_manager_secret_iam_member" "creative_cache_refresh_secret_access" {
  secret_id = google_secret_manager_secret.creative_cache_refresh_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.catscan.email}"
}

resource "google_secret_manager_secret_iam_member" "oauth_client_secret_access" {
  secret_id = google_secret_manager_secret.oauth_client_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.catscan.email}"
}

# =============================================================================
# CLOUD SCHEDULER - Precompute Refresh
# =============================================================================

resource "google_cloud_scheduler_job" "precompute_refresh" {
  name        = "precompute-refresh"
  description = "Daily precompute refresh after Gmail import catch-up completes"
  schedule    = "30 13 * * *"
  time_zone   = "Etc/UTC"
  region      = var.gcp_region

  http_target {
    http_method = "POST"
    uri         = local.precompute_refresh_url
  }

  retry_config {
    retry_count          = 3
    min_backoff_duration = "60s"
    max_backoff_duration = "600s"
  }

  depends_on = [google_project_service.cloudscheduler]

  lifecycle {
    ignore_changes = [
      http_target[0].headers,
      http_target[0].uri,
    ]
  }
}

# =============================================================================
# CLOUD SCHEDULER - Gmail Import
# =============================================================================

resource "google_cloud_scheduler_job" "gmail_import" {
  name        = "gmail-import"
  description = "Daily Gmail report import - 1h after emails arrive (~11:00 UTC)"
  schedule    = "0 12 * * *"
  time_zone   = "Etc/UTC"
  region      = var.gcp_region

  http_target {
    http_method = "POST"
    uri         = local.gmail_import_url
  }

  retry_config {
    retry_count          = 3
    min_backoff_duration = "60s"
    max_backoff_duration = "600s"
  }

  depends_on = [google_project_service.cloudscheduler]

  lifecycle {
    ignore_changes = [
      http_target[0].headers,
      http_target[0].uri,
    ]
  }
}

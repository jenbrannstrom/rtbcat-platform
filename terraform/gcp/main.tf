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

  # Block public access
  public_access_prevention = "enforced"

  uniform_bucket_level_access = true

  labels = {
    app         = var.app_name
    environment = var.environment
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

# Grant logging access
resource "google_project_iam_member" "catscan_logging" {
  project = var.gcp_project
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.catscan.email}"
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
    gcs_bucket                 = google_storage_bucket.catscan.name
    google_oauth_client_id     = var.google_oauth_client_id
    google_oauth_client_secret = var.google_oauth_client_secret
    allowed_email_domains      = var.allowed_email_domains
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
# SECRET MANAGER - Credentials Storage
# =============================================================================
# Store credentials in Secret Manager so they persist across deployments.
# ONE-TIME SETUP: Upload credentials once, they're always available.

# Enable Secret Manager API
resource "google_project_service" "secretmanager" {
  service            = "secretmanager.googleapis.com"
  disable_on_destroy = false
}

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

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
  }
}

provider "google" {
  project = var.gcp_project
  region  = var.gcp_region
}

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

resource "random_password" "gmail_import_secret" {
  length  = 32
  special = false
}

resource "random_password" "creative_cache_refresh_secret" {
  length  = 32
  special = false
}

data "google_compute_network" "default" {
  name = "default"
}

locals {
  service_account_id = replace(var.service_account_email, "@.*", "")
}

data "google_service_account" "catscan" {
  account_id = local.service_account_id
}

resource "google_compute_address" "catscan_sg_vm2" {
  name   = "${var.app_name}-${var.environment}-sg2-ip"
  region = var.gcp_region

  description = "Static IP for Cat-Scan SG VM2"
}

resource "google_compute_instance" "catscan_sg_vm2" {
  name         = "${var.app_name}-${var.environment}-sg2"
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
      nat_ip = google_compute_address.catscan_sg_vm2.address
    }
  }

  service_account {
    email  = data.google_service_account.catscan.email
    scopes = ["cloud-platform"]
  }

  metadata_startup_script = templatefile("${path.module}/startup.sh", {
    app_name                      = var.app_name
    environment                   = var.environment
    domain_name                   = var.domain_name
    enable_https                  = var.enable_https
    github_repo                   = var.github_repo
    github_branch                 = var.github_branch
    gcp_region                    = var.gcp_region
    gcs_bucket                    = var.gcs_bucket
    google_oauth_client_id        = var.google_oauth_client_id
    google_oauth_client_secret    = ""
    allowed_email_domains         = var.allowed_email_domains
    allow_any_google_accounts     = var.allow_any_google_accounts
    precompute_refresh_secret     = ""
    precompute_monitor_secret     = ""
    gmail_import_secret           = ""
    creative_cache_refresh_secret = ""
    precompute_refresh_days       = var.precompute_refresh_days
    precompute_refresh_max_age    = var.precompute_refresh_max_age_hours
    artifact_registry_domain      = var.artifact_registry_domain
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

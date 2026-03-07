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

data "google_compute_network" "default" {
  name = "default"
}

locals {
  service_account_id               = replace(var.service_account_email, "@.*", "")
  dedicated_serving_db_secret_id   = trimspace(var.serving_db_secret_id) != "" ? var.serving_db_secret_id : "${var.app_name}-serving-db-credentials-sg2"
  dedicated_cloudsql_instance_name = trimspace(var.cloudsql_instance_name) != "" ? var.cloudsql_instance_name : "${var.app_name}-${var.environment}-sg2-serving"
  shared_serving_db_secret_id      = "${var.app_name}-serving-db-credentials"
  shared_cloudsql_instance_name    = "${var.app_name}-${var.environment}-serving"
  effective_serving_db_secret_id   = var.enable_dedicated_serving_db ? local.dedicated_serving_db_secret_id : local.shared_serving_db_secret_id
  effective_cloudsql_instance_name = var.enable_dedicated_serving_db ? local.dedicated_cloudsql_instance_name : local.shared_cloudsql_instance_name
}

data "google_service_account" "catscan" {
  account_id = local.service_account_id
}

resource "google_sql_database_instance" "sg2_serving" {
  count            = var.enable_dedicated_serving_db ? 1 : 0
  name             = local.dedicated_cloudsql_instance_name
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

  lifecycle {
    ignore_changes = [settings[0].disk_size]
  }
}

resource "google_sql_database" "sg2_serving_db" {
  count    = var.enable_dedicated_serving_db ? 1 : 0
  name     = var.cloudsql_database_name
  instance = google_sql_database_instance.sg2_serving[0].name
}

resource "google_secret_manager_secret" "sg2_serving_db_credentials" {
  count     = var.enable_dedicated_serving_db ? 1 : 0
  secret_id = local.dedicated_serving_db_secret_id

  replication {
    auto {}
  }

  labels = {
    app         = var.app_name
    environment = var.environment
    type        = "database"
    scope       = "sg2"
  }
}

resource "google_secret_manager_secret_iam_member" "sg2_serving_db_credentials_access" {
  count     = var.enable_dedicated_serving_db ? 1 : 0
  secret_id = google_secret_manager_secret.sg2_serving_db_credentials[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_service_account.catscan.email}"
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
    app_name                   = var.app_name
    environment                = var.environment
    domain_name                = var.domain_name
    enable_https               = var.enable_https
    github_repo                = var.github_repo
    github_branch              = var.github_branch
    gcp_region                 = var.gcp_region
    gcs_bucket                 = var.gcs_bucket
    google_oauth_client_id     = var.google_oauth_client_id
    allowed_email_domains      = var.allowed_email_domains
    allow_any_google_accounts  = var.allow_any_google_accounts
    oauth_client_secret_id     = "${var.app_name}-oauth-client-secret-sg2"
    serving_db_secret_id       = local.effective_serving_db_secret_id
    cloudsql_instance_name     = local.effective_cloudsql_instance_name
    precompute_refresh_days    = var.precompute_refresh_days
    precompute_refresh_max_age = var.precompute_refresh_max_age_hours
    artifact_registry_domain   = var.artifact_registry_domain
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

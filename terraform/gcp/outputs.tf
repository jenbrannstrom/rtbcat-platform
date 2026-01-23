# Cat-Scan GCP Infrastructure Outputs

output "instance_name" {
  description = "Name of the GCE instance"
  value       = google_compute_instance.catscan.name
}

output "instance_zone" {
  description = "Zone of the GCE instance"
  value       = google_compute_instance.catscan.zone
}

output "sg_instance_name" {
  description = "Name of the SG migration instance"
  value       = google_compute_instance.catscan_sg.name
}

output "sg_public_ip" {
  description = "Static public IP for the SG migration instance"
  value       = google_compute_address.catscan_sg.address
}

output "sg_ssh_command" {
  description = "SSH command for the SG migration instance (IAP)"
  value       = "gcloud compute ssh ${google_compute_instance.catscan_sg.name} --zone=${google_compute_instance.catscan_sg.zone} --tunnel-through-iap"
}

output "public_ip" {
  description = "Static public IP address"
  value       = google_compute_address.catscan.address
}

output "gcs_bucket" {
  description = "Cloud Storage bucket for backups and data"
  value       = google_storage_bucket.catscan.name
}

output "raw_parquet_bucket" {
  description = "Cloud Storage bucket for raw parquet ingestion"
  value       = google_storage_bucket.raw_parquet.name
}

output "service_account_email" {
  description = "Service account email"
  value       = google_service_account.catscan.email
}

output "dashboard_url" {
  description = "Dashboard URL"
  value       = var.enable_https && var.domain_name != "" ? "https://${var.domain_name}" : "http://${google_compute_address.catscan.address}"
}

output "api_url" {
  description = "API URL"
  value       = var.enable_https && var.domain_name != "" ? "https://${var.domain_name}/api" : "http://${google_compute_address.catscan.address}/api"
}

output "precompute_refresh_url" {
  description = "Precompute refresh endpoint URL"
  value       = var.enable_https && var.domain_name != "" ? "https://${var.domain_name}/api/precompute/refresh/scheduled" : "http://${google_compute_address.catscan.address}/api/precompute/refresh/scheduled"
}

output "precompute_health_url" {
  description = "Precompute health endpoint URL"
  value       = var.enable_https && var.domain_name != "" ? "https://${var.domain_name}/api/precompute/health" : "http://${google_compute_address.catscan.address}/api/precompute/health"
}

output "ssh_command" {
  description = "SSH command (via IAP - secure)"
  value       = "gcloud compute ssh ${google_compute_instance.catscan.name} --zone=${google_compute_instance.catscan.zone} --tunnel-through-iap"
}

output "ssh_command_direct" {
  description = "Direct SSH command (only if allowed_ssh_cidrs configured)"
  value       = length(var.allowed_ssh_cidrs) > 0 ? "ssh ubuntu@${google_compute_address.catscan.address}" : "Direct SSH disabled - use IAP"
}

output "secret_manager_secrets" {
  description = "Secret Manager secrets for credentials"
  value = {
    gmail_oauth_client    = google_secret_manager_secret.gmail_oauth_client.id
    gmail_token           = google_secret_manager_secret.gmail_token.id
    ab_service_account    = google_secret_manager_secret.ab_service_account.id
    serving_db_credentials = google_secret_manager_secret.serving_db_credentials.id
  }
}

output "bigquery_dataset" {
  description = "BigQuery dataset for analytics"
  value       = google_bigquery_dataset.rtbcat_analytics.dataset_id
}

output "bigquery_raw_facts_table" {
  description = "BigQuery raw facts table"
  value       = google_bigquery_table.raw_facts.table_id
}

output "cloudsql_instance_connection_name" {
  description = "Cloud SQL instance connection name"
  value       = google_sql_database_instance.rtbcat_serving.connection_name
}

output "cloudsql_database" {
  description = "Cloud SQL database name"
  value       = google_sql_database.serving_db.name
}

output "credential_upload_commands" {
  description = "Commands to upload credentials to Secret Manager (ONE-TIME)"
  value       = <<-EOT

    === ONE-TIME Credential Setup ===

    Upload your credentials to Secret Manager ONCE. They persist forever.

    # 1. Gmail OAuth Client (from GCP Console > APIs > Credentials)
    gcloud secrets versions add ${var.app_name}-gmail-oauth-client \
      --data-file=gmail-oauth-client.json

    # 2. Authorized Buyers Service Account
    gcloud secrets versions add ${var.app_name}-ab-service-account \
      --data-file=catscan-service-account.json

    # 3. Gmail Token (after running gmail_auth.py locally)
    gcloud secrets versions add ${var.app_name}-gmail-token \
      --data-file=~/.catscan/credentials/gmail-token.json

    # 4. Serving DB credentials are created automatically by Terraform:
    #    Secret: ${var.app_name}-serving-db-credentials

    After upload, credentials are automatically pulled on VM deploy/restart.

  EOT
}

output "next_steps" {
  description = "Post-deployment instructions"
  value       = <<-EOT

    === Cat-Scan GCP Deployment Complete ===

    1. FIRST-TIME ONLY: Upload credentials to Secret Manager
       (See 'credential_upload_commands' output above)

    2. Wait 3-5 minutes for the startup script to complete

    3. Check startup progress:
       gcloud compute ssh ${google_compute_instance.catscan.name} --zone=${google_compute_instance.catscan.zone} --tunnel-through-iap
       sudo tail -f /var/log/catscan-setup.log

    4. Point DNS A record to: ${google_compute_address.catscan.address}
       Domain: ${var.domain_name != "" ? var.domain_name : "(not configured)"}

    5. Access your dashboard:
       ${var.enable_https && var.domain_name != "" ? "https://${var.domain_name}" : "http://${google_compute_address.catscan.address}"}

    === Credentials are now automatic! ===

    Credentials stored in Secret Manager:
    - ${var.app_name}-gmail-oauth-client
    - ${var.app_name}-gmail-token
    - ${var.app_name}-ab-service-account
    - ${var.app_name}-serving-db-credentials

    VM pulls credentials automatically on every deploy/restart.
    You never need to copy credentials manually again.

    === Security Notes ===

    - Ports 3000/8000 are NOT exposed (blocked by firewall)
    - All traffic goes through nginx on 80/443
    - SSH available via IAP only (requires gcloud auth)
    - Automatic security updates enabled
    - Daily backups to: gs://${google_storage_bucket.catscan.name}/backups/

  EOT
}

output "firewall_rules" {
  description = "Active firewall rules (for verification)"
  value = {
    http  = "tcp:80 from 0.0.0.0/0"
    https = var.enable_https ? "tcp:443 from 0.0.0.0/0" : "disabled"
    ssh   = length(var.allowed_ssh_cidrs) > 0 ? "tcp:22 from ${join(", ", var.allowed_ssh_cidrs)}" : "disabled (use IAP)"
    iap   = "tcp:22 from 35.235.240.0/20 (Google IAP)"
    note  = "Ports 3000/8000 are BLOCKED - not exposed"
  }
}

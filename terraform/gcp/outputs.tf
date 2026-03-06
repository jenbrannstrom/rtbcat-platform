# Cat-Scan GCP Infrastructure Outputs

output "instance_name" {
  description = "Name of the GCE instance"
  value       = google_compute_instance.catscan.name
}

output "instance_zone" {
  description = "Zone of the GCE instance"
  value       = google_compute_instance.catscan.zone
}

output "public_ip" {
  description = "Static public IP address"
  value       = google_compute_address.catscan.address
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

output "ssh_command" {
  description = "SSH command (via IAP - secure)"
  value       = "gcloud compute ssh ${google_compute_instance.catscan.name} --zone=${google_compute_instance.catscan.zone} --tunnel-through-iap"
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

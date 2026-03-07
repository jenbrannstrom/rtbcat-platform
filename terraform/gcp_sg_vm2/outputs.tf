output "sg_vm2_ip" {
  description = "Static IP for SG VM2"
  value       = google_compute_address.catscan_sg_vm2.address
}

output "sg_vm2_name" {
  description = "Instance name for SG VM2"
  value       = google_compute_instance.catscan_sg_vm2.name
}

output "sg2_serving_db_mode" {
  description = "Serving DB mode used by SG2 (dedicated or shared)"
  value       = var.enable_dedicated_serving_db ? "dedicated" : "shared"
}

output "sg2_serving_db_secret_id" {
  description = "Secret Manager secret id used by SG2 startup for DB credentials"
  value       = local.effective_serving_db_secret_id
}

output "sg2_cloudsql_instance_name" {
  description = "Cloud SQL instance name used by SG2 cloud-sql-proxy"
  value       = local.effective_cloudsql_instance_name
}

output "sg2_dedicated_cloudsql_connection_name" {
  description = "Connection name of SG2 dedicated Cloud SQL instance when enabled"
  value       = var.enable_dedicated_serving_db ? google_sql_database_instance.sg2_serving[0].connection_name : null
}

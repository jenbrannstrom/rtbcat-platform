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

output "gcs_bucket" {
  description = "Cloud Storage bucket for backups and data"
  value       = google_storage_bucket.catscan.name
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

output "ssh_command_direct" {
  description = "Direct SSH command (only if allowed_ssh_cidrs configured)"
  value       = length(var.allowed_ssh_cidrs) > 0 ? "ssh ubuntu@${google_compute_address.catscan.address}" : "Direct SSH disabled - use IAP"
}

output "next_steps" {
  description = "Post-deployment instructions"
  value       = <<-EOT

    === Cat-Scan GCP Deployment Complete ===

    1. Wait 3-5 minutes for the startup script to complete

    2. Check startup progress:
       gcloud compute ssh ${google_compute_instance.catscan.name} --zone=${google_compute_instance.catscan.zone} --tunnel-through-iap
       sudo tail -f /var/log/catscan-setup.log

    3. Point DNS A record to: ${google_compute_address.catscan.address}
       Domain: ${var.domain_name != "" ? var.domain_name : "(not configured)"}

    4. Upload Google credentials:
       gcloud compute scp google-credentials.json ${google_compute_instance.catscan.name}:/tmp/ --zone=${google_compute_instance.catscan.zone}
       gcloud compute ssh ${google_compute_instance.catscan.name} --zone=${google_compute_instance.catscan.zone} -- "sudo mv /tmp/google-credentials.json /home/catscan/.catscan/credentials/"

    5. Access your dashboard:
       ${var.enable_https && var.domain_name != "" ? "https://${var.domain_name}" : "http://${google_compute_address.catscan.address}"}

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

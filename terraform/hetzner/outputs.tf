output "app_public_ipv4" {
  description = "Stable app IPv4. Do not update production DNS during provisioning or rehearsal."
  value       = hcloud_primary_ip.app.ip_address
}

output "app_private_ipv4" {
  description = "App address on the Hetzner private network."
  value       = var.app_private_ip
}

output "app_data_volume_id" {
  description = "Hetzner app-data volume ID. Server backups do not include this volume."
  value       = hcloud_volume.app_data.id
}

output "app_data_volume_automount" {
  description = "Expected app-data automount path before it is moved to the stable application path."
  value       = "/mnt/HC_Volume_${hcloud_volume.app_data.id}"
}

output "database_public_ipv4" {
  description = "Database host public IPv4 for operator bootstrap; PostgreSQL is not exposed on it."
  value       = hcloud_primary_ip.database.ip_address
}

output "database_private_ipv4" {
  description = "PostgreSQL endpoint for the app host."
  value       = var.database_private_ip
}

output "database_volume_id" {
  description = "Hetzner database volume ID. Server backups do not include this volume."
  value       = hcloud_volume.database.id
}

output "database_volume_device" {
  description = "Linux device reported by Hetzner for the attached database volume."
  value       = hcloud_volume.database.linux_device
}

output "database_volume_automount" {
  description = "Expected automount path created by Hetzner's Ubuntu image. Confirm it before installing PostgreSQL."
  value       = "/mnt/HC_Volume_${hcloud_volume.database.id}"
}

output "rehearsal_dump_volume_id" {
  description = "Temporary directory-dump volume ID, or null when disabled. Unmount before removing it."
  value       = try(hcloud_volume.rehearsal_dump[0].id, null)
}

output "rehearsal_dump_volume_automount" {
  description = "Expected temporary dump-volume automount path, or null when disabled."
  value       = try("/mnt/HC_Volume_${hcloud_volume.rehearsal_dump[0].id}", null)
}

output "next_checkpoint" {
  description = "The next migration part after provisioning this foundation."
  value       = "Install Tailscale and PostgreSQL 15.17, mount the data volume predictably, and configure independent WAL backups before restoring data."
}

output "sg_vm2_ip" {
  description = "Static IP for SG VM2"
  value       = google_compute_address.catscan_sg_vm2.address
}

output "sg_vm2_name" {
  description = "Instance name for SG VM2"
  value       = google_compute_instance.catscan_sg_vm2.name
}

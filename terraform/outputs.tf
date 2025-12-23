# Cat-Scan Terraform Outputs

output "dashboard_url" {
  description = "URL to access the Cat-Scan dashboard"
  value       = "http://${aws_eip.catscan.public_ip}:3000"
}

output "api_url" {
  description = "URL to access the Cat-Scan API"
  value       = "http://${aws_eip.catscan.public_ip}:8000"
}

output "api_docs_url" {
  description = "URL to access the API documentation"
  value       = "http://${aws_eip.catscan.public_ip}:8000/docs"
}

output "instance_id" {
  description = "EC2 instance ID"
  value       = aws_instance.catscan.id
}

output "public_ip" {
  description = "Public IP address (Elastic IP)"
  value       = aws_eip.catscan.public_ip
}

output "s3_bucket" {
  description = "S3 bucket for CSV archival"
  value       = aws_s3_bucket.catscan.id
}

output "ssh_command" {
  description = "SSH command (if SSH key was provided)"
  value       = var.ssh_key_name != "" ? "ssh -i ~/.ssh/${var.ssh_key_name}.pem ec2-user@${aws_eip.catscan.public_ip}" : "SSH disabled (no key provided)"
}

output "next_steps" {
  description = "Next steps after deployment"
  value       = <<-EOT

    === Cat-Scan Deployment Complete ===

    1. Wait 2-3 minutes for Docker containers to start

    2. Access your dashboard:
       ${aws_eip.catscan.public_ip}:3000

    3. Upload Google credentials:
       - Go to Setup page in dashboard
       - Upload your google-credentials.json
       - Or SSH and place file at: /home/catscan/.catscan/credentials/google-credentials.json

    4. Import your first CSV report:
       - Go to Import page
       - Upload your Authorized Buyers CSV export

    Data Privacy:
    - All data stays on YOUR AWS account
    - Database stored on encrypted EBS volume
    - S3 bucket is private with encryption enabled
    - No data is shared with anyone

  EOT
}

# Cat-Scan Terraform Outputs

locals {
  https_next_steps = <<-EOT

    === Cat-Scan HTTPS Deployment Complete ===

    1. Point your DNS A record to: ${aws_eip.catscan.public_ip}
       Domain: ${var.domain_name}

    2. Wait 2-3 minutes for containers to start and SSL certificate

    3. Access your dashboard:
       https://${var.domain_name}

    4. Set API key for security:
       ssh ec2-user@${aws_eip.catscan.public_ip}
       cd /home/catscan/rtbcat-platform
       API_KEY=$(openssl rand -base64 32)
       echo "CATSCAN_API_KEY=$API_KEY" >> .env
       docker compose -f docker-compose.production.yml restart
       echo "Your API key: $API_KEY"

    5. Upload Google credentials via SCP:
       scp google-credentials.json ec2-user@${aws_eip.catscan.public_ip}:/tmp/
       ssh ec2-user@${aws_eip.catscan.public_ip} \
         "sudo mv /tmp/google-credentials.json /home/catscan/.catscan/credentials/"

  EOT

  http_next_steps = <<-EOT

    === Cat-Scan HTTP Deployment Complete ===

    1. Wait 2-3 minutes for Docker containers to start

    2. Access your dashboard:
       http://${aws_eip.catscan.public_ip}:3000

    3. Upload Google credentials:
       - Go to Setup page in dashboard
       - Upload your google-credentials.json

    4. Import your first CSV report:
       - Go to Import page
       - Upload your Authorized Buyers CSV export

    Note: For HTTPS, set domain_name and enable_https = true

  EOT
}

output "dashboard_url" {
  description = "URL to access the Cat-Scan dashboard"
  value       = var.enable_https && var.domain_name != "" ? "https://${var.domain_name}" : "http://${aws_eip.catscan.public_ip}:3000"
}

output "api_url" {
  description = "URL to access the Cat-Scan API"
  value       = var.enable_https && var.domain_name != "" ? "https://${var.domain_name}/api" : "http://${aws_eip.catscan.public_ip}:8000"
}

output "api_docs_url" {
  description = "URL to access the API documentation"
  value       = var.enable_https && var.domain_name != "" ? "https://${var.domain_name}/api/docs" : "http://${aws_eip.catscan.public_ip}:8000/docs"
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

output "https_enabled" {
  description = "Whether HTTPS is enabled"
  value       = var.enable_https
}

output "domain_name" {
  description = "Domain name (if configured)"
  value       = var.domain_name != "" ? var.domain_name : "Not configured"
}

output "next_steps" {
  description = "Next steps after deployment"
  value       = var.enable_https && var.domain_name != "" ? local.https_next_steps : local.http_next_steps
}

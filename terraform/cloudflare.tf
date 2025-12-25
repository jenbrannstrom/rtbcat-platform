# Cloudflare DNS Configuration for Cat-Scan
#
# Prerequisites:
# 1. Create Cloudflare API token at https://dash.cloudflare.com/profile/api-tokens
#    - Permissions: Zone > DNS > Edit
#    - Zone Resources: Include > Specific zone > rtb.cat
# 2. Get Zone ID from Cloudflare dashboard (rtb.cat overview page, right sidebar)
# 3. Set in terraform.tfvars:
#    cloudflare_api_token = "your-token"
#    cloudflare_zone_id = "your-zone-id"

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# DNS A record pointing to EC2 instance
resource "cloudflare_record" "catscan" {
  count   = var.cloudflare_api_token != "" && var.domain_name != "" ? 1 : 0
  zone_id = var.cloudflare_zone_id
  name    = local.subdomain
  content = aws_eip.catscan.public_ip
  type    = "A"
  ttl     = 300
  proxied = false  # Direct connection for Let's Encrypt validation
  comment = "Cat-Scan QPS Optimizer"
}

locals {
  # Extract subdomain from domain_name (e.g., "scan" from "scan.rtb.cat")
  subdomain = var.domain_name != "" ? split(".", var.domain_name)[0] : ""
}

# Output the DNS record status
output "dns_record" {
  description = "Cloudflare DNS record"
  value       = var.cloudflare_api_token != "" && var.domain_name != "" ? {
    name    = var.domain_name
    type    = "A"
    content = aws_eip.catscan.public_ip
    status  = "Created automatically"
  } : {
    name    = var.domain_name
    type    = "A"
    content = aws_eip.catscan.public_ip
    status  = "Manual setup required - set cloudflare_api_token"
  }
}

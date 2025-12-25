# Cat-Scan Cloud Deployment Guide

**Version:** 3.0 | **Created:** December 19, 2025 | **Updated:** December 25, 2025

Production deployment guide for Cat-Scan QPS Optimizer. Supports AWS (primary) with GCP instructions coming soon.

---

## Overview

Cat-Scan is deployed as a containerized application with:
- **Dashboard** (Next.js) - Web UI on port 3000
- **API** (FastAPI) - Backend on port 8000
- **Database** (SQLite) - Persistent storage
- **Authentication** - API key for backend, optional OAuth for dashboard

### Architecture

```
                                    ┌─────────────────────────────────────┐
                                    │         Cloud Instance              │
┌──────────────┐                    │                                     │
│   Browser    │───── HTTPS ───────▶│  ┌─────────────┐  ┌─────────────┐  │
│   (User)     │        :443        │  │  Dashboard  │  │    API      │  │
└──────────────┘                    │  │  (Next.js)  │──│  (FastAPI)  │  │
                                    │  │   :3000     │  │   :8000     │  │
                                    │  └─────────────┘  └─────────────┘  │
                                    │         │                │         │
                                    │         └───────┬────────┘         │
                                    │                 ▼                  │
                                    │        ┌─────────────────┐         │
                                    │        │  SQLite + Data  │         │
                                    │        │  ~/.catscan/    │         │
                                    │        └─────────────────┘         │
                                    └─────────────────────────────────────┘
```

---

## Deployment Options

| Option | Complexity | Cost | Best For |
|--------|------------|------|----------|
| **A. Single EC2 + Caddy** | Low | ~$20/mo | Personal/small team |
| **B. EC2 + ALB + ACM** | Medium | ~$35/mo | Production with AWS-native SSL |
| **C. ECS Fargate** | High | ~$50/mo | Auto-scaling, enterprise |

**Recommended:** Option A for most users.

---

## Option A: Single EC2 with Caddy (Recommended)

Caddy provides automatic HTTPS with Let's Encrypt certificates.

### Prerequisites

1. **Domain name** pointed to your server (e.g., `catscan.yourdomain.com`)
2. **AWS Account** with CLI configured
3. **Terraform** installed (v1.0+)

### Step 1: Deploy Infrastructure

```bash
cd /home/jen/Documents/rtbcat-platform/terraform

# Configure your domain
cat > terraform.tfvars << 'EOF'
domain_name = "catscan.yourdomain.com"
ssh_public_key_path = "~/.ssh/id_ed25519.pub"
enable_https = true
EOF

# Deploy
~/bin/terraform init
~/bin/terraform plan -out=tfplan
~/bin/terraform apply tfplan
```

### Step 2: Point DNS to Server

After deployment, Terraform outputs the public IP:

```bash
~/bin/terraform output public_ip
# Example: 18.185.146.184
```

Create an A record in your DNS:
- **Name:** `catscan` (or your subdomain)
- **Type:** A
- **Value:** `<public_ip>`
- **TTL:** 300

### Step 3: Configure Authentication

SSH to the server and set the API key:

```bash
ssh ec2-user@catscan.yourdomain.com

# Generate and set API key
API_KEY=$(openssl rand -base64 32)
echo "CATSCAN_API_KEY=$API_KEY" | sudo tee -a /home/catscan/.env
echo "Your API key: $API_KEY"

# Restart containers to pick up the key
cd /home/catscan/rtbcat-platform
sudo docker compose restart
```

Save the API key securely - you'll need it for API access.

### Step 4: Upload Credentials

```bash
# Upload Google Authorized Buyers credentials
scp google-credentials.json ec2-user@catscan.yourdomain.com:/tmp/
ssh ec2-user@catscan.yourdomain.com \
  "sudo mv /tmp/google-credentials.json /home/catscan/.catscan/credentials/ && \
   sudo chown catscan:catscan /home/catscan/.catscan/credentials/google-credentials.json"

# Upload Gmail OAuth credentials (for auto-import)
scp ~/.catscan/credentials/gmail-*.json ec2-user@catscan.yourdomain.com:/tmp/
ssh ec2-user@catscan.yourdomain.com \
  "sudo mv /tmp/gmail-*.json /home/catscan/.catscan/credentials/ && \
   sudo chown catscan:catscan /home/catscan/.catscan/credentials/gmail-*.json"
```

### Step 5: Access Your Deployment

| Service | URL |
|---------|-----|
| Dashboard | `https://catscan.yourdomain.com` |
| API Docs | `https://catscan.yourdomain.com/api/docs` |
| Health Check | `https://catscan.yourdomain.com/api/health` |

---

## Security Configuration

### API Key Authentication

The API uses bearer token authentication when `CATSCAN_API_KEY` is set:

```bash
# API calls require the Authorization header
curl -H "Authorization: Bearer $API_KEY" \
  https://catscan.yourdomain.com/api/health

# Public endpoints (no auth required):
# - /api/health
# - /api/docs
# - /api/openapi.json
```

### Dashboard Authentication (Optional)

For dashboard access control, options include:

1. **Basic Auth via Caddy** (simple):
   ```
   # In Caddyfile
   catscan.yourdomain.com {
     basicauth /* {
       admin $2a$14$... # bcrypt hash
     }
     reverse_proxy dashboard:3000
   }
   ```

2. **OAuth/SSO** (enterprise):
   - Integrate with Google Workspace, Okta, or Auth0
   - Requires dashboard code changes

3. **VPN/IP Allowlist** (network-level):
   - Restrict Security Group to office IPs
   - Use AWS Client VPN

---

## Infrastructure Details

### Terraform Resources Created

| Resource | Purpose |
|----------|---------|
| `aws_instance` | EC2 t3.small running Amazon Linux 2023 |
| `aws_eip` | Static IP address |
| `aws_security_group` | Firewall (22, 80, 443) |
| `aws_s3_bucket` | Data backup storage |
| `aws_key_pair` | SSH access |

### Security Group Rules

| Port | Protocol | Source | Purpose |
|------|----------|--------|---------|
| 22 | TCP | Your IP | SSH access |
| 80 | TCP | 0.0.0.0/0 | HTTP → HTTPS redirect |
| 443 | TCP | 0.0.0.0/0 | HTTPS access |

### File Locations on Server

```
/home/catscan/
├── rtbcat-platform/          # Application code
│   ├── docker-compose.yml
│   ├── creative-intelligence/
│   └── dashboard/
├── .catscan/                  # Data directory
│   ├── catscan.db            # SQLite database
│   ├── credentials/          # Google/Gmail creds
│   └── imports/              # Downloaded CSVs
└── .env                       # Environment variables
```

---

## Operations

### Daily Gmail Import

Cron job runs daily at 6 AM UTC:

```bash
# Check cron status
sudo cat /etc/cron.d/gmail-import

# Run manually
sudo docker exec catscan-api python scripts/gmail_import.py

# View logs
sudo tail -f /var/log/gmail-import.log
```

### Container Management

```bash
# View status
sudo docker ps

# View logs
sudo docker logs -f catscan-api
sudo docker logs -f catscan-dashboard

# Restart services
cd /home/catscan/rtbcat-platform
sudo docker compose restart

# Rebuild after code changes
sudo docker compose up -d --build
```

### Database Backup

```bash
# Manual backup to S3
sudo docker exec catscan-api python -c "
import shutil
import boto3
from datetime import datetime

# Copy database
shutil.copy('/home/catscan/.catscan/catscan.db', '/tmp/backup.db')

# Upload to S3
s3 = boto3.client('s3')
s3.upload_file('/tmp/backup.db', 'catscan-production-data-xxx',
               f'backups/catscan-{datetime.now():%Y%m%d-%H%M%S}.db')
"
```

### Update Deployment

```bash
# SSH to server
ssh ec2-user@catscan.yourdomain.com

# Pull latest code
cd /home/catscan/rtbcat-platform
sudo git pull origin unified-platform

# Rebuild and restart
sudo docker compose up -d --build
```

---

## Troubleshooting

### Check Service Health

```bash
# API health
curl https://catscan.yourdomain.com/api/health

# Container status
sudo docker ps -a

# Container logs
sudo docker logs catscan-api --tail 100
sudo docker logs catscan-dashboard --tail 100
```

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| 502 Bad Gateway | Container not running | `sudo docker compose up -d` |
| SSL certificate error | DNS not propagated | Wait 5-10 min, check DNS |
| API returns 401 | Missing/wrong API key | Check `Authorization: Bearer` header |
| Dashboard shows no data | API key not set in dashboard env | Set `NEXT_PUBLIC_API_KEY` |
| Gmail import fails | Token expired | Re-run OAuth flow locally, copy new token |

### Reset Everything

```bash
# Nuclear option: destroy and recreate
cd /home/jen/Documents/rtbcat-platform/terraform
~/bin/terraform destroy
~/bin/terraform apply
```

---

## Cost Breakdown

| Component | Monthly Cost |
|-----------|--------------|
| EC2 t3.small | ~$15 |
| EBS 30GB | ~$2.40 |
| Elastic IP | Free (attached) |
| S3 storage | ~$1-3 |
| Data transfer | ~$1-5 |
| **Total** | **~$20-25/month** |

### Cost Optimization

- **Stop when not in use:** `aws ec2 stop-instances --instance-ids i-xxx`
- **Use Spot instances:** 60-70% savings (with interruption risk)
- **Reserved instances:** 30-40% savings for 1-year commitment

---

## GCP Deployment (Coming Soon)

GCP deployment will use:
- **Compute Engine** (equivalent to EC2)
- **Cloud SQL** or persistent disk for SQLite
- **Cloud CDN** for static assets
- **Identity-Aware Proxy** for authentication

See `docs/GCP_DEPLOYMENT_PLAN.md` (to be created).

---

## Migration Notes

### From SSH Tunnel Setup

If migrating from the SSH tunnel approach:

1. **Export data from old deployment:**
   ```bash
   ssh ec2-user@old-server "sudo docker exec catscan-api cat /data/catscan.db" > backup.db
   ```

2. **Import to new deployment:**
   ```bash
   scp backup.db ec2-user@new-server:/tmp/
   ssh ec2-user@new-server "sudo mv /tmp/backup.db /home/catscan/.catscan/catscan.db"
   ```

3. **Update DNS** to point to new server

4. **Destroy old infrastructure**

---

## Current Deployment Status

### Active Instance

| Property | Value |
|----------|-------|
| **IP** | `18.185.146.184` |
| **Region** | eu-central-1 (Frankfurt) |
| **Instance** | t3.small |
| **Status** | Running (SSH tunnel mode - legacy) |

### Pending Migration

- [ ] Register domain or subdomain
- [ ] Update Terraform for Caddy/HTTPS
- [ ] Migrate to proper auth
- [ ] Update dashboard to use API key

---

*Document maintained by: Claude Code*
*Last updated: December 25, 2025*

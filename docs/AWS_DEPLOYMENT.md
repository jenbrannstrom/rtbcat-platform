# Cat-Scan AWS Deployment Plan

**Version:** 1.0 | **Created:** December 19, 2025

This document outlines the complete plan for deploying Cat-Scan Creative Intelligence to AWS with S3 archival and 90-day data retention.

---

## Executive Summary

**Goal:** Deploy Cat-Scan to AWS EC2 with automated daily CSV imports and long-term archival.

| Component | Solution | Monthly Cost |
|-----------|----------|--------------|
| Compute | EC2 t3.small | ~$15/month |
| Storage | 30GB EBS | ~$2.40/month |
| CSV Archive | S3 with lifecycle | ~$1-3 for 36GB/year |
| **Total** | | **~$18-20/month** |

---

## Quick Reference - How to Connect

### Server Details

| Property | Value |
|----------|-------|
| **Domain** | `scan.rtb.cat` |
| **Public IP** | `52.58.210.20` |
| **Region** | `eu-central-1` (Frankfurt) |
| **Instance ID** | `i-021da86a0d0a38603` |
| **Instance Type** | t3.small (2 vCPU, 2GB RAM) |
| **OS** | Amazon Linux 2023 |
| **HTTPS** | Port 443 (via Caddy) |

### SSH Access

```bash
# Connect to the server using your local SSH key
ssh -i ~/.ssh/id_ed25519 ec2-user@52.58.210.20
```

**Key Details:**
| Property | Value |
|----------|-------|
| Local Key | `~/.ssh/id_ed25519` |
| Key Pair Name (AWS) | `jen-laptop` |
| SSH User | `ec2-user` |
| Backup Key | AWS Secrets Manager: `catscan-deploy-key` |

### AWS Credentials (`~/.aws/credentials`)

The file `~/.aws/credentials` contains your AWS access keys that allow the AWS CLI (and any AWS SDK) to authenticate with AWS services:

```ini
[default]
aws_access_key_id = AKIAXXXXXXXXXXXXXXXX
aws_secret_access_key = xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**What it does:**
- **aws_access_key_id**: Your AWS account identifier (like a username)
- **aws_secret_access_key**: Your secret key (like a password) - never share this!

**How it's used:**
- All `aws` CLI commands use these credentials automatically
- Retrieves the SSH key from Secrets Manager
- Uploads/downloads files from S3
- Manages EC2 instances, security groups, etc.

**Security Notes:**
- This file should have permissions `600` (owner read/write only)
- Never commit this file to git (it's in `.gitignore`)
- These are IAM user credentials, not root account credentials
- Can be rotated in AWS IAM Console if compromised

### API Access

```bash
# Health check (via HTTPS domain)
curl https://scan.rtb.cat/health

# API documentation (Swagger UI)
# Open in browser: https://scan.rtb.cat/docs

# Import status
curl https://scan.rtb.cat/gmail/status

# List recent imports
curl https://scan.rtb.cat/uploads/history
```

### Service Management (Docker-based)

```bash
# SSH to server first (retrieve key from Secrets Manager - see SSH Access section above)
ssh -i ~/.ssh/id_ed25519 ec2-user@52.58.210.20

# Check container status
docker ps

# View logs (live)
docker logs -f catscan-api
docker logs -f catscan-dashboard

# View recent logs
docker logs catscan-api --tail 100

# Restart containers
sudo -u catscan bash -c 'cd ~/rtbcat-platform && docker compose -f docker-compose.production.yml restart'

# Rebuild and restart (after code changes)
sudo -u catscan bash -c 'cd ~/rtbcat-platform && docker compose -f docker-compose.production.yml up -d --build'

# Stop all containers
sudo -u catscan bash -c 'cd ~/rtbcat-platform && docker compose -f docker-compose.production.yml down'

# Start all containers
sudo -u catscan bash -c 'cd ~/rtbcat-platform && docker compose -f docker-compose.production.yml up -d'
```

### File Locations (on server)

**Note:** App runs in Docker containers under the `catscan` user.

| Path | Contents |
|------|----------|
| `/home/catscan/rtbcat-platform/` | Git repo (source code) |
| `/home/catscan/.catscan/catscan.db` | SQLite database |
| `/home/catscan/.catscan/credentials/` | API credentials (service accounts) |
| `/home/catscan/.catscan/imports/` | Downloaded CSV files |

**Docker containers:**
| Container | Purpose |
|-----------|---------|
| `catscan-api` | Python FastAPI backend |
| `catscan-dashboard` | Next.js frontend |
| `catscan-caddy` | HTTPS reverse proxy |

### Manual Operations

```bash
# SSH into server first (retrieve key from Secrets Manager - see SSH Access section above)
ssh -i ~/.ssh/id_ed25519 ec2-user@52.58.210.20

# Activate virtual environment
cd /opt/catscan && source venv/bin/activate

# Run Gmail import manually
python scripts/gmail_import.py

# Run cleanup manually (dry-run first)
python scripts/cleanup_old_data.py --dry-run
python scripts/cleanup_old_data.py

# Check cron jobs
crontab -l

# View import log
tail -100 ~/.catscan/logs/gmail-import.log

# View cleanup log
tail -100 ~/.catscan/logs/cleanup.log
```

### S3 Archive Access

```bash
# List all archived files
aws s3 ls s3://rtbcat-csv-archive-frankfurt-328614522524/ --recursive --region eu-central-1

# List performance reports
aws s3 ls s3://rtbcat-csv-archive-frankfurt-328614522524/performance/ --recursive --region eu-central-1

# Download a specific file
aws s3 cp s3://rtbcat-csv-archive-frankfurt-328614522524/performance/2025/12/21/catscan-performance-2025-12-21.csv.gz ./ --region eu-central-1

# Decompress
gunzip catscan-performance-2025-12-21.csv.gz
```

### Auto-Deploy (GitHub Actions)

**Deployments are automatic!** Pushing to `unified-platform` branch triggers GitHub Actions to deploy.

**How it works:**
1. Push code to `unified-platform` branch
2. GitHub Actions SSHs to the server
3. Pulls latest code, rebuilds Docker containers, restarts

**View deployment status:**
- GitHub Actions: https://github.com/jenbrannstrom/rtbcat-platform/actions

**GitHub Secrets configured:**
| Secret | Value |
|--------|-------|
| `AWS_HOST` | `52.58.210.20` |
| `AWS_SSH_KEY` | SSH private key from laptop |

**Workflow file:** `.github/workflows/deploy.yml`

### Manual Deploy (if needed)

If you need to deploy manually without pushing to git:

```bash
# SSH to server (retrieve key from Secrets Manager first - see SSH Access section)
ssh -i ~/.ssh/id_ed25519 ec2-user@52.58.210.20

# Switch to catscan user and pull latest code
sudo su - catscan
cd ~/rtbcat-platform
git pull origin unified-platform

# Rebuild and restart containers
docker compose -f docker-compose.production.yml build
docker compose -f docker-compose.production.yml up -d

# Verify containers are running
docker ps

# Check logs if needed
docker logs catscan-api --tail 50
docker logs catscan-dashboard --tail 50
```

**Quick one-liner (from local machine):**
```bash
# First retrieve the key, then run:
ssh -i ~/.ssh/id_ed25519 ec2-user@52.58.210.20 "sudo -u catscan bash -c 'cd ~/rtbcat-platform && git pull origin unified-platform && docker compose -f docker-compose.production.yml build && docker compose -f docker-compose.production.yml up -d'"
```

### AWS Console Access

- **EC2 Console:** https://eu-central-1.console.aws.amazon.com/ec2/home?region=eu-central-1#Instances:instanceId=i-08758180a9d369fb7
- **S3 Console:** https://s3.console.aws.amazon.com/s3/buckets/rtbcat-csv-archive-frankfurt-328614522524?region=eu-central-1

### Troubleshooting

```bash
# Check if API is responding
curl -v https://scan.rtb.cat/health

# Check disk space
df -h

# Check memory usage
free -m

# Check running processes
ps aux | grep python

# Check if port 8000 is listening
sudo ss -tlnp | grep 8000

# Check security group allows traffic (from local)
nc -zv 52.58.210.20 443
nc -zv 52.58.210.20 22
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AWS Account (eu-central-1 - Frankfurt)      │
│                                                                     │
│  ┌─────────────────┐     ┌──────────────────────────────────────┐  │
│  │   S3 Bucket     │     │         EC2 t3.micro                 │  │
│  │                 │     │                                      │  │
│  │ rtbcat-csv-     │◄────│  ┌────────────────────────────────┐  │  │
│  │ archive-*       │     │  │     Cat-Scan FastAPI App       │  │  │
│  │                 │     │  │                                │  │  │
│  │ /performance/   │     │  │  - Gmail import (cron: daily)  │  │  │
│  │ /funnel-geo/    │     │  │  - API on port 8000            │  │  │
│  │ /funnel-pubs/   │     │  │  - SQLite (90-day retention)   │  │  │
│  │                 │     │  │  - S3 archival on import       │  │  │
│  └─────────────────┘     │  └────────────────────────────────┘  │  │
│                          │                                      │  │
│   Lifecycle Policy:      │  Cron Jobs:                          │  │
│   - 30 days → IA storage │  - 08:00 UTC: Gmail import           │  │
│   - Unlimited retention  │  - 02:00 UTC: 90-day cleanup         │  │
│                          │                                      │  │
│                          └──────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

External:
  Google Authorized Buyers → Gmail → Cat-Scan imports → S3 archive
```

---

## Existing AWS Resources (Frankfurt - eu-central-1)

The following resources exist in the Frankfurt region:

| Resource | ID/Name | Purpose |
|----------|---------|---------|
| SSH Key Pair | `jen-laptop` | SSH access to EC2 (private key in AWS Secrets Manager: `catscan-deploy-key`) |
| Security Group | `sg-00367df5f7826fd77` (catscan-sg) | Allows SSH (22) + HTTPS (443) |
| VPC | `vpc-05cc8303080eb9fa3` (default) | Network |
| S3 Bucket | `rtbcat-csv-archive-frankfurt-328614522524` | CSV archival with lifecycle |
| IAM Role | `catscan-ec2-role` | EC2 access to S3 |
| EC2 Instance | `i-021da86a0d0a38603` (catscan-production) | Running at 52.58.210.20, domain: scan.rtb.cat |

---

## Component 1: S3 CSV Archival

### Status: COMPLETED (Frankfurt)

**Bucket:** `rtbcat-csv-archive-frankfurt-328614522524`

**Structure:**
```
s3://rtbcat-csv-archive-frankfurt-328614522524/
├── performance/
│   ├── 2025/12/19/catscan-performance-2025-12-19.csv.gz
│   └── ...
├── funnel-geo/
│   ├── 2025/12/19/catscan-funnel-geo-2025-12-19.csv.gz
│   └── ...
└── funnel-publishers/
    ├── 2025/12/19/catscan-funnel-publishers-2025-12-19.csv.gz
    └── ...
```

**Lifecycle Policy (configured):**
- Days 0-30: Standard storage ($0.023/GB)
- Days 30+: Infrequent Access ($0.0125/GB) - 46% cheaper
- No expiration (keep forever for history reconstruction)

**Cost Estimate:**
| Data Volume | Monthly Cost |
|-------------|--------------|
| 36 GB (1 year) | ~$0.50-0.80 |
| 100 GB | ~$1.50-2.00 |
| 365 GB (10 years) | ~$5-6 |

---

## Component 2: EC2 Instance

### Configuration (Frankfurt)

| Setting | Value |
|---------|-------|
| AMI | Amazon Linux 2023 (ami-0b9f50ee4cf81e8d8) |
| Instance Type | t3.small (2 vCPU, 2GB RAM) |
| Storage | 30 GB gp3 EBS |
| Key Pair | jen-laptop |
| Security Group | catscan-production-sg (sg-0268d377b64d1996d) |
| Subnet | Default VPC public subnet |
| Public IP | 52.58.210.20 |
| Instance ID | i-021da86a0d0a38603 |

### Security Group Rules Required

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | Your IP | Server access |
| HTTP | 80 | 0.0.0.0/0 | Redirect to HTTPS |
| HTTPS | 443 | 0.0.0.0/0 | Dashboard & API (via Caddy) |

### IAM Role for EC2

Create an IAM role with these permissions:
- `AmazonS3FullAccess` (or scoped to the bucket)
- Attach to EC2 instance for S3 access without hardcoded credentials

---

## Component 3: Code Changes Required

### 3.1 S3 Archival on Import

**File:** `scripts/gmail_import.py`

**Changes:**
1. After downloading CSV from Gmail, upload to S3 before importing
2. Compress with gzip before upload
3. Use date-based path structure

**New Function:**
```python
def archive_to_s3(file_path: Path, report_type: str) -> str:
    """
    Archive CSV to S3 with gzip compression.

    Args:
        file_path: Local path to CSV file
        report_type: One of 'performance', 'funnel-geo', 'funnel-publishers'

    Returns:
        S3 URI of archived file
    """
    # Extract date from filename or use today
    # Compress file
    # Upload to s3://rtbcat-csv-archive-328614522524/{report_type}/{year}/{month}/{day}/
    # Return S3 URI
```

**Integration Point:**
- Call `archive_to_s3()` after CSV extraction, before database import
- Store S3 URI in import_history table for reference

### 3.2 90-Day Data Retention

**New File:** `scripts/cleanup_old_data.py`

**Purpose:** Delete database records older than 90 days while preserving S3 archives.

**Tables to Clean:**
| Table | Retention | Cleanup Query |
|-------|-----------|---------------|
| `rtb_daily` | 90 days | `DELETE FROM rtb_daily WHERE day < date('now', '-90 days')` |
| `rtb_funnel` | 90 days | `DELETE FROM rtb_funnel WHERE day < date('now', '-90 days')` |
| `performance_metrics` | 90 days | `DELETE FROM performance_metrics WHERE date < date('now', '-90 days')` |
| `import_history` | Keep all | No cleanup (small table, useful for auditing) |

**Features:**
- Dry-run mode to preview deletions
- Logging of deleted row counts
- VACUUM after deletion to reclaim space

### 3.3 Configuration Updates

**File:** `config/config_manager.py`

**New Settings:**
```python
@dataclass
class RetentionConfig:
    database_days: int = 90  # Days to keep in SQLite
    archive_enabled: bool = True  # Archive to S3 before cleanup

@dataclass
class S3ArchiveConfig:
    bucket: str = "rtbcat-csv-archive-frankfurt-328614522524"
    region: str = "eu-central-1"
    compress: bool = True  # gzip compression
```

---

## Component 4: Deployment Steps

### Step 1: Prepare the Application

```bash
# On local machine
cd /home/jen/Documents/rtbcat-platform/creative-intelligence

# Create deployment package
tar -czvf catscan-deploy.tar.gz \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    --exclude='*.db' \
    .
```

### Step 2: Launch EC2 Instance

```bash
# Create instance
aws ec2 run-instances \
    --image-id ami-0c44f651ab5e9285f \
    --instance-type t3.micro \
    --key-name rtb-gateway-key \
    --security-group-ids sg-0a84f5107d486995c \
    --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=catscan-server}]' \
    --iam-instance-profile Name=catscan-ec2-role

# Allocate Elastic IP (optional but recommended)
aws ec2 allocate-address --domain vpc
aws ec2 associate-address --instance-id <instance-id> --allocation-id <eip-alloc-id>
```

### Step 3: Configure EC2 Instance

```bash
# SSH into instance
ssh -i ~/.ssh/rtb-gateway-key.pem ec2-user@<public-ip>

# Install dependencies
sudo dnf update -y
sudo dnf install -y python3.11 python3.11-pip git

# Create app directory
sudo mkdir -p /opt/catscan
sudo chown ec2-user:ec2-user /opt/catscan

# Create data directory
mkdir -p ~/.catscan/credentials
mkdir -p ~/.catscan/imports
mkdir -p ~/.catscan/logs
```

### Step 4: Deploy Application

```bash
# From local machine - copy files
scp -i ~/.ssh/rtb-gateway-key.pem catscan-deploy.tar.gz ec2-user@<public-ip>:/opt/catscan/

# On EC2 - extract and setup
cd /opt/catscan
tar -xzvf catscan-deploy.tar.gz
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 5: Copy Credentials

```bash
# From local machine - copy Gmail credentials
scp -i ~/.ssh/rtb-gateway-key.pem \
    ~/.catscan/credentials/gmail-oauth-client.json \
    ~/.catscan/credentials/gmail-token.json \
    ec2-user@<public-ip>:~/.catscan/credentials/

# Copy service account if used
scp -i ~/.ssh/rtb-gateway-key.pem \
    ~/.catscan/credentials/*.json \
    ec2-user@<public-ip>:~/.catscan/credentials/
```

### Step 6: Setup Systemd Service

```bash
# On EC2
sudo cp /opt/catscan/catscan-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable catscan-api
sudo systemctl start catscan-api

# Verify
sudo systemctl status catscan-api
curl http://localhost:8000/health
```

### Step 7: Configure Cron Jobs

```bash
# On EC2 - edit crontab
crontab -e

# Add these lines:
# Gmail import at 8:00 AM UTC daily (after Google sends reports)
0 8 * * * /opt/catscan/venv/bin/python /opt/catscan/scripts/gmail_import.py >> ~/.catscan/logs/gmail-import.log 2>&1

# Database cleanup at 2:00 AM UTC on Sundays
0 2 * * 0 /opt/catscan/venv/bin/python /opt/catscan/scripts/cleanup_old_data.py >> ~/.catscan/logs/cleanup.log 2>&1
```

---

## Component 5: Data Recovery from S3

If you need to reconstruct historical data beyond the 90-day retention:

```bash
# List available archives
aws s3 ls s3://rtbcat-csv-archive-frankfurt-328614522524/performance/ --recursive --region eu-central-1

# Download specific date range
aws s3 cp s3://rtbcat-csv-archive-frankfurt-328614522524/performance/2025/06/ ./recovery/ --recursive --region eu-central-1

# Decompress and import
gunzip recovery/*.csv.gz
python -m qps.smart_importer recovery/*.csv
```

---

## Monitoring & Maintenance

### Health Checks

| Check | Command | Frequency |
|-------|---------|-----------|
| API Health | `curl http://localhost:8000/health` | Every 5 min |
| Disk Usage | `df -h /` | Daily |
| Import Status | `curl http://localhost:8000/gmail/status` | Daily |

### Log Files

| Log | Location | Purpose |
|-----|----------|---------|
| API logs | `journalctl -u catscan-api` | Application logs |
| Gmail import | `~/.catscan/logs/gmail-import.log` | Import history |
| Cleanup | `~/.catscan/logs/cleanup.log` | Retention cleanup |

### Alerts (Optional - Future)

- CloudWatch alarm on disk usage > 80%
- SNS notification on import failures
- Weekly cost report

---

## Cost Summary

### Current Costs (t3.small)

| Resource | Monthly Cost |
|----------|--------------|
| EC2 t3.small | ~$15.00 |
| EBS 30GB gp3 | ~$2.40 |
| S3 ~36GB | ~$0.80 |
| Data Transfer | ~$1.00 |
| **Total** | **~$19/month** |

---

## Implementation Checklist

- [x] Create S3 bucket with lifecycle policy (Frankfurt: rtbcat-csv-archive-frankfurt-328614522524)
- [x] Create IAM role for EC2 with S3 access (catscan-ec2-role with AmazonS3FullAccess)
- [x] Launch EC2 instance (i-08758180a9d369fb7 at 52.58.210.20, scan.rtb.cat)
- [x] Modify `gmail_import.py` to archive to S3
- [x] Create `cleanup_old_data.py` script
- [x] Update config manager with retention settings
- [x] Deploy application to EC2
- [x] Copy credentials to EC2
- [x] Configure systemd service (catscan-api.service)
- [x] Set up cron jobs (8:00 UTC daily import, 2:00 UTC Sunday cleanup)
- [x] Verify API works (https://scan.rtb.cat/health)
- [x] Verify S3 archival works (tested 2025-12-21)
- [ ] Test data recovery from S3
- [ ] Set up Gmail OAuth on EC2 (requires browser-based auth)

---

## Rollback Plan

If deployment fails:

1. **EC2 Issues:** Terminate instance, no data loss (S3 has archives)
2. **Import Issues:** Run import manually from laptop until fixed
3. **Database Corruption:** Restore from S3 archives

---

## Next Steps

1. ~~Review and approve this plan~~ DONE
2. ~~Implement code changes (S3 archival, cleanup script)~~ DONE
3. ~~Execute deployment steps~~ DONE
4. ~~Verify all systems operational~~ DONE
5. **Set up Gmail OAuth on EC2** - Required for automated imports
6. Monitor for first few days

### Setting Up Gmail OAuth

Gmail OAuth requires browser-based authentication. To complete setup:

```bash
# SSH to server (retrieve key from Secrets Manager first - see SSH Access section)
ssh -i ~/.ssh/id_ed25519 ec2-user@52.58.210.20

# Run the import script interactively
cd /opt/catscan && source venv/bin/activate
python scripts/gmail_import.py

# This will print a URL - open it in your browser
# Complete the OAuth flow and paste the authorization code
# The token will be saved to ~/.catscan/credentials/gmail-token.json
```

---

*Document maintained by: Claude Code*
*Last updated: January 6, 2026*
*Production deployment: scan.rtb.cat (52.58.210.20, Frankfurt, eu-central-1)*

**Note:** SSH key is stored in AWS Secrets Manager (`catscan-deploy-key`), not on local machine. Use AWS CLI to retrieve it before connecting.

**Note:** Server was recreated on Dec 30, 2025 after deployment docs were accidentally committed to GitHub. New server has fresh credentials.

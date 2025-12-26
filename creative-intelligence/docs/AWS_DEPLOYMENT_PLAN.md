# Cat-Scan AWS Deployment Plan

**Version:** 1.0 | **Created:** December 19, 2025

This document outlines the complete plan for deploying Cat-Scan Creative Intelligence to AWS with S3 archival and 90-day data retention.

---

## Executive Summary

**Goal:** Deploy Cat-Scan to AWS EC2 with automated daily CSV imports and long-term archival.

| Component | Solution | Monthly Cost |
|-----------|----------|--------------|
| Compute | EC2 t3.micro (free tier) | $0 (first year), ~$8 after |
| Storage | 30GB EBS | $0 (free tier) |
| CSV Archive | S3 with lifecycle | ~$1-3 for 36GB/year |
| **Total** | | **$0-3/month (year 1)** |

---

## Quick Reference - How to Connect

### Server Details

| Property | Value |
|----------|-------|
| **Public IP** | `63.176.52.250` |
| **Region** | `eu-central-1` (Frankfurt) |
| **Instance ID** | `i-018d0db64128c2bd3` |
| **Instance Type** | t3.micro (2 vCPU, 1GB RAM) |
| **OS** | Amazon Linux 2023 |
| **API Port** | 8000 |

### SSH Access

```bash
# Connect to the server (uses your local ~/.ssh/id_ed25519 key)
ssh ec2-user@63.176.52.250

# Or explicitly specify the key
ssh -i ~/.ssh/id_ed25519 ec2-user@63.176.52.250
```

### API Access

```bash
# Health check
curl http://63.176.52.250:8000/health

# API documentation (Swagger UI)
# Open in browser: http://63.176.52.250:8000/docs

# Import status
curl http://63.176.52.250:8000/gmail/status

# List recent imports
curl http://63.176.52.250:8000/uploads/history
```

### Service Management (on server)

```bash
# Check service status
sudo systemctl status catscan-api

# View logs (live)
sudo journalctl -u catscan-api -f

# View recent logs
sudo journalctl -u catscan-api -n 100

# Restart service
sudo systemctl restart catscan-api

# Stop/Start service
sudo systemctl stop catscan-api
sudo systemctl start catscan-api
```

### File Locations (on server)

| Path | Contents |
|------|----------|
| `/opt/catscan/` | Application code |
| `/opt/catscan/venv/` | Python virtual environment |
| `~/.catscan/catscan.db` | SQLite database |
| `~/.catscan/credentials/` | API credentials (service accounts) |
| `~/.catscan/imports/` | Downloaded CSV files |
| `~/.catscan/logs/` | Cron job logs |

### Manual Operations

```bash
# SSH into server first
ssh ec2-user@63.176.52.250

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

### Redeploy Application

```bash
# On local machine - create package and upload
cd /home/jen/Documents/rtbcat-platform/creative-intelligence
tar -czf /tmp/catscan-deploy.tar.gz --exclude='*.pyc' --exclude='__pycache__' --exclude='.git' --exclude='*.db' --exclude='venv' .
scp /tmp/catscan-deploy.tar.gz ec2-user@63.176.52.250:/tmp/

# On server - extract and restart
ssh ec2-user@63.176.52.250
cd /opt/catscan
tar -xzf /tmp/catscan-deploy.tar.gz
sudo systemctl restart catscan-api
```

### AWS Console Access

- **EC2 Console:** https://eu-central-1.console.aws.amazon.com/ec2/home?region=eu-central-1#Instances:instanceId=i-018d0db64128c2bd3
- **S3 Console:** https://s3.console.aws.amazon.com/s3/buckets/rtbcat-csv-archive-frankfurt-328614522524?region=eu-central-1

### Troubleshooting

```bash
# Check if API is responding
curl -v http://63.176.52.250:8000/health

# Check disk space
df -h

# Check memory usage
free -m

# Check running processes
ps aux | grep python

# Check if port 8000 is listening
sudo ss -tlnp | grep 8000

# Check security group allows traffic (from local)
nc -zv 63.176.52.250 8000
nc -zv 63.176.52.250 22
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
| SSH Key Pair | `catscan-frankfurt-key` | SSH access to EC2 (uses local ~/.ssh/id_ed25519) |
| Security Group | `sg-00367df5f7826fd77` (catscan-sg) | Allows SSH (22) + HTTP (8000) |
| VPC | `vpc-05cc8303080eb9fa3` (default) | Network |
| S3 Bucket | `rtbcat-csv-archive-frankfurt-328614522524` | CSV archival with lifecycle |
| IAM Role | `catscan-ec2-role` | EC2 access to S3 |
| EC2 Instance | `i-018d0db64128c2bd3` (catscan-server) | Running at 63.176.52.250 |

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
| Instance Type | t3.micro (2 vCPU, 1GB RAM) |
| Storage | 30 GB gp3 EBS |
| Key Pair | catscan-frankfurt-key |
| Security Group | catscan-sg (sg-00367df5f7826fd77) |
| Subnet | Default VPC public subnet |
| Public IP | 63.176.52.250 |
| Instance ID | i-018d0db64128c2bd3 |

### Security Group Rules Required

| Type | Port | Source | Purpose |
|------|------|--------|---------|
| SSH | 22 | Your IP | Server access |
| HTTP | 8000 | 0.0.0.0/0 (or restricted) | API access |
| HTTPS | 443 | 0.0.0.0/0 | Future: SSL termination |

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

### Year 1 (Free Tier)

| Resource | Monthly Cost |
|----------|--------------|
| EC2 t3.micro | $0 (750 hrs free) |
| EBS 30GB gp3 | $0 (30GB free) |
| S3 ~36GB | $0.50-1.00 |
| Data Transfer | $0 (minimal) |
| **Total** | **~$1/month** |

### After Free Tier

| Resource | Monthly Cost |
|----------|--------------|
| EC2 t3.micro | ~$7.60 |
| EBS 30GB gp3 | ~$2.40 |
| S3 ~36GB | ~$0.80 |
| Data Transfer | ~$1.00 |
| **Total** | **~$12/month** |

---

## Implementation Checklist

- [x] Create S3 bucket with lifecycle policy (Frankfurt: rtbcat-csv-archive-frankfurt-328614522524)
- [x] Create IAM role for EC2 with S3 access (catscan-ec2-role with AmazonS3FullAccess)
- [x] Launch EC2 instance (i-018d0db64128c2bd3 at 63.176.52.250)
- [x] Modify `gmail_import.py` to archive to S3
- [x] Create `cleanup_old_data.py` script
- [x] Update config manager with retention settings
- [x] Deploy application to EC2
- [x] Copy credentials to EC2
- [x] Configure systemd service (catscan-api.service)
- [x] Set up cron jobs (8:00 UTC daily import, 2:00 UTC Sunday cleanup)
- [x] Verify API works (http://63.176.52.250:8000/health)
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
# SSH to server
ssh ec2-user@63.176.52.250

# Run the import script interactively
cd /opt/catscan && source venv/bin/activate
python scripts/gmail_import.py

# This will print a URL - open it in your browser
# Complete the OAuth flow and paste the authorization code
# The token will be saved to ~/.catscan/credentials/gmail-token.json
```

---

*Document maintained by: Claude Code*
*Last updated: December 21, 2025*
*Deployment completed: December 21, 2025 (Frankfurt, eu-central-1)*

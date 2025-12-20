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

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AWS Account (ap-south-1)                    │
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

## Existing AWS Resources (Reuse)

The following resources already exist in the account and will be reused:

| Resource | ID/Name | Purpose |
|----------|---------|---------|
| SSH Key Pair | `rtb-gateway-key` | SSH access to EC2 |
| Security Group | `sg-0a84f5107d486995c` (rtb-gateway-sg) | Allows SSH + HTTP |
| VPC | `vpc-0cc69037ad33c9149` (default) | Network |
| S3 Bucket | `rtbcat-csv-archive-328614522524` | CSV archival (created) |

---

## Component 1: S3 CSV Archival

### Status: COMPLETED

**Bucket:** `rtbcat-csv-archive-328614522524`

**Structure:**
```
s3://rtbcat-csv-archive-328614522524/
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

### Configuration

| Setting | Value |
|---------|-------|
| AMI | Amazon Linux 2023 (ami-0c44f651ab5e9285f) |
| Instance Type | t3.micro (2 vCPU, 1GB RAM) |
| Storage | 30 GB gp3 EBS |
| Key Pair | rtb-gateway-key |
| Security Group | rtb-gateway-sg |
| Subnet | Default VPC public subnet |
| Public IP | Enabled (Elastic IP recommended) |

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
    bucket: str = "rtbcat-csv-archive-328614522524"
    region: str = "ap-south-1"
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
aws s3 ls s3://rtbcat-csv-archive-328614522524/performance/ --recursive

# Download specific date range
aws s3 cp s3://rtbcat-csv-archive-328614522524/performance/2025/06/ ./recovery/ --recursive

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

- [x] Create S3 bucket with lifecycle policy
- [ ] Create IAM role for EC2 with S3 access
- [ ] Launch EC2 instance
- [ ] Modify `gmail_import.py` to archive to S3
- [ ] Create `cleanup_old_data.py` script
- [ ] Update config manager with retention settings
- [ ] Deploy application to EC2
- [ ] Copy credentials to EC2
- [ ] Configure systemd service
- [ ] Set up cron jobs
- [ ] Verify Gmail import works
- [ ] Verify S3 archival works
- [ ] Test data recovery from S3

---

## Rollback Plan

If deployment fails:

1. **EC2 Issues:** Terminate instance, no data loss (S3 has archives)
2. **Import Issues:** Run import manually from laptop until fixed
3. **Database Corruption:** Restore from S3 archives

---

## Next Steps

1. Review and approve this plan
2. Implement code changes (S3 archival, cleanup script)
3. Execute deployment steps
4. Verify all systems operational
5. Monitor for first few days

---

*Document maintained by: Claude Code*
*Last updated: December 19, 2025*

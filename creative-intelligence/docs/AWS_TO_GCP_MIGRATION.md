# Cat-Scan: AWS to GCP Migration Plan

**Created:** December 24, 2025
**Status:** Planning

---

## Executive Summary

Migrate Cat-Scan from AWS to Google Cloud Platform (GCP). This makes more sense since:
- The app integrates with Google Authorized Buyers API
- Gmail OAuth is already configured in GCP
- Simpler credential management (one cloud provider)
- Potential for tighter Google API integration

---

## Phase 1: AWS Resource Inventory

### Terraform-Managed Resources (eu-central-1)

| Resource Type | Resource Name/ID | Purpose |
|---------------|------------------|---------|
| EC2 Instance | `i-08758180a9d369fb7` | App server |
| Elastic IP | `18.185.146.184` | Static IP |
| S3 Bucket | `catscan-production-data-b18d05c7` | Data storage |
| Security Group | `catscan-sg` | Firewall rules |
| IAM Role | `catscan-production-role` | EC2 permissions |
| IAM Instance Profile | `catscan-production-profile` | Role attachment |

### Manually Created Resources

| Resource Type | Resource Name | Region | Purpose |
|---------------|---------------|--------|---------|
| S3 Bucket | `rtbcat-csv-archive-328614522524` | us-east-1? | CSV archive |
| S3 Bucket | `rtbcat-csv-archive-frankfurt-328614522524` | eu-central-1 | CSV archive (active) |
| EC2 Key Pair | `jen-laptop` | eu-central-1 | SSH access |
| EC2 Key Pair | `catscan-frankfurt-key` | eu-central-1 | SSH access (old) |
| IAM Role | `catscan-ec2-role` | global | EC2 permissions (old) |
| IAM Instance Profile | `catscan-ec2-role` | global | Role attachment (old) |

### Data to Migrate

| Data | Location | Size (approx) |
|------|----------|---------------|
| SQLite Database | EC2: `/home/catscan/.catscan/catscan.db` | ~50MB |
| Gmail OAuth Token | EC2: `/home/catscan/.catscan/credentials/gmail-token.json` | 1KB |
| Archived CSVs | S3: `rtbcat-csv-archive-frankfurt-*` | ~100MB |

---

## Phase 2: GCP Infrastructure Setup

### GCP Equivalent Resources

| AWS Service | GCP Equivalent | Resource Name |
|-------------|----------------|---------------|
| EC2 t3.small | Compute Engine e2-small | `catscan-vm` |
| Elastic IP | Static External IP | `catscan-ip` |
| S3 Bucket | Cloud Storage | `catscan-data-<project-id>` |
| Security Group | Firewall Rules | `catscan-allow-http` |
| IAM Role | Service Account | `catscan-vm@<project>.iam` |

### Estimated GCP Costs

| Resource | Monthly Cost |
|----------|--------------|
| e2-small (2 vCPU, 2GB) | ~$12 |
| 30GB Standard Disk | ~$1.20 |
| Static IP | ~$3 |
| Cloud Storage (100GB) | ~$2 |
| **Total** | **~$18/month** |

### GCP Project Setup

```bash
# Use existing project or create new
gcloud projects create catscan-production --name="Cat-Scan Production"

# Enable required APIs
gcloud services enable compute.googleapis.com
gcloud services enable storage.googleapis.com

# Set default region
gcloud config set compute/region europe-west1
gcloud config set compute/zone europe-west1-b
```

---

## Phase 3: GCP Terraform Configuration

### New Terraform Structure

```
terraform/
├── main.tf              # Provider config (GCP)
├── variables.tf         # Input variables
├── outputs.tf           # Output values
├── compute.tf           # VM instance
├── network.tf           # Firewall rules
├── storage.tf           # Cloud Storage bucket
├── iam.tf               # Service account
└── startup-script.sh    # VM initialization
```

### Key Terraform Changes

**Provider:**
```hcl
# OLD (AWS)
provider "aws" {
  region = "eu-central-1"
}

# NEW (GCP)
provider "google" {
  project = var.project_id
  region  = "europe-west1"
  zone    = "europe-west1-b"
}
```

**Compute:**
```hcl
# OLD (AWS EC2)
resource "aws_instance" "catscan" {
  ami           = data.aws_ami.amazon_linux.id
  instance_type = "t3.small"
}

# NEW (GCP Compute Engine)
resource "google_compute_instance" "catscan" {
  name         = "catscan-vm"
  machine_type = "e2-small"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      size  = 30
    }
  }

  network_interface {
    network = "default"
    access_config {
      nat_ip = google_compute_address.catscan.address
    }
  }

  metadata_startup_script = file("startup-script.sh")
}
```

**Storage:**
```hcl
# OLD (AWS S3)
resource "aws_s3_bucket" "catscan" {
  bucket = "catscan-production-data-${random_id.suffix.hex}"
}

# NEW (GCP Cloud Storage)
resource "google_storage_bucket" "catscan" {
  name     = "catscan-data-${var.project_id}"
  location = "EU"

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition { age = 365 }
    action { type = "Delete" }
  }
}
```

---

## Phase 4: Code Changes

### Files to Update

| File | Change |
|------|--------|
| `scripts/gmail_import.py` | Replace S3 with Cloud Storage |
| `terraform/*` | Complete rewrite for GCP |
| `docs/AWS_DEPLOYMENT_PLAN.md` | Delete or rename to GCP |
| `README.md` | Update deployment section |
| `docker-compose.simple.yml` | No change (container is cloud-agnostic) |

### gmail_import.py Changes

```python
# OLD (AWS S3)
import boto3
s3_client = boto3.client('s3', region_name='eu-central-1')
s3_client.upload_file(filepath, bucket, key)

# NEW (GCP Cloud Storage)
from google.cloud import storage
client = storage.Client()
bucket = client.bucket('catscan-data-PROJECT')
blob = bucket.blob(key)
blob.upload_from_filename(filepath)
```

---

## Phase 5: Migration Steps

### 5.1 Pre-Migration (Before GCP is Ready)

```bash
# 1. Download database from AWS
scp -i ~/.ssh/id_ed25519 ec2-user@18.185.146.184:/home/catscan/.catscan/catscan.db ~/backup/

# 2. Download archived CSVs from S3
aws s3 sync s3://rtbcat-csv-archive-frankfurt-328614522524 ~/backup/csv-archive/

# 3. Save credentials (already have locally)
cp ~/.catscan/credentials/gmail-token.json ~/backup/
```

### 5.2 GCP Deployment

```bash
# 1. Create Terraform for GCP
cd terraform
# (rewrite terraform files for GCP)

# 2. Initialize and deploy
terraform init
terraform plan -out=tfplan
terraform apply tfplan

# 3. Get new IP
terraform output public_ip
```

### 5.3 Data Migration

```bash
# 1. Upload database to GCP VM
gcloud compute scp ~/backup/catscan.db catscan-vm:/home/catscan/.catscan/

# 2. Upload credentials
gcloud compute scp ~/backup/gmail-token.json catscan-vm:/home/catscan/.catscan/credentials/

# 3. Migrate CSV archive to Cloud Storage
gsutil -m cp -r ~/backup/csv-archive/* gs://catscan-data-PROJECT/csv-archive/
```

### 5.4 Verification

```bash
# 1. Test API
curl http://NEW_IP:8000/health

# 2. Test Dashboard
open http://NEW_IP:3000

# 3. Test Gmail import
gcloud compute ssh catscan-vm -- "cd /home/catscan/rtbcat-platform/creative-intelligence && python scripts/gmail_import.py"
```

---

## Phase 6: AWS Cleanup

### Step 1: Stop EC2 Instance (Immediate Cost Savings)

```bash
aws ec2 stop-instances --region eu-central-1 --instance-ids i-08758180a9d369fb7
```

### Step 2: Terraform Destroy (Main Resources)

```bash
cd /home/jen/Documents/rtbcat-platform/terraform
~/bin/terraform destroy -auto-approve
```

This deletes:
- EC2 instance
- Elastic IP
- S3 bucket (catscan-production-data-*)
- Security group
- IAM role & instance profile

### Step 3: Delete Manually Created S3 Buckets

```bash
# Empty buckets first (required before deletion)
aws s3 rm s3://rtbcat-csv-archive-328614522524 --recursive
aws s3 rm s3://rtbcat-csv-archive-frankfurt-328614522524 --recursive

# Delete buckets
aws s3api delete-bucket --bucket rtbcat-csv-archive-328614522524 --region us-east-1
aws s3api delete-bucket --bucket rtbcat-csv-archive-frankfurt-328614522524 --region eu-central-1
```

### Step 4: Delete Key Pairs

```bash
aws ec2 delete-key-pair --region eu-central-1 --key-name jen-laptop
aws ec2 delete-key-pair --region eu-central-1 --key-name catscan-frankfurt-key
```

### Step 5: Delete Legacy IAM Resources

```bash
# Remove role from instance profile
aws iam remove-role-from-instance-profile \
  --instance-profile-name catscan-ec2-role \
  --role-name catscan-ec2-role

# Delete instance profile
aws iam delete-instance-profile --instance-profile-name catscan-ec2-role

# Delete role policies
aws iam list-role-policies --role-name catscan-ec2-role --query 'PolicyNames' --output text | \
  xargs -I {} aws iam delete-role-policy --role-name catscan-ec2-role --policy-name {}

# Delete attached policies
aws iam list-attached-role-policies --role-name catscan-ec2-role --query 'AttachedPolicies[].PolicyArn' --output text | \
  xargs -I {} aws iam detach-role-policy --role-name catscan-ec2-role --policy-arn {}

# Delete role
aws iam delete-role --role-name catscan-ec2-role
```

### Step 6: Verify Cleanup

```bash
# Check for remaining resources
aws ec2 describe-instances --region eu-central-1 \
  --filters "Name=tag:Name,Values=*catscan*" \
  --query 'Reservations[].Instances[].InstanceId'

aws s3api list-buckets --query "Buckets[?contains(Name, 'catscan') || contains(Name, 'rtbcat')].Name"

aws iam list-roles --query "Roles[?contains(RoleName, 'catscan')].RoleName"
```

---

## Phase 7: Documentation Updates

### Files to Update After Migration

| File | Action |
|------|--------|
| `docs/AWS_DEPLOYMENT_PLAN.md` | Delete |
| `docs/GCP_DEPLOYMENT.md` | Create (new) |
| `README.md` | Update deployment section |
| `terraform/` | Rewrite for GCP |

### New Documentation Structure

```
docs/
├── GCP_DEPLOYMENT.md        # Main deployment guide
├── GMAIL_OAUTH_SETUP.md     # OAuth setup (reuse from AWS doc)
├── CSV_REPORTS_GUIDE.md     # No change
└── HANDOVER.md              # Update references
```

---

## Timeline Summary

| Phase | Duration | Description |
|-------|----------|-------------|
| 1. Inventory | Done | AWS resources documented |
| 2. GCP Setup | 1-2 hours | Project, APIs, credentials |
| 3. Terraform | 2-3 hours | Rewrite for GCP |
| 4. Code Changes | 1 hour | Update S3 → Cloud Storage |
| 5. Migration | 1 hour | Deploy, migrate data, verify |
| 6. AWS Cleanup | 30 min | Delete all AWS resources |
| 7. Documentation | 1 hour | Update all docs |

**Total estimated time: 6-8 hours**

---

## Rollback Plan

If GCP migration fails:
1. AWS resources remain until explicitly deleted
2. Can restart EC2 instance anytime
3. Data backed up locally before migration

---

## Checklist

### Pre-Migration
- [ ] Backup SQLite database from EC2
- [ ] Backup CSV archive from S3
- [ ] Backup credentials locally
- [ ] Create GCP project
- [ ] Enable GCP APIs

### GCP Deployment
- [ ] Write GCP Terraform config
- [ ] Deploy infrastructure
- [ ] Upload application code
- [ ] Upload database
- [ ] Upload credentials
- [ ] Verify API health
- [ ] Verify Dashboard
- [ ] Test Gmail import

### AWS Cleanup
- [ ] Stop EC2 instance
- [ ] Run terraform destroy
- [ ] Delete S3 buckets (manual)
- [ ] Delete key pairs
- [ ] Delete IAM resources
- [ ] Verify all resources deleted

### Documentation
- [ ] Delete AWS_DEPLOYMENT_PLAN.md
- [ ] Create GCP_DEPLOYMENT.md
- [ ] Update README.md
- [ ] Update any other references

---

*Document maintained by: Claude Code*
*Created: December 24, 2025*

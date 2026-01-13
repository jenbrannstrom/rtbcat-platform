# GCP Migration Plan for Cat-Scan

**Created:** January 6, 2026
**Updated:** January 12, 2026
**Status:** Ready to Execute
**Current State:** AWS EC2 (Frankfurt) with SQLite
**Target State:** GCP e2-micro (europe-west1) - **$6/month**

---

## Executive Summary

**Decision:** Migrate to GCP e2-micro for ~$6/month total cost.

| Aspect | Value |
|--------|-------|
| **Monthly Cost** | ~$6 (vs $45 original plan) |
| **Instance Type** | e2-micro (2 shared vCPU, 1GB RAM) |
| **Storage** | 20GB SSD ($3.40/month) |
| **Free Tier** | First 744 hours/month FREE |
| **Migration Effort** | 1-2 days |
| **Why GCP** | Zero egress fees, native Google API integration |

---

## Why Migrate to GCP?

Cat-Scan is fundamentally a **Google-centric application**:

| Component | Google Dependency |
|-----------|------------------|
| Core API | Google Authorized Buyers RTB API |
| Report Delivery | Gmail (scheduled CSV reports) |
| Large Reports | Google Cloud Storage downloads |
| Authentication | Google OAuth / Service Accounts |
| Future: Real-time | Google Pub/Sub (if available) |

**Current Pain Points on AWS:**
1. Gmail OAuth tokens need manual copying between machines
2. GCS downloads require cross-cloud authentication
3. Service account credentials scattered across environments
4. Potential egress fees for GCS report downloads
5. No native Cloud Scheduler for cron jobs

**GCP Benefits:**
1. **Native Authentication**: Service accounts "just work"
2. **Zero Egress Fees**: All traffic stays in Google's network
3. **Cloud Scheduler**: Built-in cron for Gmail imports
4. **Unified IAM**: One permission model for all Google APIs
5. **Simpler Operations**: Fewer moving parts

---

## Database Options: First Principles Analysis

### Current State

```
Database: SQLite 3.x with WAL mode
Size: 437 MB
Tables: 34
Largest table: performance_metrics (1.6M rows)
Location: ~/.catscan/catscan.db (single file)
```

### Original SQLite Rationale

SQLite was chosen for:
- Zero configuration
- Single-file backup (just copy the file)
- WAL mode for concurrent reads
- "Good enough" for expected scale

---

## Option 1: SQLite on GCE e2-micro (RECOMMENDED)

**Architecture:** Single VM with SQLite file on persistent disk
**Cost:** ~$6/month (or FREE with free tier)

### How It Works
SQLite is an embedded database - it's a C library that reads/writes directly to a file. There's no separate server process. Your Python application links against SQLite and performs file I/O directly.

```
┌─────────────────────────────────────────┐
│           GCE VM (e2-micro)             │
│           1GB RAM, 2 shared vCPU        │
│  ┌─────────────┐    ┌────────────────┐  │
│  │  FastAPI    │───▶│  SQLite File   │  │
│  │  (Python)   │    │  (catscan.db)  │  │
│  └─────────────┘    └────────────────┘  │
│                            │            │
│                     20GB SSD Disk       │
└─────────────────────────────────────────┘
```

### Why e2-micro is Sufficient

| Metric | Requirement | e2-micro Capacity |
|--------|-------------|-------------------|
| **RAM** | ~300MB (FastAPI + Next.js) | 1GB |
| **CPU** | Low (mostly I/O bound) | 2 shared vCPU |
| **Storage** | 437MB database | 20GB SSD |
| **Concurrent Users** | 1-5 | Handles fine |
| **Daily Imports** | ~50 CSV files | No problem |

**Note:** If you experience slowness, upgrade to e2-small ($13/month) with one command.

**CSV Import Details:** Cat-Scan supports 5 CSV report types from Google Authorized Buyers. See [DATA_MODEL.md](../DATA_MODEL.md#csv-import-reference) for complete column specifications, sample data, and detection logic.

### Pros
| Advantage | Explanation |
|-----------|-------------|
| **Zero migration effort** | Same code, same schema, just copy the file |
| **Extremely low cost** | ~$6/month (or FREE with free tier) |
| **Simplest operations** | Backup = copy file to GCS |
| **No network latency** | Database is local to application |
| **Fastest queries** | No network round-trips |
| **ACID compliant** | Full transaction support |
| **Native Google APIs** | No egress fees for GCS downloads |
| **Cloud Scheduler** | Free tier includes 3 jobs/month |

### Cons
| Disadvantage | Explanation |
|--------------|-------------|
| **Single writer** | Only one process can write at a time (WAL helps) |
| **No horizontal scaling** | Cannot add more instances |
| **VM management** | You manage OS updates (automated via startup script) |
| **Limited RAM** | 1GB means careful memory management |

### When to Choose
- Single-tenant deployments (you!)
- Predictable, low-moderate load
- Cost is primary concern
- Want native Google integration

### Cost Estimate (e2-micro)
```
e2-micro (2 shared vCPU, 1GB RAM):  $0/month (free tier) or ~$6/month
20GB SSD persistent disk:           ~$3.40/month
Static IP (attached to running VM): $0/month
Cloud Scheduler (3 jobs):           $0/month (free tier)
                                    ─────────
Total:                              ~$3-6/month
```

### Upgrade Path (if needed)
```bash
# If e2-micro is too slow, upgrade instantly:
gcloud compute instances set-machine-type catscan-production \
  --machine-type=e2-small --zone=europe-west1-b

# e2-small: 2 vCPU, 2GB RAM = ~$13/month
# e2-medium: 2 vCPU, 4GB RAM = ~$25/month
```

---

## Option 2: Cloud SQL (PostgreSQL)

**Architecture:** Managed PostgreSQL with Cloud Run or GCE

### How It Works
Cloud SQL runs a PostgreSQL server in a managed environment. Your application connects over the network (or Unix socket via Cloud SQL Proxy). Google handles replication, backups, patches.

```
┌─────────────────┐         ┌─────────────────────────┐
│   Cloud Run     │         │      Cloud SQL          │
│  ┌───────────┐  │   TCP   │  ┌─────────────────┐    │
│  │  FastAPI  │──┼────────▶│  │   PostgreSQL    │    │
│  │  (Python) │  │  :5432  │  │   (Managed)     │    │
│  └───────────┘  │         │  └─────────────────┘    │
└─────────────────┘         │  - Auto backups         │
                            │  - HA optional          │
                            │  - Auto patches         │
                            └─────────────────────────┘
```

### Pros
| Advantage | Explanation |
|-----------|-------------|
| **Managed service** | Google handles backups, patches, HA |
| **Horizontal read scaling** | Read replicas for heavy read loads |
| **Point-in-time recovery** | Restore to any second in retention window |
| **Multiple connections** | Many application instances can connect |
| **Rich SQL features** | JSON columns, full-text search, CTEs, window functions |
| **Cloud Run compatible** | Serverless app + managed DB |
| **Familiar tooling** | psql, pgAdmin, standard PostgreSQL ecosystem |

### Cons
| Disadvantage | Explanation |
|--------------|-------------|
| **Schema migration required** | SQLite → PostgreSQL syntax differences |
| **Network latency** | ~1-5ms per query (adds up for chatty apps) |
| **Higher cost** | Minimum ~$10/month even when idle |
| **Connection management** | Need connection pooling for serverless |
| **Complexity** | More configuration, more things to monitor |

### Migration Effort

**SQLite → PostgreSQL differences:**

| SQLite | PostgreSQL | Migration Action |
|--------|------------|------------------|
| `INTEGER PRIMARY KEY` | `SERIAL` or `BIGSERIAL` | Schema change |
| `AUTOINCREMENT` | `SERIAL` | Schema change |
| `TEXT` for everything | Proper types (`VARCHAR`, `JSONB`) | Optional optimization |
| `datetime('now')` | `NOW()` or `CURRENT_TIMESTAMP` | Query changes |
| `date('now', '-7 days')` | `NOW() - INTERVAL '7 days'` | Query changes |
| `||` for concat | `||` (same) | No change |
| No `BOOLEAN` | Native `BOOLEAN` | Optional |
| JSON as TEXT | Native `JSONB` | Optional optimization |

**Estimated effort:** 2-4 hours for schema, 4-8 hours for query syntax

### When to Choose
- Need multiple application instances
- Want managed backups and HA
- Planning to scale significantly
- Team familiar with PostgreSQL
- Using Cloud Run (serverless)

### Cost Estimate
```
db-f1-micro (shared, 0.6GB RAM):  ~$10/month (dev/test)
db-g1-small (1 vCPU, 1.7GB RAM):  ~$35/month (light prod)
db-custom-2-4096 (2 vCPU, 4GB):   ~$75/month (production)
100GB SSD storage:                ~$17/month
Backups (7 days):                 ~$5/month
                                  ─────────
Total (light prod):               ~$57/month
```

---

## Option 3: Firestore (NoSQL)

**Architecture:** Serverless document database

### How It Works
Firestore is a document-oriented NoSQL database. Data is stored as documents in collections. No schema enforcement - each document can have different fields. Scales automatically.

```
┌─────────────────┐         ┌─────────────────────────┐
│   Cloud Run     │         │      Firestore          │
│  ┌───────────┐  │  gRPC   │  ┌─────────────────┐    │
│  │  FastAPI  │──┼────────▶│  │  Collections    │    │
│  │  (Python) │  │         │  │  - creatives    │    │
│  └───────────┘  │         │  │  - campaigns    │    │
└─────────────────┘         │  │  - metrics/     │    │
                            │  │    {date}/      │    │
                            │  │      {doc}      │    │
                            │  └─────────────────┘    │
                            │  - Auto-scaling         │
                            │  - Real-time sync       │
                            │  - Offline support      │
                            └─────────────────────────┘
```

### Pros
| Advantage | Explanation |
|-----------|-------------|
| **Truly serverless** | No instances to manage, scales to zero |
| **Auto-scaling** | Handles any load automatically |
| **Real-time listeners** | Push updates to clients (great for dashboards) |
| **Generous free tier** | 50K reads, 20K writes, 1GB storage/day free |
| **No connection limits** | No pooling needed |
| **Offline support** | Client SDKs handle offline gracefully |

### Cons
| Disadvantage | Explanation |
|--------------|-------------|
| **Complete rewrite** | NoSQL requires different data modeling |
| **No JOINs** | Must denormalize or do client-side joins |
| **No aggregations** | COUNT, SUM, AVG must be maintained manually |
| **Query limitations** | No OR queries, limited inequality filters |
| **Cost unpredictability** | Pay per read/write operation |
| **Vendor lock-in** | Firestore-specific APIs |

### Why It's Wrong for Cat-Scan

Cat-Scan's data model is **deeply relational**:

```sql
-- This common query pattern is trivial in SQL:
SELECT c.name, SUM(pm.spend_micros), COUNT(DISTINCT pm.geography)
FROM creatives c
JOIN performance_metrics pm ON pm.creative_id = c.id
WHERE pm.metric_date >= '2026-01-01'
GROUP BY c.id
ORDER BY SUM(pm.spend_micros) DESC;
```

In Firestore, this would require:
1. Maintaining a separate `creative_spend_totals` collection
2. Updating it on every metrics write (Cloud Functions)
3. Multiple queries to assemble the data
4. Potential consistency issues

**Verdict:** Firestore is excellent for chat apps, user profiles, real-time collaboration. It's a poor fit for analytics workloads with complex aggregations.

### When to Choose
- Building a mobile app with offline support
- Need real-time sync across clients
- Simple document structure
- Unpredictable, bursty traffic
- Want to avoid all server management

### Cost Estimate
```
Firestore pricing is per-operation:
- Reads:  $0.036 per 100K
- Writes: $0.108 per 100K
- Deletes: $0.012 per 100K
- Storage: $0.108 per GB/month

For Cat-Scan (estimated):
- 1.6M metrics rows × 10 reads/day = 16M reads = ~$5.76/day = $173/month
- Plus writes for imports...

Total: $150-300/month (HIGHER than SQL options)
```

---

## Recommendation

### For Cat-Scan: Option 1 (SQLite on GCE e2-micro) - $6/month

**Rationale:**

1. **No migration effort** - Same code works immediately
2. **Extremely low cost** - ~$6/month (essentially free)
3. **Performance** - Local disk faster than network DB
4. **Scale is sufficient** - 1.6M rows is small; SQLite handles 100M+ fine
5. **Native Google** - Zero egress fees, Cloud Scheduler for cron
6. **One cloud** - Simplifies operations, authentication, billing

**When to upgrade:**
- **e2-small ($13/month)** - If you notice slowness
- **e2-medium ($25/month)** - If running heavy analytics
- **Cloud SQL ($57/month)** - If database exceeds 10GB or need HA

### Migration Path

```
NOW:           GCE e2-micro + SQLite (~$6/month)
               ↓ (If slow)
UPGRADE 1:     GCE e2-small + SQLite (~$16/month)
               ↓ (If database >10GB)
UPGRADE 2:     GCE e2-small + Cloud SQL (~$50/month)
               ↓ (If need serverless)
UPGRADE 3:     Cloud Run + Cloud SQL (~$75/month)
```

---

## GCP Architecture Plan

### Target Architecture (e2-micro - $6/month)

```
┌──────────────────────────────────────────────────────────────────┐
│                     GCP Project (europe-west1)                    │
│                                                                   │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │              GCE e2-micro ($6/month)                        │  │
│  │              1GB RAM, 2 shared vCPU, 20GB SSD               │  │
│  │                                                             │  │
│  │  ┌─────────────┐     ┌─────────────┐     ┌──────────────┐  │  │
│  │  │   Nginx     │────▶│  FastAPI    │────▶│   SQLite     │  │  │
│  │  │  (SSL/443)  │     │  (8000)     │     │  (catscan.db)│  │  │
│  │  └──────┬──────┘     └─────────────┘     └──────────────┘  │  │
│  │         │                                                   │  │
│  │         └───────────▶┌─────────────┐                       │  │
│  │                      │  Next.js    │                       │  │
│  │                      │  (3000)     │                       │  │
│  │                      └─────────────┘                       │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │
│  │ Cloud Scheduler │  │  OAuth2 Proxy   │  │ Cloud Storage   │   │
│  │ (FREE - 3 jobs) │  │  (Google Auth)  │  │ (Backups/CSV)   │   │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘   │
│                                                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │                    Service Account                           │ │
│  │  - Gmail API (report imports)                               │ │
│  │  - Authorized Buyers API (creatives, pretargeting)          │ │
│  │  - Cloud Storage (zero egress - same cloud!)                │ │
│  └─────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Components & Costs

| Component | GCP Service | Monthly Cost |
|-----------|-------------|--------------|
| **Compute** | GCE e2-micro | $0-6 (free tier eligible) |
| **Storage** | 20GB SSD | $3.40 |
| **Database** | SQLite (on disk) | $0 |
| **SSL** | Let's Encrypt | $0 |
| **Auth** | OAuth2 Proxy | $0 |
| **Cron** | Cloud Scheduler | $0 (3 free jobs) |
| **Backups** | Cloud Storage | ~$0.50 |
| **Static IP** | Attached to VM | $0 |
| **DNS** | Cloud DNS | $0.20/zone |
| | | **~$4-10/month** |

---

## Implementation Steps (Terraform - Recommended)

> **IMPORTANT:** Use Terraform for deployment. Manual `gcloud` commands led to security misconfiguration (ports 3000/8000 exposed) that enabled the January 2026 breach.

### Prerequisites

1. **Install Terraform** (if not already installed)
   ```bash
   # Ubuntu/Debian
   wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
   echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
   sudo apt update && sudo apt install terraform
   ```

2. **Authenticate with GCP**
   ```bash
   gcloud auth login
   gcloud auth application-default login
   ```

3. **Enable Required APIs** (one-time)
   ```bash
   gcloud services enable \
     compute.googleapis.com \
     storage.googleapis.com \
     iap.googleapis.com
   ```

### Step 1: Configure Terraform Variables

```bash
cd terraform/gcp
cp terraform.tfvars.example terraform.tfvars

# Edit with your values
nano terraform.tfvars
```

Required settings in `terraform.tfvars`:
```hcl
gcp_project  = "your-new-project-id"  # Your new GCP project
gcp_region   = "europe-west1"
domain_name  = "scan.rtb.cat"
enable_https = true
```

### Step 2: Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Preview changes
terraform plan

# Deploy (creates VM, firewall rules, storage bucket, service account)
terraform apply
```

This creates:
- GCE VM with hardened startup script
- **Secure firewall**: Only ports 80/443 exposed (NOT 3000/8000)
- Cloud Storage bucket for backups
- Service account with minimal permissions
- Static IP address

### Step 3: Wait for Startup Script

```bash
# SSH via IAP (secure - no SSH port exposed)
gcloud compute ssh catscan-production --zone=europe-west1-b --tunnel-through-iap

# Check startup progress
sudo tail -f /var/log/catscan-setup.log
```

### Step 4: Upload Credentials

```bash
# Upload Google API credentials
gcloud compute scp ~/.catscan/credentials/google-credentials.json \
  catscan-production:/tmp/ --zone=europe-west1-b

gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "sudo mv /tmp/google-credentials.json /home/catscan/.catscan/credentials/"
```

### Step 5: Migrate Database (Optional)

```bash
# If you have an existing database to migrate:
gcloud compute scp ~/.catscan/catscan.db \
  catscan-production:/tmp/ --zone=europe-west1-b

gcloud compute ssh catscan-production --zone=europe-west1-b -- \
  "sudo mv /tmp/catscan.db /home/catscan/.catscan/ && sudo chown catscan:catscan /home/catscan/.catscan/catscan.db"
```

### Step 6: Update DNS

Point your domain's A record to the static IP shown in Terraform output:
```bash
terraform output public_ip
```

### Step 7: Verify Security

```bash
# SSH into the VM
gcloud compute ssh catscan-production --zone=europe-west1-b --tunnel-through-iap

# Verify ports 3000/8000 are NOT publicly accessible
sudo netstat -tlnp | grep -E '(3000|8000)'
# Should show 127.0.0.1:3000 and 127.0.0.1:8000 (localhost only)

# Test from outside (should fail)
curl http://YOUR_IP:3000  # Should timeout/refuse
curl http://YOUR_IP:8000  # Should timeout/refuse
```

---

## Security: What Terraform Prevents

| Issue | Manual Setup | Terraform Setup |
|-------|--------------|-----------------|
| Port 3000 exposed | **YES** (caused breach) | **NO** (blocked) |
| Port 8000 exposed | **YES** (caused breach) | **NO** (blocked) |
| SSH from anywhere | Often yes | IAP only (requires Google auth) |
| Services on 0.0.0.0 | Default | Bound to 127.0.0.1 |
| Firewall misconfiguration | Easy to make | Prevented by code |

---

## Gmail Integration (Post-Deploy)

**Set up Cloud Scheduler** (after VM is running):
```bash
gcloud scheduler jobs create http gmail-import \
  --location=europe-west1 \
  --schedule="0 8 * * *" \
  --uri="https://scan.rtb.cat/api/gmail/import" \
  --http-method=POST \
  --oidc-service-account-email=$(terraform output -raw service_account_email)
```

---

## Backup Strategy

Backups are **automatically configured** by the startup script:
- Daily backup at 3 AM to Cloud Storage
- 30-day retention policy
- Bucket name: `terraform output gcs_bucket`

Manual backup:
```bash
gcloud compute ssh catscan-production --zone=europe-west1-b -- "sudo /usr/local/bin/catscan-backup"
```

---

## Cost Comparison

| Item | AWS (Current) | GCP e2-micro (Proposed) |
|------|---------------|-------------------------|
| Compute | EC2 t3.medium ~$30 | GCE e2-micro ~$6 |
| Storage | EBS 100GB ~$10 | PD-SSD 20GB ~$3.40 |
| Load Balancer | ALB ~$16 | Nginx (on VM) ~$0 |
| Static IP | $3.60 | $0 (attached to VM) |
| Data Transfer | $0 (within AWS) | $0 (within GCP) |
| **GCS Egress** | **~$10-20** (cross-cloud) | **$0** (same cloud) |
| SSL | ACM ~$0 | Let's Encrypt ~$0 |
| **Total** | **~$60-80/month** | **~$6-10/month** |

**Savings: 85-90%** (~$50-70/month saved)

**Additional Benefits:**
- Native Google API authentication
- Zero egress fees for GCS report downloads
- Cloud Scheduler for Gmail import cron (free)
- Simpler billing (one cloud provider)
- Instant upgrade path if needed

---

## Rollback Plan

If GCP migration fails:

1. DNS points to GCP but can switch back to AWS in minutes
2. AWS EC2 instance kept running (stopped) for 1 week
3. SQLite database file easily portable
4. Same Docker containers work on both clouds

---

## Timeline

| Day | Task | Time |
|-----|------|------|
| 1 | GCP project setup, enable APIs | 30 min |
| 1 | Create e2-micro VM via Terraform | 15 min |
| 1 | Copy database + credentials from AWS | 30 min |
| 1 | Test application works | 30 min |
| 2 | Update DNS to point to GCP | 5 min |
| 2 | SSL certificate (Let's Encrypt) | 15 min |
| 2 | Set up Cloud Scheduler for Gmail import | 15 min |
| 2 | Full testing, verify all features | 1 hour |
| 3 | Monitor for 24 hours | - |
| 3 | Stop AWS instance (keep 1 week as backup) | 5 min |

**Total: 1-2 days** (mostly waiting for DNS propagation)

---

## Quick Start Commands

```bash
# 1. Create GCP project (if new)
gcloud projects create catscan-prod --name="Cat-Scan"
gcloud config set project catscan-prod

# 2. Enable APIs
gcloud services enable compute.googleapis.com storage.googleapis.com

# 3. Create e2-micro VM
gcloud compute instances create catscan-production \
  --zone=europe-west1-b \
  --machine-type=e2-micro \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB \
  --boot-disk-type=pd-ssd \
  --tags=http-server,https-server

# 4. Create firewall rule (HTTPS only!)
gcloud compute firewall-rules create allow-https \
  --allow=tcp:80,tcp:443 \
  --target-tags=http-server,https-server

# 5. SSH and setup
gcloud compute ssh catscan-production --zone=europe-west1-b
```

---

## Decision: APPROVED

| Decision | Choice |
|----------|--------|
| **Instance Type** | e2-micro ($6/month) |
| **Database** | SQLite on GCE (same code) |
| **Gmail Auth** | OAuth with refresh token |
| **Timeline** | Ready to execute |

**Next Step:** Run the Terraform deployment or quick start commands above.

---

*Plan created by Claude Code. Updated January 12, 2026 for cost optimization.*

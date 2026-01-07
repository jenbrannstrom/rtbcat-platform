# GCP Migration Plan for Cat-Scan

**Created:** January 6, 2026
**Status:** Planning
**Current State:** AWS EC2 (Frankfurt) with SQLite
**Target State:** GCP (europe-west1) with native Google integration

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

## Option 1: SQLite on GCE (Compute Engine)

**Architecture:** Single VM with SQLite file on persistent disk

### How It Works
SQLite is an embedded database - it's a C library that reads/writes directly to a file. There's no separate server process. Your Python application links against SQLite and performs file I/O directly.

```
┌─────────────────────────────────────────┐
│           GCE VM (e2-medium)            │
│  ┌─────────────┐    ┌────────────────┐  │
│  │  FastAPI    │───▶│  SQLite File   │  │
│  │  (Python)   │    │  (catscan.db)  │  │
│  └─────────────┘    └────────────────┘  │
│                            │            │
│                     Persistent Disk     │
└─────────────────────────────────────────┘
```

### Pros
| Advantage | Explanation |
|-----------|-------------|
| **Zero migration effort** | Same code, same schema, just copy the file |
| **Lowest cost** | ~$25/month for e2-medium + disk |
| **Simplest operations** | Backup = copy file to GCS |
| **No network latency** | Database is local to application |
| **Fastest queries** | No network round-trips |
| **ACID compliant** | Full transaction support |

### Cons
| Disadvantage | Explanation |
|--------------|-------------|
| **Single writer** | Only one process can write at a time (WAL helps but doesn't eliminate) |
| **No horizontal scaling** | Cannot add more instances |
| **VM management** | You manage OS updates, security patches |
| **Disk-bound** | Performance limited by disk IOPS |
| **No point-in-time recovery** | Manual backup strategy required |

### When to Choose
- Single-tenant deployments
- Predictable, moderate load
- Cost is primary concern
- Team prefers simplicity over scalability

### Cost Estimate
```
e2-medium (2 vCPU, 4GB RAM):     ~$25/month
100GB SSD persistent disk:       ~$17/month
Static IP:                       ~$3/month
                                 ─────────
Total:                           ~$45/month
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

### For Cat-Scan: Option 1 (SQLite on GCE)

**Rationale:**

1. **No migration effort** - Same code works immediately
2. **Lowest cost** - ~$45/month vs $57+ for Cloud SQL
3. **Performance** - Local disk faster than network DB for this workload
4. **Scale is sufficient** - 1.6M rows is small; SQLite handles 100M+ fine
5. **Simplicity** - One less service to manage

**When to reconsider:**
- If you need multiple app instances (load balancing)
- If database grows past 10GB
- If you need point-in-time recovery
- If you hire a team (managed DB reduces ops burden)

### Migration Path

```
Phase 1: GCE + SQLite (Current plan)
   │
   ▼ (If needed later)
Phase 2: GCE + Cloud SQL (PostgreSQL)
   │
   ▼ (If needed later)
Phase 3: Cloud Run + Cloud SQL (Serverless)
```

---

## GCP Architecture Plan

### Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GCP Project                               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 Cloud Load Balancing                      │   │
│  │                 (HTTPS, managed SSL)                      │   │
│  └─────────────────────────┬────────────────────────────────┘   │
│                            │                                     │
│  ┌─────────────────────────▼────────────────────────────────┐   │
│  │              GCE Instance (e2-medium)                     │   │
│  │              europe-west1-b                               │   │
│  │  ┌─────────────────┐  ┌─────────────────┐                │   │
│  │  │   FastAPI       │  │   Next.js       │                │   │
│  │  │   (Port 8000)   │  │   (Port 3000)   │                │   │
│  │  └────────┬────────┘  └─────────────────┘                │   │
│  │           │                                               │   │
│  │  ┌────────▼────────┐                                     │   │
│  │  │  SQLite DB      │                                     │   │
│  │  │  (Persistent    │                                     │   │
│  │  │   Disk SSD)     │                                     │   │
│  │  └─────────────────┘                                     │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐   │
│  │ Cloud Scheduler │  │ Secret Manager  │  │ Cloud Storage  │   │
│  │ (Gmail cron)    │  │ (Credentials)   │  │ (CSV Archive)  │   │
│  └─────────────────┘  └─────────────────┘  └────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Service Account                             │    │
│  │  - Gmail API (domain-wide delegation or OAuth)          │    │
│  │  - Authorized Buyers API                                │    │
│  │  - Cloud Storage (for GCS report downloads)             │    │
│  └─────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────┘
```

### Components

| Component | GCP Service | Purpose |
|-----------|-------------|---------|
| Compute | GCE e2-medium | Run API + Dashboard |
| Database | SQLite on SSD | Data persistence |
| Load Balancer | Cloud Load Balancing | HTTPS termination |
| DNS | Cloud DNS | scan.rtb.cat |
| Scheduler | Cloud Scheduler | Gmail import cron |
| Secrets | Secret Manager | API keys, OAuth tokens |
| Storage | Cloud Storage | CSV archive, backups |
| IAM | Service Account | API authentication |

---

## Implementation Steps

### Phase 1: GCP Setup (Day 1)

1. **Create GCP Project** (or use existing)
   ```bash
   gcloud projects create catscan-prod --name="Cat-Scan Production"
   gcloud config set project catscan-prod
   ```

2. **Enable Required APIs**
   ```bash
   gcloud services enable \
     compute.googleapis.com \
     cloudscheduler.googleapis.com \
     secretmanager.googleapis.com \
     storage.googleapis.com \
     authorizedbuyersmarketplace.googleapis.com \
     gmail.googleapis.com
   ```

3. **Create Service Account**
   ```bash
   gcloud iam service-accounts create catscan-api \
     --display-name="Cat-Scan API Service Account"
   ```

4. **Create GCE Instance**
   ```bash
   gcloud compute instances create catscan-prod \
     --zone=europe-west1-b \
     --machine-type=e2-medium \
     --image-family=debian-12 \
     --image-project=debian-cloud \
     --boot-disk-size=50GB \
     --boot-disk-type=pd-ssd \
     --tags=http-server,https-server \
     --service-account=catscan-api@catscan-prod.iam.gserviceaccount.com \
     --scopes=cloud-platform
   ```

### Phase 2: Application Deployment (Day 1-2)

1. **Install Docker on GCE**
   ```bash
   sudo apt-get update
   sudo apt-get install -y docker.io docker-compose
   sudo usermod -aG docker $USER
   ```

2. **Clone Repository**
   ```bash
   git clone https://github.com/your-repo/rtbcat-platform.git
   cd rtbcat-platform
   ```

3. **Copy SQLite Database**
   ```bash
   # From local machine:
   scp ~/.catscan/catscan.db user@GCE_IP:~/.catscan/
   ```

4. **Deploy with Docker Compose**
   ```bash
   docker-compose -f docker-compose.production.yml up -d
   ```

### Phase 3: DNS & SSL (Day 2)

1. **Reserve Static IP**
   ```bash
   gcloud compute addresses create catscan-ip --region=europe-west1
   ```

2. **Update DNS** (scan.rtb.cat → new IP)

3. **Set up HTTPS** (managed SSL via Load Balancer or Caddy)

### Phase 4: Gmail Integration (Day 2-3)

1. **Configure Service Account for Gmail**
   - Option A: Domain-wide delegation (requires Workspace admin)
   - Option B: OAuth with refresh token (current approach)

2. **Set up Cloud Scheduler**
   ```bash
   gcloud scheduler jobs create http gmail-import \
     --location=europe-west1 \
     --schedule="0 8 * * *" \
     --uri="https://scan.rtb.cat/gmail/import" \
     --http-method=POST \
     --oidc-service-account-email=catscan-api@catscan-prod.iam.gserviceaccount.com
   ```

### Phase 5: Backup Strategy (Day 3)

1. **Daily SQLite Backup to GCS**
   ```bash
   # Cron job or Cloud Scheduler
   sqlite3 ~/.catscan/catscan.db ".backup /tmp/backup.db"
   gsutil cp /tmp/backup.db gs://catscan-backups/$(date +%Y-%m-%d).db
   ```

2. **Retention Policy**
   ```bash
   gsutil lifecycle set lifecycle.json gs://catscan-backups/
   # Keep 30 days of daily backups
   ```

---

## Cost Comparison

| Item | AWS (Current) | GCP (Proposed) |
|------|---------------|----------------|
| Compute | EC2 t3.medium ~$30 | GCE e2-medium ~$25 |
| Storage | EBS 100GB ~$10 | PD-SSD 100GB ~$17 |
| Load Balancer | ALB ~$16 | Cloud LB ~$18 |
| Static IP | $3.60 | $3 |
| Data Transfer | $0 (within AWS) | $0 (within GCP) |
| **GCS Egress** | **~$10-20** (cross-cloud) | **$0** (same cloud) |
| **Total** | **~$60-80/month** | **~$63/month** |

**Net effect:** Similar cost, but eliminates cross-cloud auth complexity.

---

## Rollback Plan

If GCP migration fails:

1. DNS points to GCP but can switch back to AWS in minutes
2. AWS EC2 instance kept running (stopped) for 1 week
3. SQLite database file easily portable
4. Same Docker containers work on both clouds

---

## Timeline

| Day | Task |
|-----|------|
| 1 | GCP project setup, GCE instance creation |
| 1 | Docker deployment, database migration |
| 2 | DNS switchover, SSL setup |
| 2 | Gmail integration, Cloud Scheduler |
| 3 | Testing, backup setup |
| 3 | AWS teardown (after verification) |

**Total: 3 days**

---

## Decision Required

Before proceeding, confirm:

1. **Database choice**: SQLite on GCE (recommended) or Cloud SQL?
2. **Gmail auth method**:
   - Domain-wide delegation (cleanest, requires Workspace admin)
   - OAuth with refresh token (current approach, needs initial browser auth)
3. **Timeline**: Ready to start migration?

---

*Plan created by Claude Code based on current architecture analysis.*

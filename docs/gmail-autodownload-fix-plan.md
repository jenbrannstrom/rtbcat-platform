# Gmail Auto-Download Fix Plan

## Problem Statement
Gmail reports are not being automatically downloaded and parsed. Users must manually click "Import Now" in the dashboard.

## Root Cause Analysis

### Finding 1: No Scheduler Configured in Production Infrastructure

The current GCP terraform (`terraform/gcp/main.tf`) does NOT include a Cloud Scheduler job for Gmail imports:

```hcl
# Line 673-689 - ONLY precompute refresh is scheduled
resource "google_cloud_scheduler_job" "precompute_refresh" {
  name     = "${var.app_name}-precompute-refresh"
  schedule = var.precompute_refresh_schedule
  # Posts to /api/precompute/refresh/scheduled
}

# NO gmail scheduler job exists!
```

### Finding 2: Startup Script Migration Lost Gmail Cron

Two startup scripts exist:

| File | Gmail Cron | Status |
|------|------------|--------|
| `terraform/user_data.sh` (OLD) | YES (lines 163-171) | Not used |
| `terraform/gcp/startup.sh` (NEW) | NO | Currently used |

The old script had:
```bash
# Setup daily Gmail import cron
cat > /etc/cron.d/gmail-import << 'CRONEOF'
0 8 * * * root docker exec catscan-api python scripts/gmail_import.py >> /var/log/gmail-import.log 2>&1
CRONEOF
```

This was never ported to the new `startup.sh`.

### Finding 3: API Endpoint Exists But Unused

The scheduled import endpoint is ready:
- **Endpoint:** `POST /api/gmail/import/scheduled`
- **Auth:** Requires `X-Gmail-Import-Secret` header matching `GMAIL_IMPORT_SECRET` env var
- **File:** `api/routers/gmail.py:102-131`

But nothing calls it.

### Finding 4: Environment Variable Not Configured

`GMAIL_IMPORT_SECRET` is documented in `.env.example` and `docs/GCP_CREDENTIALS_SETUP.md` but:
- Not generated in terraform
- Not passed to the VM/container
- Not set in production

---

## Fix Options

### Option A: Cloud Scheduler (Recommended)

Add Gmail import to terraform Cloud Scheduler. Consistent with precompute approach.

**Pros:**
- Managed service, no VM-level cron
- Visible in GCP Console
- Built-in retry, logging, alerting
- Already proven pattern (precompute uses it)

**Cons:**
- Requires terraform apply
- Needs `GMAIL_IMPORT_SECRET` env var configured

### Option B: Cron Job in startup.sh

Port the cron setup from `user_data.sh` to `startup.sh`.

**Pros:**
- Simpler, runs directly on VM
- No Cloud Scheduler dependency

**Cons:**
- Less visibility
- No built-in alerting
- Cron logs harder to access

### Option C: Systemd Timer

Add `catscan-gmail-import.timer` alongside existing `catscan-home-refresh.timer`.

**Pros:**
- Standard Linux approach
- Better than cron (journalctl logs)

**Cons:**
- More files to manage
- Still VM-level, less visibility than Cloud Scheduler

---

## Recommended Implementation: Option A (Cloud Scheduler)

### Step 1: Add Secret Generation to Terraform

In `terraform/gcp/main.tf`, add after line 44:

```hcl
resource "random_password" "gmail_import_secret" {
  length  = 32
  special = false
}
```

### Step 2: Add Cloud Scheduler Job

In `terraform/gcp/main.tf`, add after the precompute scheduler (after line 689):

```hcl
# Gmail Import Scheduler - Daily at 8 AM UTC
resource "google_cloud_scheduler_job" "gmail_import" {
  name        = "${var.app_name}-gmail-import"
  description = "Daily Gmail report import"
  schedule    = "0 8 * * *"  # 8 AM UTC daily
  time_zone   = "Etc/UTC"
  region      = var.gcp_region

  http_target {
    http_method = "POST"
    uri         = local.gmail_import_url
    headers = {
      X-Gmail-Import-Secret = random_password.gmail_import_secret.result
    }
  }

  retry_config {
    retry_count = 3
    min_backoff_duration = "60s"
    max_backoff_duration = "600s"
  }

  depends_on = [google_project_service.cloudscheduler]
}
```

### Step 3: Add Local for URL

In `terraform/gcp/main.tf`, add to locals block (around line 46):

```hcl
gmail_import_url = (var.enable_https && var.domain_name != "") ? "https://${var.domain_name}/api/gmail/import/scheduled" : "http://${google_compute_address.catscan.address}/api/gmail/import/scheduled"
```

### Step 4: Pass Secret to VM

In `terraform/gcp/main.tf`, update the `metadata_startup_script` templatefile call to include:

```hcl
gmail_import_secret = random_password.gmail_import_secret.result
```

### Step 5: Update startup.sh

In `terraform/gcp/startup.sh`, add to environment setup:

```bash
export GMAIL_IMPORT_SECRET="${gmail_import_secret}"
```

And ensure it's in the docker-compose environment or `.env` file.

### Step 6: Add Monitoring (Optional)

Add logging metric and alert for Gmail import failures, similar to precompute:

```hcl
resource "google_logging_metric" "gmail_import_failures" {
  name   = "${var.app_name}-gmail-import-failures"
  filter = "resource.type=\"cloud_scheduler_job\" AND resource.labels.job_id=\"${google_cloud_scheduler_job.gmail_import.name}\" AND severity>=ERROR"
  # ...
}
```

---

## Verification Steps

1. After terraform apply, check Cloud Scheduler in GCP Console
2. Manually trigger the scheduler job to test
3. Check API logs for import activity
4. Verify Gmail reports appear in dashboard after scheduled run

---

## Files to Modify

| File | Change |
|------|--------|
| `terraform/gcp/main.tf` | Add gmail_import_secret, scheduler job, locals |
| `terraform/gcp/startup.sh` | Pass GMAIL_IMPORT_SECRET to container |
| `terraform/gcp/variables.tf` | Add gmail_import_schedule variable (optional) |

---

## Timeline

- Implementation: 1-2 hours
- Testing: 1 hour (wait for scheduled run or manually trigger)
- Deployment: Requires `terraform apply`

---

## Alternative Quick Fix (No Terraform)

If terraform changes are blocked, manually create the scheduler:

```bash
# Generate secret
GMAIL_SECRET=$(openssl rand -hex 16)

# Set env var on VM
ssh catscan-production-sg
sudo bash -c 'echo "GMAIL_IMPORT_SECRET=YOUR_SECRET" >> /opt/catscan/.env'
docker compose restart

# Create Cloud Scheduler via gcloud
gcloud scheduler jobs create http catscan-gmail-import \
  --location=asia-southeast1 \
  --schedule="0 8 * * *" \
  --uri="https://scan.rtb.cat/api/gmail/import/scheduled" \
  --http-method=POST \
  --headers="X-Gmail-Import-Secret=YOUR_SECRET" \
  --attempt-deadline=600s
```

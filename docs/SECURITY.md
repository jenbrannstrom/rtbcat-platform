# Security Guide

This document explains what data must stay private when deploying Cat-Scan, especially for forked instances.

## Golden Rule

**Code is public. Data and credentials are private.**

The current source tree must contain no credentials or customer data. Scan Git
history as well: deleting a file from the current tree does not remove old copies.
Keep sensitive data outside the repository:
- On your VM in `~/.catscan/`
- In your cloud provider's secret manager
- In gitignored local files (`.env`, `terraform.tfvars`)

---

## What Must NEVER Be Committed

### Credentials & Keys

| File Pattern | Contains | Risk if Leaked |
|--------------|----------|----------------|
| `*.json` (service accounts) | GCP API access | Full access to your Google Cloud project |
| `.env` | API keys, secrets | Access to external services |
| `terraform.tfvars` | OAuth secrets, passwords | Account compromise |
| `*.tfstate` | Full infrastructure state | Exposes all secrets in plain text |
| `~/.catscan/credentials/` | Service account keys | Authorized Buyers API access |

### Data Files

| File Pattern | Contains | Risk if Leaked |
|--------------|----------|----------------|
| `*.db`, `*.sqlite` | Legacy database dumps (if any) | Competitive intelligence leak |
| `*.sql`, `*.dump` | Postgres exports/backups | Business data exposure |
| `*.csv` | Imported Google reports | Revenue and traffic data |
| `~/.catscan/imports/` | Downloaded CSV archives | Historical business data |

### Infrastructure Details

| File | Contains | Risk if Leaked |
|------|----------|----------------|
| Local deployment notes (outside repo) | VM IPs, project IDs, domains | Targeted attacks |
| Terraform outputs | Infrastructure endpoints | Attack surface mapping |

---

## Gitignore Protection

The `.gitignore` file blocks sensitive files. **Verify these patterns exist:**

```gitignore
# Environment and secrets
.env
*.tfstate
*.tfstate.backup
terraform.tfvars
terraform/gcp/terraform.tfvars

# Data files
*.db
data/

# Credentials
catscan-ci-key.json
```

### How to Verify

```bash
# Check if sensitive files are tracked
git ls-files | grep -E '\.(env|tfstate|db)$|terraform\.tfvars'

# Should return empty. If files appear, remove them:
git rm --cached <filename>
```

---

## For Fork Maintainers (Partners)

When you fork Cat-Scan for your organization:

### 1. Before First Commit

```bash
# Verify no secrets in staged files
git diff --cached --name-only | xargs grep -l -E '(password|secret|key|token)' 2>/dev/null
```

### 2. Set Up Your Own Secrets

Create these files locally (they're gitignored):

```bash
# Copy example files
cp .env.example .env
cp terraform/terraform.tfvars.example terraform/terraform.tfvars
cp terraform/gcp/terraform.tfvars.example terraform/gcp/terraform.tfvars

# Edit with your values
nano .env
```

### 3. CI and current production boundaries

Production uses Hetzner with digest-pinned images. The manual GHCR build uses the
workflow's package-scoped `GITHUB_TOKEN`; it does not need production database,
Google or SSH credentials. The security workflow uses the private
`REDACTION_DENYLIST` to check that operational identifiers are not committed.
Keep deployment credentials on the operator/host side, outside source and build
artifacts. See [versioning](VERSIONING.md) and [Hetzner tooling](../scripts/hetzner/README.md).

Google Secret Manager still supplies application Google credentials, even though
application hosting moved. API credentials and the database password are mounted
or retrieved by the API process. The MCP process has no Google or database secret;
it forwards a scoped agent token to the API on each call.

Grok/other clients receive their own expiring, revocable `cat_agent_*` token.
Never publish that token with the connector code. Personal Grok Bots share cloud
credentials; see [the setup guide](GROK_BOT.md) before assigning buyer access.

### 4. Never Commit These

Even if you think it's "just for testing":
- Database files (`*.db`)
- Environment files (`.env`)
- Service account keys (`*.json`)
- Terraform state (`*.tfstate`)
- Deployment notes with real IPs or project IDs

---

## Retained GCP deployment reference

The following GCP bootstrap and infrastructure sections describe the historical
GCE deployment. Those application writers are frozen. Do not restart them or
apply their deployment scripts to publish a current release. Current deployment
controls are in `deploy/hetzner/` and `scripts/hetzner/`.

## Secret Management Architecture

Cat-Scan uses a layered approach to secret management:

### Backend hierarchy

| Backend | When used | How secrets are stored |
|---------|-----------|----------------------|
| **GCP Secret Manager** | Production (GCE VMs) | Terraform creates GSM secret resources; `scripts/provision_gcp_runtime_config.sh` creates versions; startup.sh fetches at boot |
| **Environment variables** | Local dev / Docker | Plain `.env` file (gitignored) |
| **Template fallback** | Phase 1 migration | Terraform `templatefile()` injects into startup script |

### Secrets stored in GSM (production)

| Secret ID pattern | Source | Used by |
|-------------------|--------|---------|
| `{app}-precompute-refresh-secret` | Recovery script generated version | Cloud Scheduler precompute refresh |
| `{app}-precompute-monitor-secret` | Recovery script generated version | Cloud Scheduler precompute monitoring |
| `{app}-gmail-import-secret` | Recovery script generated version | Cloud Scheduler Gmail import |
| `{app}-creative-cache-refresh-secret` | Recovery script generated version | Creative cache refresh |
| `{app}-oauth-client-secret` | Recovery script or operator-provided value | OAuth2 Proxy Google login |
| `{app}-gmail-oauth-client` | Manual upload | Gmail API authentication |
| `{app}-gmail-token` | Manual upload | Gmail API token |
| `{app}-ab-service-account` | Manual upload | Authorized Buyers API |
| `{app}-serving-db-credentials` | Recovery script generated version | Postgres DSN |

### Bootstrap token

On GCP deployments, `CATSCAN_BOOTSTRAP_TOKEN` is generated at VM startup via `openssl rand -hex 24` and written to `/etc/catscan.env`. This prevents an attacker from racing to become admin on a fresh deploy. Retrieve it with:

```bash
sudo grep CATSCAN_BOOTSTRAP_TOKEN /etc/catscan.env
```

See [AUTHENTICATION.md](AUTHENTICATION.md) for the bootstrap flow.

---

## GCP Security Checklist

When deploying on Google Cloud Platform, verify:

### IAM & Service Accounts

- [ ] Service accounts have minimal required permissions
- [ ] No service account keys in the repository
- [ ] Use Workload Identity where possible (instead of JSON keys)

### Secret Manager

If using GCP Secret Manager:

```bash
# List secrets (verify no unexpected ones)
gcloud secrets list

# Check who can access secrets
gcloud secrets get-iam-policy SECRET_NAME
```

### Compute Engine

- [ ] VM has no public SSH port (use IAP tunneling)
- [ ] Startup scripts don't contain hardcoded secrets
- [ ] Metadata doesn't expose sensitive environment variables

```bash
# Check VM metadata for secrets
gcloud compute instances describe VM_NAME --zone=ZONE \
  --format='get(metadata.items)'
```

### Cloud Storage (if used)

- [ ] Buckets containing backups are not public
- [ ] Lifecycle rules delete old backups

---

## Pulling Upstream Changes Safely

When your fork pulls updates from the main repository:

```bash
# Fetch upstream
git fetch upstream

# Review changes before merging
git diff upstream/main -- .gitignore
git diff upstream/main -- .env.example

# Merge (your local secrets are safe - they're gitignored)
git merge upstream/main
```

Your `.env`, `terraform.tfvars`, and database files won't be affected because they're not tracked.

---

## Incident Response

If you accidentally commit secrets:

### 1. Rotate Immediately

```bash
# GCP service account key
gcloud iam service-accounts keys delete KEY_ID \
  --iam-account=SERVICE_ACCOUNT_EMAIL

# Generate new key
gcloud iam service-accounts keys create new-key.json \
  --iam-account=SERVICE_ACCOUNT_EMAIL
```

### 2. Coordinate history cleanup

Revoke or rotate the credential first and verify the dependent service still
works. Removing text from Git does not revoke access. Identify all affected refs,
mirrors and forks, prepare a reviewed history rewrite and recovery plan, then
coordinate it with maintainers. History rewriting and force pushes require
explicit approval because they invalidate existing clones and signatures.
Do not suppress an unresolved credential finding to make a release check green.

### 3. Check for Exposure

- Search GitHub/Gitee for the leaked content
- Check Google's Secret Scanner alerts
- Review GCP audit logs for unauthorized access

---

## Security Contact

If you discover a security issue in Cat-Scan:
- **Do not** open a public GitHub issue
- Email the maintainer directly
- Allow time for a fix before public disclosure

---

## Summary

| Category | Public (in repo) | Private (gitignored) |
|----------|------------------|----------------------|
| Application code | ✅ | |
| Docker configs | ✅ | |
| Documentation | ✅ | |
| `.env.example` | ✅ | |
| `.env` (real values) | | ✅ |
| `terraform.tfvars` | | ✅ |
| Service account JSON | | ✅ |
| Postgres backups/exports | | ✅ |
| CSV imports | | ✅ |
| Deploy prompts (real) | | ✅ |

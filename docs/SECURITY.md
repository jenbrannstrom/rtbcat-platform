# Security Guide

This document explains what data must stay private when deploying Cat-Scan, especially for forked instances.

## Golden Rule

**Code is public. Data and credentials are private.**

The Cat-Scan repository contains only application code. All sensitive data lives outside the repository:
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
| `prompts/deploy-catscan.md` | VM IPs, project IDs, domains | Targeted attacks |
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
prompts/deploy-catscan.md
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
cp prompts/deploy-catscan.example.md prompts/deploy-catscan.md

# Edit with your values
nano .env
```

### 3. GitHub Secrets (for CI/CD)

In your fork's GitHub settings, add:

| Secret | Description |
|--------|-------------|
| `GCP_SA_KEY` | Service account JSON for deployments |

And variables:

| Variable | Description |
|----------|-------------|
| `GCP_PROJECT` | Your GCP project ID |
| `GCP_ZONE` | VM zone (e.g., `europe-west1-b`) |
| `VM_NAME` | Your VM name |

### 4. Never Commit These

Even if you think it's "just for testing":
- Database files (`*.db`)
- Environment files (`.env`)
- Service account keys (`*.json`)
- Terraform state (`*.tfstate`)
- Your deploy prompts with real IPs

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

### 2. Remove from Git History

```bash
# Remove file from history (requires force push)
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch PATH_TO_SECRET' \
  --prune-empty --tag-name-filter cat -- --all

# Force push (coordinate with team!)
git push --force --all
```

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
| SQLite database | | ✅ |
| CSV imports | | ✅ |
| Deploy prompts (real) | | ✅ |

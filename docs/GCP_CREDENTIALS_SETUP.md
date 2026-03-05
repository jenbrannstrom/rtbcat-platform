# GCP Credentials Setup (OSS-Safe)

This guide shows how to configure Google Cloud credentials for Cat-Scan without committing sensitive values.

## Security Principles

- Never commit `.env`, `terraform.tfvars`, service-account JSON files, or tokens.
- Keep all secrets in your cloud secret manager or GitHub/Gitee secret store.
- Use least-privilege service accounts.
- Rotate credentials immediately if exposure is suspected.

## 1) Service Accounts You Need

Create separate service accounts:

1. `catscan-ci` (used by GitHub Actions build/deploy)
2. `catscan-vm` (attached to the GCE VM for runtime access)

Recommended roles for `catscan-ci`:

- `roles/artifactregistry.writer`
- `roles/compute.osLogin` (if workflow deploys via SSH/IAP)
- `roles/iap.tunnelResourceAccessor` (if using IAP tunnel)

Recommended roles for `catscan-vm`:

- `roles/secretmanager.secretAccessor`
- `roles/cloudsql.client`
- `roles/storage.objectAdmin` (or tighter bucket-scoped role)
- Additional product-specific roles as required by your collectors

## 2) Generate CI Key (if Workload Identity is not used)

```bash
gcloud iam service-accounts keys create /tmp/catscan-ci-key.json \
  --iam-account=catscan-ci@YOUR_PROJECT_ID.iam.gserviceaccount.com
```

Store this JSON as a repository secret and delete the local file immediately:

```bash
rm -f /tmp/catscan-ci-key.json
```

## 3) Configure Repository Variables/Secrets

Set these Actions variables:

- `GCP_PROJECT`
- `GCP_ZONE`
- `GCP_VM_NAME_PROD`
- `GCP_VM_NAME_STAGING`
- `IMAGE_REGISTRY` (format: `REGION-docker.pkg.dev/PROJECT/REPO`)
- Optional: `GIT_BRANCH`, `APP_DIR`, feature-toggle variables

Set these Actions secrets:

- `GCP_SA_KEY`
- Any runtime canary/auth secrets used by optional workflows

## 4) Runtime Secrets (VM/API)

Keep runtime secrets out of git. Use one backend:

- GCP Secret Manager (`SECRETS_BACKEND=gcp`) recommended for production
- Environment variables (`SECRETS_BACKEND=env`) for local development

Typical keys:

- `CATSCAN_API_KEY`
- `AUTHING_APP_ID`, `AUTHING_APP_SECRET`, `AUTHING_ISSUER` (if Authing enabled)
- `GMAIL_IMPORT_SECRET`, `PRECOMPUTE_REFRESH_SECRET`, `PRECOMPUTE_MONITOR_SECRET`
- AI provider keys (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `XAI_API_KEY`) if enabled

## 5) VM Identity and Access

- Attach `catscan-vm` service account to the VM.
- Prefer IAP-tunneled SSH over public SSH exposure.
- Restrict inbound firewall rules to required ports only.

## 6) Validation Checklist

Before production deploy:

- `gcloud auth list` shows expected account
- `gcloud secrets list --project YOUR_PROJECT_ID` works for authorized users only
- CI workflow can push/pull images from your Artifact Registry
- VM can fetch required secrets and pass `/health` + `/system/secrets-health`

## 7) Rotation Playbook

When rotating credentials:

1. Add new secret/key version
2. Redeploy/restart services to pick up new values
3. Validate health checks
4. Revoke old key/version

## References

- [INSTALL.md](../INSTALL.md)
- [SECURITY.md](SECURITY.md)
- [SECRETS_MIGRATION_GUIDE.md](SECRETS_MIGRATION_GUIDE.md)

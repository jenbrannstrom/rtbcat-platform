# Production Setup And Recovery

Cat-Scan production is recoverable from GitHub plus Google-managed state.

GitHub is the source of truth for:

- application code
- Dockerfiles and Compose definitions
- GitHub Actions build/deploy workflows
- Terraform resource definitions
- GCE startup/server configuration
- recovery and provisioning scripts

Google Cloud is the source of truth for:

- Secret Manager secret versions
- Cloud SQL data and backups
- Artifact Registry images built from GitHub commits
- DNS/static IP assignment after Terraform apply

Cloud Run is not used by the current production stack. Production runs on GCE
with Docker Compose, Nginx, OAuth2 Proxy, Cloud SQL Auth Proxy, Cloud Scheduler,
Secret Manager, Artifact Registry, GCS, and BigQuery.

## Production Components

| Component | Source of truth | Notes |
|---|---|---|
| App code | GitHub `main` | VM fetches from GitHub during deploy |
| API/dashboard images | GitHub Actions -> Artifact Registry | Tagged `sha-<shortsha>` |
| Infrastructure | `terraform/gcp` + GCS Terraform state | One production GCE VM, Cloud SQL, GSM, Scheduler, GCS, BigQuery |
| Server config | `terraform/gcp/startup.sh` | Writes Nginx, systemd, Docker override, Cloud SQL proxy |
| Runtime secrets | Google Secret Manager | Provisioned by `scripts/provision_gcp_runtime_config.sh` |
| DB data | Cloud SQL | Automated backups + logical export workflow |
| Scheduler jobs | Terraform resources + script-applied secret headers | Headers are secret values and are intentionally not committed |

## Retired: Staging

The production workflow no longer requires staging. Do not use `vm2` as a
promotion gate. Deployments are manual production deploys from GitHub Actions,
with health, version, secrets-health, and contract checks.

## Fresh Production Build

Run these steps from a machine with `gcloud` and `terraform`.

1. Clone GitHub.

```bash
git clone https://github.com/jenbrannstrom/rtbcat-platform.git
cd rtbcat-platform
```

2. Authenticate to Google Cloud.

```bash
gcloud auth login
gcloud config set project catscan-prod-202601
```

3. Prepare Terraform inputs.

```bash
cd terraform/gcp
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with production values. Do not commit it.

4. Bootstrap Terraform remote state.

```bash
cd ../..
scripts/bootstrap_gcp_terraform_state.sh \
  --project catscan-prod-202601 \
  --bucket catscan-prod-202601-tfstate \
  --init
```

This creates a versioned private GCS state bucket if missing and initializes the
`terraform/gcp` backend.

5. Apply Terraform.

```bash
cd terraform/gcp
terraform apply
```

Terraform creates the GCP resources and empty Secret Manager secret resources.
Secret values are provisioned in the next step.

If an existing production Artifact Registry repository already exists outside
Terraform, import it before apply:

```bash
terraform import google_artifact_registry_repository.docker \
  projects/catscan-prod-202601/locations/asia-southeast1/repositories/catscan
```

6. Provision GSM values, Cloud SQL credentials, and Scheduler headers.

```bash
cd ../..
scripts/provision_gcp_runtime_config.sh \
  --project catscan-prod-202601 \
  --region asia-southeast1 \
  --app-name catscan \
  --domain scan.rtb.cat \
  --db-instance catscan-production-serving \
  --db-name rtbcat_serving \
  --db-user rtbcat_serving \
  --gmail-oauth-client-file /secure/path/gmail-oauth-client.json \
  --gmail-token-file /secure/path/gmail-token.json \
  --ab-service-account-file /secure/path/catscan-service-account.json \
  --oauth-client-secret "$OAUTH_CLIENT_SECRET" \
  --github-repo jenbrannstrom/rtbcat-platform \
  --sync-github-canary-secret
```

If the scheduler or DB secrets already exist, the script keeps them unless
`--rotate-scheduler-secrets`, `--rotate-api-key`, or `--rotate-db-password` is
passed.

7. Trigger image build if needed.

Pushing code to `main` builds and publishes:

- `catscan-api:sha-<shortsha>`
- `catscan-dashboard:sha-<shortsha>`

8. Deploy production from GitHub Actions.

```bash
gh workflow run deploy.yml \
  --ref main \
  -f target=production \
  -f confirm=DEPLOY \
  -f reason="production recovery or deploy"
```

9. Verify production.

```bash
curl -sS https://scan.rtb.cat/health
curl -sS https://scan.rtb.cat/api/health
```

The health payload must show the expected `version` or `git_sha`.

If GSM values are rotated outside a deploy, refresh the VM env and recreate the
API container:

```bash
gcloud compute ssh catscan-production-sg \
  --zone asia-southeast1-b \
  --tunnel-through-iap \
  --command "cd /opt/catscan && sudo bash scripts/refresh_gcp_vm_runtime_env.sh --recreate-api"
```

## Restore From Cloud SQL Backup

Cloud SQL automated backups and PITR are enabled by Terraform for production.

For a point-in-time restore, use the GCP Console or:

```bash
gcloud sql backups list --instance catscan-production-serving
```

Restore into a new Cloud SQL instance first, validate the data, then repoint the
serving credentials in GSM by rerunning:

```bash
scripts/provision_gcp_runtime_config.sh \
  --project catscan-prod-202601 \
  --domain scan.rtb.cat \
  --db-instance <restored-instance-name> \
  --db-name rtbcat_serving \
  --db-user rtbcat_serving \
  --rotate-db-password
```

The scheduled logical backup workflow is `.github/workflows/cloudsql-logical-backup.yml`.
It exports compressed SQL dumps to the configured GCS bucket.

## Secret Inventory

The production secret IDs are:

- `catscan-gmail-oauth-client`
- `catscan-gmail-token`
- `catscan-ab-service-account`
- `catscan-api-key`
- `catscan-precompute-refresh-secret`
- `catscan-precompute-monitor-secret`
- `catscan-gmail-import-secret`
- `catscan-creative-cache-refresh-secret`
- `catscan-oauth-client-secret`
- `catscan-serving-db-credentials`
- `catscan-deploy-key` if the repo is private

The recovery script creates missing secret resources and adds missing generated
versions where possible. Human-provided JSON credentials still need to come from
the secure operator store.

## GitHub Repository Variables

Production deploy expects these repository variables:

- `GCP_PROJECT`
- `GCP_REGION`
- `GCP_ZONE`
- `GCP_VM_PRODUCTION`
- `CLOUDSQL_INSTANCE`
- `CLOUDSQL_CONNECTION_NAME`
- `IMAGE_REGISTRY`
- `GCP_REPOSITORY`
- `GCP_REGISTRY_HOST`
- `PRODUCTION_API_BASE_URL`

GitHub secret:

- `GCP_SA_KEY`
- `CATSCAN_CANARY_BEARER_TOKEN` mirrors `catscan-api-key` for scheduled runtime guardrails and API automation

## Recovery Checks

After rebuild or restore:

```bash
gh run list --workflow=build-and-push.yml --limit=3
gh run list --workflow=deploy.yml --limit=3
gcloud scheduler jobs list --project=catscan-prod-202601 --location=asia-southeast1
gcloud secrets list --project=catscan-prod-202601 --filter='name:catscan-'
```

Then verify:

- `/health` is healthy
- `/api/health` reports the intended SHA
- `scripts/verify_secrets_health.sh` passes inside the API container during deploy
- Gmail import and precompute scheduler jobs have secret headers
- Cloud SQL latest backup exists

# Terraform State Import — Final Drift Report

**Date:** 2026-03-05 (import), 2026-03-06 (verification + regression fix)
**Performed by:** Claude (terraform import + refresh-only — no `terraform apply` was run)

## Plan Gating Results

| Stack | `terraform plan -detailed-exitcode` | Add | Change | Destroy | Replace |
|---|---|---|---|---|---|
| `terraform/gcp/` | **EXIT_CODE=0** | 0 | 0 | 0 | 0 |
| `terraform/gcp_sg_vm2/` | **EXIT_CODE=0** | 0 | 0 | 0 | 0 |

**Both stacks pass plan gating: zero diff.**

---

## 1. `terraform/gcp/` — Main Stack (40 resources)

### Resources in State
| Category | Count | Resources |
|---|---|---|
| Compute | 4 | address, instance, 2 firewalls (http, https) |
| Firewall | 1 | IAP firewall rule |
| Storage | 2 | raw_parquet bucket + IAM |
| BigQuery | 2 | dataset + raw_facts table |
| Cloud SQL | 3 | instance + database + user |
| Secret Manager | 9 | 9 secret resources |
| Secret IAM | 8 | 8 IAM bindings |
| IAM | 2 | cloudsql.client + logging.logWriter |
| Service Account | 1 | catscan-production-sa |
| API Services | 6 | bigquery, sqladmin, secretmanager, cloudscheduler, monitoring, logging |
| Scheduler | 1 | gmail-import |
| **Total** | **39 managed + 1 data** | |

### Config Changes Made (vs original main.tf)
1. **Removed `random` provider** and all 6 `random_*` resources — secrets come from GSM
2. **Removed `google_storage_bucket.catscan`** — data bucket doesn't exist in production
3. **Removed `google_bigquery_dataset.catscan[0]`** — duplicate dataset
4. **Removed `google_project_iam_member.bigquery_job_user`** — not in production
5. **Removed `google_bigquery_dataset_iam_member.bigquery_data_editor`** — not in production
6. **Removed ALL `google_secret_manager_secret_version.*` resources** — managed externally via gcloud
7. **Removed `google_cloud_scheduler_job.precompute_refresh`** — doesn't exist in production
8. **Removed `google_cloud_scheduler_job.creative_cache_refresh`** — doesn't exist in production
9. **Removed ALL monitoring resources** (uptime check, 2 alert policies, logging metric) — none exist
10. **Removed `create_sg_instance` parallel resources** — managed by separate sg_vm2 stack
11. **Removed `google_secret_manager_secret_iam_member.serving_db_credentials_access`** — no binding in prod
12. **Fixed compute address name**: `catscan-production-ip` -> `catscan-production-sg-ip`
13. **Fixed compute instance name**: `catscan-production` -> `catscan-production-sg`
14. **Fixed scheduler job name**: `catscan-gmail-import` -> `gmail-import`
15. **Fixed BigQuery raw_facts schema**: 24 columns, partition on `metric_date`, clustering on `buyer_account_id`
16. **Added `lifecycle { ignore_changes }` on**: compute instance (startup_script, metadata, image), SQL instance (disk_size), SQL user (password), BQ table (schema), scheduler (headers, uri)
17. **Removed `google_oauth_client_secret`** from templatefile vars — OAuth secret fetched from GSM at runtime via `oauth_client_secret_id`
18. **Fixed startup.sh template escape**: `${ENABLE_HTTPS:-}` -> `$${ENABLE_HTTPS:-}`

### Variables Cleaned Up
Removed unused variables: `google_oauth_client_secret`, `cloudflare_api_token`, `cloudflare_zone_id`, `precompute_refresh_schedule`, `creative_cache_refresh_schedule`, `parquet_retention_days`, `bigquery_partition_retention_days`, `create_sg_instance`

Updated defaults to match production:
- `cloudsql_tier`: `db-perf-optimized-N-2` -> `db-custom-1-3840`
- `cloudsql_availability_type`: `REGIONAL` -> `ZONAL`
- `cloudsql_disk_size_gb`: 10 -> `118`
- `boot_disk_size`: 30 -> `80`

### Resources in Production but NOT in TF
| Resource | GCP ID | Notes |
|---|---|---|
| Secret | `catscan-deploy-key` | SSH deploy key for GitHub |
| Secret | `catscan-oauth-client-secret-sg2` | OAuth secret for SG2 instance |
| Secret | `gmail-token` | Legacy name (duplicate of `catscan-gmail-token`) |
| Service Account | `catscan-ci@...` | CI/CD service account |
| Service Account | `catscan-api@...` | API service account (AB credentials) |
| IAM roles | `artifactregistry.writer`, `compute.instanceAdmin.v1`, etc. | On SA, not in TF |
| GCS bucket | `catscan-prod-202601_cloudbuild` | Cloud Build bucket |
| BQ tables | `rtb_bid_filtering`, `rtb_bidstream`, `rtb_daily` | Additional analytics tables |

---

## 2. `terraform/gcp_sg_vm2/` — SG VM2 Stack (2 resources)

### Resources in State
| Resource | TF Address | GCP Name |
|---|---|---|
| Static IP | `google_compute_address.catscan_sg_vm2` | `catscan-production-sg2-ip` |
| VM Instance | `google_compute_instance.catscan_sg_vm2` | `catscan-production-sg2` |

### Config Changes Made
1. **Removed `random` provider** and all `random_*` resources
2. **Removed `google_oauth_client_secret` variable** — not used in template
3. **Added `lifecycle { ignore_changes }` on**: startup_script, metadata, boot disk image
4. **Fixed startup.sh template**: removed old secret template vars, added `oauth_client_secret_id`
5. **Fixed startup.sh template escape**: `${ENABLE_HTTPS:-}` -> `$${ENABLE_HTTPS:-}`

---

## 3. Secret Version Management — Design Decision

**Decision:** Terraform manages secret *resources* and *IAM* only. Secret *versions* (data) are managed externally via `gcloud secrets versions add`.

**Rationale:**
- ADC credentials lack `secretmanager.versions.access` — can't import secret data
- Secret data changes (key rotation, token refresh) should NOT require TF workflow
- Prevents secret values from appearing in tfstate
- Cleaner separation: infra (TF) vs operations (gcloud/scripts)

---

## 4. State Fixes Applied

### `terraform_labels` Fix
After `terraform import`, the Google provider leaves `labels` and `terraform_labels` as `{}` in state while `effective_labels` has correct values. Fixed by:
1. `terraform state pull > state.json`
2. Python script: copy `effective_labels` -> `labels` + `terraform_labels`
3. Increment serial
4. `terraform state push state.json`

Applied to: 12 resources in gcp/, 2 resources in gcp_sg_vm2/

### IAM Import Format Fix
IAM member resources require space-separated format, not slash-separated:
```
# WRONG (causes "Wrong number of parts" error):
terraform import 'google_project_iam_member.cloudsql_client' 'project/role/member'

# CORRECT:
terraform import 'google_project_iam_member.cloudsql_client' 'project role member'
```

---

## 5. Verification

```
# gcp/ stack
$ cd terraform/gcp && terraform plan -detailed-exitcode
No changes. Your infrastructure matches the configuration.
EXIT_CODE=0

# gcp_sg_vm2/ stack
$ cd terraform/gcp_sg_vm2 && terraform plan -detailed-exitcode
No changes. Your infrastructure matches the configuration.
EXIT_CODE=0
```

### Safety Confirmation
- **No `terraform apply` was run** (only `terraform apply -refresh-only` to sync state)
- **No production resources were modified**
- State files are gitignored and not committed
- tfvars files are gitignored and not committed

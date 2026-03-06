# Terraform Import Map

**Date:** 2026-03-05
**Project:** catscan-prod-202601
**Region:** asia-southeast1

## terraform/gcp/ — Import Commands

```bash
cd terraform/gcp
terraform init

# Service Account
terraform import google_service_account.catscan projects/catscan-prod-202601/serviceAccounts/catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com

# IAM (NOTE: space-separated format, NOT slash-separated)
terraform import 'google_project_iam_member.cloudsql_client' 'catscan-prod-202601 roles/cloudsql.client serviceAccount:catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com'
terraform import 'google_project_iam_member.catscan_logging' 'catscan-prod-202601 roles/logging.logWriter serviceAccount:catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com'

# Firewalls
terraform import google_compute_firewall.allow_http projects/catscan-prod-202601/global/firewalls/catscan-production-allow-http
terraform import 'google_compute_firewall.allow_https[0]' projects/catscan-prod-202601/global/firewalls/catscan-production-allow-https
terraform import google_compute_firewall.allow_iap projects/catscan-prod-202601/global/firewalls/catscan-production-allow-iap

# Storage
terraform import google_storage_bucket.raw_parquet rtbcat-raw-parquet-sg-202601
terraform import 'google_storage_bucket_iam_member.raw_parquet_storage' 'b/rtbcat-raw-parquet-sg-202601 roles/storage.objectAdmin serviceAccount:catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com'

# API Services
terraform import google_project_service.bigquery catscan-prod-202601/bigquery.googleapis.com
terraform import google_project_service.sqladmin catscan-prod-202601/sqladmin.googleapis.com
terraform import google_project_service.secretmanager catscan-prod-202601/secretmanager.googleapis.com
terraform import google_project_service.cloudscheduler catscan-prod-202601/cloudscheduler.googleapis.com
terraform import google_project_service.monitoring catscan-prod-202601/monitoring.googleapis.com
terraform import google_project_service.logging catscan-prod-202601/logging.googleapis.com

# BigQuery
terraform import google_bigquery_dataset.rtbcat_analytics projects/catscan-prod-202601/datasets/rtbcat_analytics
terraform import google_bigquery_table.raw_facts projects/catscan-prod-202601/datasets/rtbcat_analytics/tables/raw_facts

# Cloud SQL
terraform import google_sql_database_instance.rtbcat_serving catscan-production-serving
terraform import google_sql_database.serving_db projects/catscan-prod-202601/instances/catscan-production-serving/databases/rtbcat_serving
terraform import google_sql_user.serving_user catscan-prod-202601/catscan-production-serving/rtbcat_serving

# Compute
terraform import google_compute_address.catscan projects/catscan-prod-202601/regions/asia-southeast1/addresses/catscan-production-sg-ip
terraform import google_compute_instance.catscan projects/catscan-prod-202601/zones/asia-southeast1-b/instances/catscan-production-sg

# Secret Manager Secrets
terraform import google_secret_manager_secret.gmail_oauth_client projects/catscan-prod-202601/secrets/catscan-gmail-oauth-client
terraform import google_secret_manager_secret.gmail_token projects/catscan-prod-202601/secrets/catscan-gmail-token
terraform import google_secret_manager_secret.ab_service_account projects/catscan-prod-202601/secrets/catscan-ab-service-account
terraform import google_secret_manager_secret.precompute_refresh_secret projects/catscan-prod-202601/secrets/catscan-precompute-refresh-secret
terraform import google_secret_manager_secret.precompute_monitor_secret projects/catscan-prod-202601/secrets/catscan-precompute-monitor-secret
terraform import google_secret_manager_secret.gmail_import_secret projects/catscan-prod-202601/secrets/catscan-gmail-import-secret
terraform import google_secret_manager_secret.creative_cache_refresh_secret projects/catscan-prod-202601/secrets/catscan-creative-cache-refresh-secret
terraform import google_secret_manager_secret.oauth_client_secret projects/catscan-prod-202601/secrets/catscan-oauth-client-secret
terraform import google_secret_manager_secret.serving_db_credentials projects/catscan-prod-202601/secrets/catscan-serving-db-credentials

# Secret Manager IAM (space-separated format)
terraform import 'google_secret_manager_secret_iam_member.gmail_oauth_client_access' 'projects/catscan-prod-202601/secrets/catscan-gmail-oauth-client roles/secretmanager.secretAccessor serviceAccount:catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com'
terraform import 'google_secret_manager_secret_iam_member.gmail_token_access' 'projects/catscan-prod-202601/secrets/catscan-gmail-token roles/secretmanager.secretAccessor serviceAccount:catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com'
terraform import 'google_secret_manager_secret_iam_member.ab_service_account_access' 'projects/catscan-prod-202601/secrets/catscan-ab-service-account roles/secretmanager.secretAccessor serviceAccount:catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com'
terraform import 'google_secret_manager_secret_iam_member.precompute_refresh_secret_access' 'projects/catscan-prod-202601/secrets/catscan-precompute-refresh-secret roles/secretmanager.secretAccessor serviceAccount:catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com'
terraform import 'google_secret_manager_secret_iam_member.precompute_monitor_secret_access' 'projects/catscan-prod-202601/secrets/catscan-precompute-monitor-secret roles/secretmanager.secretAccessor serviceAccount:catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com'
terraform import 'google_secret_manager_secret_iam_member.gmail_import_secret_access' 'projects/catscan-prod-202601/secrets/catscan-gmail-import-secret roles/secretmanager.secretAccessor serviceAccount:catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com'
terraform import 'google_secret_manager_secret_iam_member.creative_cache_refresh_secret_access' 'projects/catscan-prod-202601/secrets/catscan-creative-cache-refresh-secret roles/secretmanager.secretAccessor serviceAccount:catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com'
terraform import 'google_secret_manager_secret_iam_member.oauth_client_secret_access' 'projects/catscan-prod-202601/secrets/catscan-oauth-client-secret roles/secretmanager.secretAccessor serviceAccount:catscan-production-sa@catscan-prod-202601.iam.gserviceaccount.com'

# Scheduler
terraform import google_cloud_scheduler_job.gmail_import projects/catscan-prod-202601/locations/asia-southeast1/jobs/gmail-import

# Post-import: sync state
terraform apply -refresh-only -auto-approve
```

## terraform/gcp_sg_vm2/ — Import Commands

```bash
cd terraform/gcp_sg_vm2
terraform init

terraform import google_compute_address.catscan_sg_vm2 projects/catscan-prod-202601/regions/asia-southeast1/addresses/catscan-production-sg2-ip
terraform import google_compute_instance.catscan_sg_vm2 projects/catscan-prod-202601/zones/asia-southeast1-b/instances/catscan-production-sg2

# Post-import: sync state
terraform apply -refresh-only -auto-approve
```

## Post-Import: Fix terraform_labels

After import, run this Python script to fix the Google provider's `terraform_labels` issue:

```python
import json

# Pull state
# terraform state pull > state.json

with open('state.json', 'r') as f:
    state = json.load(f)

for resource in state.get('resources', []):
    if resource.get('mode') == 'data':
        continue
    for instance in resource.get('instances', []):
        attrs = instance.get('attributes', {})
        if 'terraform_labels' in attrs and 'effective_labels' in attrs:
            effective = attrs.get('effective_labels', {})
            if effective and not attrs.get('terraform_labels'):
                attrs['labels'] = dict(effective)
                attrs['terraform_labels'] = dict(effective)

state['serial'] = state.get('serial', 0) + 1

with open('state_fixed.json', 'w') as f:
    json.dump(state, f, indent=2)

# Push state
# terraform state push state_fixed.json
```

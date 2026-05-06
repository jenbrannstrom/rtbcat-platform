# Secrets Migration Guide (env, GCP, AWS, optional Alibaba)

This guide shows how Cat-Scan secret handling works with the unified secrets
manager and startup validation.

For production rebuilds, use
[`scripts/provision_gcp_runtime_config.sh`](../scripts/provision_gcp_runtime_config.sh)
after Terraform has created the GCP resources. That script creates missing GSM
secret versions, provisions Cloud SQL serving credentials, and applies Cloud
Scheduler secret headers.

## 1) Define logical keys

Use these logical keys in all backends:

- `CATSCAN_API_KEY`
- `AUTHING_APP_ID`
- `AUTHING_APP_SECRET`
- `AUTHING_ISSUER`
- `GMAIL_IMPORT_SECRET`
- `CREATIVE_CACHE_REFRESH_SECRET`
- `PRECOMPUTE_REFRESH_SECRET`
- `PRECOMPUTE_MONITOR_SECRET`
- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`
- `XAI_API_KEY`

## 2) Backend selection

Set one backend:

```bash
SECRETS_BACKEND=env|gcp|aws|alibaba
SECRETS_NAME_PREFIX=catscan
SECRETS_PREFER_ENV=true
SECRETS_HEALTH_STRICT=false
```

For the secure default OSS install, use `env`, `gcp`, or `aws`. The Alibaba
backend remains optional code-level support, but its vendor SDK is not shipped
in the default dependency bundles because upstream currently constrains
`cryptography` below the secure baseline used by this repo.

## 3) Backend-specific examples

### A) `env` backend (local/dev)

```bash
SECRETS_BACKEND=env
GMAIL_IMPORT_SECRET=replace-me
PRECOMPUTE_REFRESH_SECRET=replace-me
PRECOMPUTE_MONITOR_SECRET=replace-me
CREATIVE_CACHE_REFRESH_SECRET=replace-me
GEMINI_API_KEY=replace-me
ANTHROPIC_API_KEY=replace-me
XAI_API_KEY=replace-me
CATSCAN_LANGUAGE_AI_PROVIDER=gemini
```

### B) `gcp` backend (Google Secret Manager)

```bash
SECRETS_BACKEND=gcp
GCP_PROJECT_ID=my-gcp-project
SECRETS_NAME_PREFIX=catscan
SECRETS_PREFER_ENV=false
```

Create or update production secrets with the recovery script:

```bash
scripts/provision_gcp_runtime_config.sh \
  --project catscan-prod-202601 \
  --domain scan.rtb.cat \
  --db-instance catscan-production-serving \
  --gmail-oauth-client-file /secure/path/gmail-oauth-client.json \
  --gmail-token-file /secure/path/gmail-token.json \
  --ab-service-account-file /secure/path/catscan-service-account.json \
  --oauth-client-secret "$OAUTH_CLIENT_SECRET"
```

The script does not print secret values. It keeps existing generated scheduler
and DB secrets unless explicit rotation flags are passed.

### C) `aws` backend (AWS Secrets Manager)

```bash
SECRETS_BACKEND=aws
AWS_REGION=ap-southeast-1
SECRETS_NAME_PREFIX=catscan
SECRETS_PREFER_ENV=false
```

Create secret (example):

```bash
aws secretsmanager create-secret \
  --name catscan-gmail-import-secret \
  --secret-string "replace-me"
```

### D) `alibaba` backend (Alibaba Cloud KMS Secrets Manager)

```bash
SECRETS_BACKEND=alibaba
ALIBABA_REGION_ID=cn-hangzhou
ALIBABA_ACCESS_KEY_ID=your-ak
ALIBABA_ACCESS_KEY_SECRET=your-sk
ALIBABA_KMS_ENDPOINT=kms.cn-hangzhou.aliyuncs.com
SECRETS_NAME_PREFIX=catscan
SECRETS_PREFER_ENV=false
```

Create secret (example via console/API), name with prefix convention:

- `catscan-gmail-import-secret`
- `catscan-precompute-refresh-secret`

## 4) Optional key overrides

If your secret names differ, map them explicitly:

```bash
SECRET_ID_GMAIL_IMPORT_SECRET=my-custom-gmail-secret
SECRET_ID_PRECOMPUTE_REFRESH_SECRET=my-precompute-refresh
```

## 5) Enable strict rollout (after validation)

When all required secrets are in place, enforce at startup:

```bash
SECRETS_HEALTH_STRICT=true
```

If required secrets for enabled features are missing, the API will fail fast on startup.

## 6) Runtime verification

Use the status endpoint:

```bash
GET /api/system/secrets-health
```

Response is non-sensitive: backend, enabled features, per-key configured status, and missing key names.

# Secrets Migration Guide (env, GCP, AWS, Alibaba)

This guide shows how to migrate Cat-Scan secret handling to the unified secrets manager with startup validation.

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

## 2) Backend selection

Set one backend:

```bash
SECRETS_BACKEND=env|gcp|aws|alibaba
SECRETS_NAME_PREFIX=catscan
SECRETS_PREFER_ENV=true
SECRETS_HEALTH_STRICT=false
```

## 3) Backend-specific examples

### A) `env` backend (local/dev)

```bash
SECRETS_BACKEND=env
GMAIL_IMPORT_SECRET=replace-me
PRECOMPUTE_REFRESH_SECRET=replace-me
PRECOMPUTE_MONITOR_SECRET=replace-me
CREATIVE_CACHE_REFRESH_SECRET=replace-me
GEMINI_API_KEY=replace-me
```

### B) `gcp` backend (Google Secret Manager)

```bash
SECRETS_BACKEND=gcp
GCP_PROJECT_ID=my-gcp-project
SECRETS_NAME_PREFIX=catscan
SECRETS_PREFER_ENV=false
```

Create secrets (example):

```bash
echo -n "replace-me" | gcloud secrets create catscan-gmail-import-secret --data-file=-
echo -n "replace-me" | gcloud secrets create catscan-precompute-refresh-secret --data-file=-
```

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

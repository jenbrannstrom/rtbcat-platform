# GCP Credentials Setup

This guide covers the minimum Google Cloud credentials needed to run Cat-Scan safely.

## 1) Service Account for Google Authorized Buyers API

Create a service account in your GCP project and grant only the roles needed for your deployment.

Store the JSON key outside the repository:

```bash
mkdir -p ~/.catscan/credentials
cp /path/to/downloaded-key.json ~/.catscan/credentials/google-credentials.json
chmod 600 ~/.catscan/credentials/google-credentials.json
```

Set:

```bash
GOOGLE_APPLICATION_CREDENTIALS=~/.catscan/credentials/google-credentials.json
```

## 2) Runtime Secrets (Do Not Commit)

At minimum, configure:

- `POSTGRES_DSN`
- `POSTGRES_SERVING_DSN`
- `CATSCAN_API_KEY`

Feature-specific secrets (Gmail import, conversion webhooks, AI keys) should be added only when those features are enabled.

## 3) Production Recommendation

Use a secrets manager (for example, GCP Secret Manager) instead of plaintext `.env` files wherever possible.

See:

- [`SECURITY.md`](../SECURITY.md)
- [`SECRETS_MIGRATION_GUIDE.md`](SECRETS_MIGRATION_GUIDE.md)
- [`DEPLOY_CHECKLIST.md`](DEPLOY_CHECKLIST.md)

## 4) Verify Before Deploy

Run:

```bash
curl -sS https://your-domain.example/api/health
curl -sS https://your-domain.example/api/system/secrets-health
```

In production, keep:

- `DISABLE_OPENAPI_DOCS=true`
- `SECRETS_HEALTH_STRICT=true`

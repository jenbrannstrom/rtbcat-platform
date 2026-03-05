# Secret Rotation Runbook

Procedures for rotating Cat-Scan secrets stored in GCP Secret Manager.

## Prerequisites

- `gcloud` CLI authenticated with project admin or secret manager admin role
- SSH access to the VM (for bootstrap token)

## 1. Rotate a Scheduler Secret

Example: rotating `precompute-refresh-secret`.

```bash
# Generate new secret value
NEW_SECRET=$(openssl rand -hex 24)

# Add new version to GSM
echo -n "$NEW_SECRET" | gcloud secrets versions add catscan-precompute-refresh-secret --data-file=-

# Restart the VM's catscan service so startup.sh re-fetches
gcloud compute ssh VM_NAME --zone=ZONE -- 'sudo systemctl restart catscan'
```

The same steps apply to:
- `catscan-precompute-monitor-secret`
- `catscan-gmail-import-secret`
- `catscan-creative-cache-refresh-secret`

After rotation, update the corresponding Cloud Scheduler job headers with the new secret value.

## 2. Rotate the OAuth Client Secret

```bash
# 1. Rotate in Google Cloud Console → APIs & Services → Credentials
# 2. Copy the new client secret

# 3. Update GSM
echo -n "NEW_CLIENT_SECRET_HERE" | gcloud secrets versions add catscan-oauth-client-secret --data-file=-

# 4. Restart catscan + oauth2-proxy
gcloud compute ssh VM_NAME --zone=ZONE -- 'sudo systemctl restart catscan && sudo systemctl restart oauth2-proxy'
```

## 3. Rotate the Bootstrap Token

The bootstrap token is only relevant before the first admin is created. After bootstrap is completed, the token is ignored.

To regenerate (e.g., if the VM was re-provisioned before first admin was created):

```bash
# SSH into the VM
gcloud compute ssh VM_NAME --zone=ZONE

# Generate and write new token
NEW_TOKEN=$(openssl rand -hex 24)
sudo sed -i "s/^CATSCAN_BOOTSTRAP_TOKEN=.*/CATSCAN_BOOTSTRAP_TOKEN=$NEW_TOKEN/" /etc/catscan.env
sudo grep CATSCAN_BOOTSTRAP_TOKEN /opt/catscan/.env && \
  sudo sed -i "s/^CATSCAN_BOOTSTRAP_TOKEN=.*/CATSCAN_BOOTSTRAP_TOKEN=$NEW_TOKEN/" /opt/catscan/.env

# Restart the app
sudo systemctl restart catscan
```

## 4. Verify via Health Endpoint

After any rotation, check that the secrets health endpoint reports healthy:

```bash
curl -s https://DOMAIN/api/system/secrets-health | jq '.healthy, .features'
```

All enabled features should show `"healthy": true`.

## 5. Emergency Fallback to Environment Variables

If GSM is unreachable (e.g., IAM misconfiguration), secrets can be set directly:

```bash
# SSH into the VM
gcloud compute ssh VM_NAME --zone=ZONE

# Edit the environment file
sudo nano /etc/catscan.env
# Add/update: PRECOMPUTE_REFRESH_SECRET=your-value

# Copy to app .env
sudo cp /etc/catscan.env /opt/catscan/.env

# Restart
sudo systemctl restart catscan
```

The app's secrets manager reads `SECRETS_PREFER_ENV=true` by default, so explicit env vars always take precedence over GSM values.

## 6. Disable Old Secret Versions

After confirming rotation works, disable old versions to prevent rollback:

```bash
# List versions
gcloud secrets versions list catscan-precompute-refresh-secret

# Disable old version (keep latest only)
gcloud secrets versions disable VERSION_ID --secret=catscan-precompute-refresh-secret
```

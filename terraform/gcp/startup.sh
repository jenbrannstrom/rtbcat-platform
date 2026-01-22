#!/bin/bash
# Cat-Scan GCE Startup Script
# Hardened deployment with security best practices
#
# SECURITY FEATURES:
# - Services bind to 127.0.0.1 only (not exposed to internet)
# - Nginx/Caddy terminates SSL and proxies to internal services
# - Automatic security updates enabled
# - Firewall rules managed by Terraform (ports 3000/8000 blocked)

set -euo pipefail

# Variables from Terraform (injected at deploy time)
APP_NAME="${app_name}"
ENVIRONMENT="${environment}"
DOMAIN_NAME="${domain_name}"
ENABLE_HTTPS="${enable_https}"
GITHUB_REPO="${github_repo}"
GITHUB_BRANCH="${github_branch}"
GCS_BUCKET="${gcs_bucket}"

# OAuth2 Proxy - Google Authentication (REQUIRED)
GOOGLE_OAUTH_CLIENT_ID="${google_oauth_client_id}"
GOOGLE_OAUTH_CLIENT_SECRET="${google_oauth_client_secret}"
ALLOWED_EMAIL_DOMAINS='${jsonencode(allowed_email_domains)}'

# Paths
APP_DIR="/opt/catscan"
DATA_DIR="/home/catscan/.catscan"
LOG_FILE="/var/log/catscan-setup.log"

exec > >(tee -a "$LOG_FILE") 2>&1
echo "=== Cat-Scan Setup Started: $(date) ==="

# -----------------------------------------------------------------------------
# 1. System Updates and Security
# -----------------------------------------------------------------------------
echo ">>> Installing updates and security packages..."

apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# Enable automatic security updates
apt-get install -y unattended-upgrades
cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

# Install required packages
apt-get install -y \
    docker.io \
    docker-compose \
    nginx \
    certbot \
    python3-certbot-nginx \
    sqlite3 \
    curl \
    git \
    jq \
    fail2ban

# Configure Docker to authenticate with Artifact Registry
echo ">>> Configuring Docker authentication for Artifact Registry..."
gcloud auth configure-docker europe-west1-docker.pkg.dev --quiet

# -----------------------------------------------------------------------------
# 1b. Install OAuth2 Proxy (Google Authentication)
# -----------------------------------------------------------------------------
echo ">>> Installing OAuth2 Proxy..."

OAUTH2_PROXY_VERSION="7.6.0"
wget -q "https://github.com/oauth2-proxy/oauth2-proxy/releases/download/v$${OAUTH2_PROXY_VERSION}/oauth2-proxy-v$${OAUTH2_PROXY_VERSION}.linux-amd64.tar.gz" -O /tmp/oauth2-proxy.tar.gz
tar -xzf /tmp/oauth2-proxy.tar.gz -C /tmp
mv /tmp/oauth2-proxy-v$${OAUTH2_PROXY_VERSION}.linux-amd64/oauth2-proxy /usr/local/bin/
chmod +x /usr/local/bin/oauth2-proxy
rm -rf /tmp/oauth2-proxy*

# Generate cookie secret (must be exactly 32 bytes for AES-256)
# Use hex output and take first 32 chars, then convert to the format oauth2-proxy expects
COOKIE_SECRET=$(openssl rand -hex 16)

# Determine email domains config
if [ "$ALLOWED_EMAIL_DOMAINS" = "[]" ] || [ -z "$ALLOWED_EMAIL_DOMAINS" ]; then
    EMAIL_DOMAINS_CONFIG='email_domains = ["*"]'
else
    # Convert JSON array to oauth2-proxy format
    EMAIL_DOMAINS_CONFIG="email_domains = $ALLOWED_EMAIL_DOMAINS"
fi

# Create OAuth2 Proxy config
cat > /etc/oauth2-proxy.cfg << OAUTHEOF
# OAuth2 Proxy Configuration for Cat-Scan
# All requests require Google authentication

provider = "google"
client_id = "$GOOGLE_OAUTH_CLIENT_ID"
client_secret = "$GOOGLE_OAUTH_CLIENT_SECRET"
cookie_secret = "$COOKIE_SECRET"
cookie_secure = true
cookie_name = "_catscan_oauth"

# Redirect URL after authentication
redirect_url = "https://$DOMAIN_NAME/oauth2/callback"

# Listen on localhost only (nginx proxies to us)
http_address = "127.0.0.1:4180"

# Email domain restrictions
$EMAIL_DOMAINS_CONFIG

# Session settings
cookie_expire = "168h"  # 7 days
cookie_refresh = "1h"

# Skip authentication for health check
skip_auth_routes = ["/health"]

# Pass user info to upstream
set_xauthrequest = true
pass_user_headers = true
OAUTHEOF

chmod 600 /etc/oauth2-proxy.cfg

# Create OAuth2 Proxy systemd service
cat > /etc/systemd/system/oauth2-proxy.service << 'SERVICEEOF'
[Unit]
Description=OAuth2 Proxy
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/oauth2-proxy --config=/etc/oauth2-proxy.cfg
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable oauth2-proxy

# -----------------------------------------------------------------------------
# 2. Create Application User
# -----------------------------------------------------------------------------
echo ">>> Creating catscan user..."

if ! id -u catscan &>/dev/null; then
    useradd -m -s /bin/bash catscan
fi

usermod -aG docker catscan

# Create directories
mkdir -p "$APP_DIR" "$DATA_DIR/credentials" "$DATA_DIR/thumbnails" "$DATA_DIR/imports"
chown -R catscan:catscan "$APP_DIR" "$DATA_DIR"

# -----------------------------------------------------------------------------
# 2b. Fetch Credentials from Secret Manager (ONE-TIME SETUP)
# -----------------------------------------------------------------------------
# These secrets are uploaded ONCE via gcloud or Terraform.
# The VM pulls them automatically on every deployment.
echo ">>> Fetching credentials from Secret Manager..."

PROJECT_ID=$(curl -s http://metadata.google.internal/computeMetadata/v1/project/project-id -H 'Metadata-Flavor: Google')

# Gmail OAuth Client
echo "  - Fetching Gmail OAuth client..."
gcloud secrets versions access latest --secret="${app_name}-gmail-oauth-client" --project="$PROJECT_ID" \
    > "$DATA_DIR/credentials/gmail-oauth-client.json" 2>/dev/null || true

if [ -s "$DATA_DIR/credentials/gmail-oauth-client.json" ]; then
    echo "    ✓ Gmail OAuth client loaded"
else
    echo "    ⚠ Gmail OAuth client not found in Secret Manager"
    echo "    Upload with: gcloud secrets versions add ${app_name}-gmail-oauth-client --data-file=gmail-oauth-client.json"
fi

# Gmail Token (may not exist on first deploy)
echo "  - Fetching Gmail token..."
gcloud secrets versions access latest --secret="${app_name}-gmail-token" --project="$PROJECT_ID" \
    > "$DATA_DIR/credentials/gmail-token.json" 2>/dev/null || true

if [ -s "$DATA_DIR/credentials/gmail-token.json" ]; then
    echo "    ✓ Gmail token loaded"
else
    echo "    ⚠ Gmail token not found (run gmail_auth.py after deploy, then upload token)"
fi

# Authorized Buyers Service Account
echo "  - Fetching AB service account..."
gcloud secrets versions access latest --secret="${app_name}-ab-service-account" --project="$PROJECT_ID" \
    > "$DATA_DIR/credentials/catscan-service-account.json" 2>/dev/null || true

if [ -s "$DATA_DIR/credentials/catscan-service-account.json" ]; then
    echo "    ✓ AB service account loaded"
else
    echo "    ⚠ AB service account not found in Secret Manager"
    echo "    Upload with: gcloud secrets versions add ${app_name}-ab-service-account --data-file=catscan-service-account.json"
fi

# Fix permissions
chmod 600 "$DATA_DIR/credentials/"*.json 2>/dev/null || true
chown -R catscan:catscan "$DATA_DIR"

# -----------------------------------------------------------------------------
# 3. Setup SSH Deploy Key (for private GitHub repo)
# -----------------------------------------------------------------------------
echo ">>> Setting up GitHub deploy key..."

# Create SSH directory for catscan user
mkdir -p /home/catscan/.ssh
chmod 700 /home/catscan/.ssh

# Fetch deploy key from GCP Secret Manager
gcloud secrets versions access latest --secret=catscan-deploy-key \
    --project="$(curl -s http://metadata.google.internal/computeMetadata/v1/project/project-id -H 'Metadata-Flavor: Google')" \
    > /home/catscan/.ssh/id_ed25519 2>/dev/null

if [ -s /home/catscan/.ssh/id_ed25519 ]; then
    chmod 600 /home/catscan/.ssh/id_ed25519
    chown -R catscan:catscan /home/catscan/.ssh

    # Add GitHub to known hosts
    ssh-keyscan github.com >> /home/catscan/.ssh/known_hosts 2>/dev/null
    chown catscan:catscan /home/catscan/.ssh/known_hosts

    # Convert HTTPS URL to SSH URL for private repo
    GITHUB_SSH_URL=$(echo "$GITHUB_REPO" | sed 's|https://github.com/|git@github.com:|')
    echo "Using SSH URL: $GITHUB_SSH_URL"
else
    echo "WARNING: No deploy key found in Secret Manager, using HTTPS (will fail for private repos)"
    GITHUB_SSH_URL="$GITHUB_REPO"
fi

# -----------------------------------------------------------------------------
# 3b. Clone Repository
# -----------------------------------------------------------------------------
echo ">>> Cloning repository..."

if [ -d "$APP_DIR/.git" ]; then
    cd "$APP_DIR"
    sudo -u catscan git fetch origin
    sudo -u catscan git checkout "$GITHUB_BRANCH"
    sudo -u catscan git pull origin "$GITHUB_BRANCH"
else
    sudo -u catscan git clone -b "$GITHUB_BRANCH" "$GITHUB_SSH_URL" "$APP_DIR"
fi

# -----------------------------------------------------------------------------
# 4. Configure Services to Bind to 127.0.0.1 ONLY
# -----------------------------------------------------------------------------
echo ">>> Configuring secure service binding..."

# Create production docker-compose override
cat > "$APP_DIR/docker-compose.override.yml" << 'EOF'
# SECURITY: Bind services to localhost only
# External access goes through nginx on ports 80/443

version: '3.8'

services:
  api:
    ports:
      - "127.0.0.1:8000:8000"
    environment:
      - CATSCAN_BIND_HOST=0.0.0.0
    restart: unless-stopped

  dashboard:
    ports:
      - "127.0.0.1:3000:3000"
    environment:
      - HOSTNAME=0.0.0.0
    restart: unless-stopped
EOF

chown catscan:catscan "$APP_DIR/docker-compose.override.yml"

# -----------------------------------------------------------------------------
# 5. Configure Nginx as Reverse Proxy
# -----------------------------------------------------------------------------
echo ">>> Configuring nginx..."

cat > /etc/nginx/sites-available/catscan << 'NGINXEOF'
# Cat-Scan Nginx Configuration
# SECURITY: OAuth2 Proxy handles authentication before any request reaches the app

server {
    listen 80;
    server_name DOMAIN_PLACEHOLDER;

    # OAuth2 Proxy endpoints (handles Google login flow)
    location /oauth2/ {
        proxy_pass http://127.0.0.1:4180;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Auth-Request-Redirect $request_uri;
    }

    # OAuth2 Proxy auth check (internal)
    location = /oauth2/auth {
        proxy_pass http://127.0.0.1:4180;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Content-Length "";
        proxy_pass_request_body off;
    }

    # Health check (no auth required - for load balancers/monitoring)
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
    }

    # API routes - require Google authentication
    location /api/ {
        auth_request /oauth2/auth;
        error_page 401 = /oauth2/sign_in;

        # Pass authenticated user info to backend
        auth_request_set $user $upstream_http_x_auth_request_user;
        auth_request_set $email $upstream_http_x_auth_request_email;
        proxy_set_header X-User $user;
        proxy_set_header X-Email $email;

        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Cookie $http_cookie;
        proxy_pass_header Set-Cookie;

        # Timeouts for long operations
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Dashboard - require Google authentication
    location / {
        auth_request /oauth2/auth;
        error_page 401 = /oauth2/sign_in;

        # Pass authenticated user info to frontend
        auth_request_set $user $upstream_http_x_auth_request_user;
        auth_request_set $email $upstream_http_x_auth_request_email;
        proxy_set_header X-User $user;
        proxy_set_header X-Email $email;

        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
NGINXEOF

# Replace domain placeholder (avoiding variable expansion issues)
sed -i "s/DOMAIN_PLACEHOLDER/$DOMAIN_NAME/g" /etc/nginx/sites-available/catscan

# Enable site
ln -sf /etc/nginx/sites-available/catscan /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Start OAuth2 Proxy (must be running before nginx uses auth_request)
echo ">>> Starting OAuth2 Proxy..."
systemctl start oauth2-proxy
sleep 2  # Wait for OAuth2 Proxy to be ready

# Test and reload nginx
nginx -t && systemctl reload nginx

# -----------------------------------------------------------------------------
# 6. SSL Certificate (if domain configured)
# -----------------------------------------------------------------------------
if [ -n "$DOMAIN_NAME" ] && [ "$ENABLE_HTTPS" = "true" ]; then
    echo ">>> Setting up SSL certificate..."

    # Wait for DNS propagation (if just created)
    sleep 10

    # Get certificate (non-interactive)
    certbot --nginx -d "$DOMAIN_NAME" --non-interactive --agree-tos \
        --email "admin@$DOMAIN_NAME" --redirect || {
        echo "WARNING: SSL setup failed - will retry later"
    }

    # Enable auto-renewal
    systemctl enable certbot.timer
    systemctl start certbot.timer
fi

# -----------------------------------------------------------------------------
# 7. Fail2Ban Configuration
# -----------------------------------------------------------------------------
echo ">>> Configuring fail2ban..."

cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
EOF

systemctl enable fail2ban
systemctl restart fail2ban

# -----------------------------------------------------------------------------
# 8. Backup Script
# -----------------------------------------------------------------------------
echo ">>> Setting up backup script..."

cat > /usr/local/bin/catscan-backup << 'BACKUPEOF'
#!/bin/bash
# Daily backup of SQLite database to GCS

set -euo pipefail

DATA_DIR="/home/catscan/.catscan"
BACKUP_FILE="/tmp/catscan-backup-$(date +%Y%m%d-%H%M%S).db"
GCS_PATH="gs://${gcs_bucket}/backups/$(date +%Y/%m)/catscan-$(date +%Y%m%d).db"

# Create backup using SQLite's backup command (safe for concurrent access)
sqlite3 "$DATA_DIR/catscan.db" ".backup '$BACKUP_FILE'"

# Upload to GCS
gsutil cp "$BACKUP_FILE" "$GCS_PATH"

# Cleanup local backup
rm -f "$BACKUP_FILE"

echo "Backup completed: $GCS_PATH"
BACKUPEOF

chmod +x /usr/local/bin/catscan-backup

# Add daily cron job
echo "0 3 * * * root /usr/local/bin/catscan-backup >> /var/log/catscan-backup.log 2>&1" > /etc/cron.d/catscan-backup

# -----------------------------------------------------------------------------
# 8b. Maintenance Cron Jobs (CRITICAL - prevents disk full)
# -----------------------------------------------------------------------------
echo ">>> Setting up maintenance cron jobs..."

# Docker cleanup - runs daily at 4am UTC
# Removes unused images, containers, networks older than 24h
# SAFE: Never removes running containers or volumes
cat > /etc/cron.d/docker-cleanup << 'EOF'
# Docker Cleanup - runs daily at 4am UTC
0 4 * * * root docker system prune -af --filter "until=24h" > /var/log/docker-cleanup.log 2>&1
EOF
chmod 644 /etc/cron.d/docker-cleanup

# Database cleanup - runs weekly on Sunday at 2am UTC
# Deletes data older than 90 days (configurable via CATSCAN_RETENTION_DAYS)
cat > /etc/cron.d/catscan-db-cleanup << 'EOF'
# Database cleanup - runs weekly on Sunday at 2am UTC
0 2 * * 0 root docker exec catscan-api python scripts/cleanup_old_data.py >> /var/log/catscan-db-cleanup.log 2>&1
EOF
chmod 644 /etc/cron.d/catscan-db-cleanup

# Home page precompute - systemd timer runs daily at 3am UTC
# Refreshes precomputed tables for fast dashboard loading
cat > /etc/systemd/system/catscan-home-refresh.service << 'EOF'
[Unit]
Description=Cat-Scan Home Page Data Refresh
After=docker.service

[Service]
Type=oneshot
ExecStart=/usr/bin/docker exec catscan-api python -c "from services.home_precompute import refresh_all_home_tables; refresh_all_home_tables()"
EOF

cat > /etc/systemd/system/catscan-home-refresh.timer << 'EOF'
[Unit]
Description=Daily refresh of Cat-Scan home page tables

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable catscan-home-refresh.timer

echo "Maintenance jobs configured:"
echo "  - docker-cleanup: daily 4am UTC"
echo "  - catscan-db-cleanup: weekly Sunday 2am UTC"
echo "  - catscan-home-refresh: daily 3am UTC"

# -----------------------------------------------------------------------------
# 9. Systemd Service
# -----------------------------------------------------------------------------
echo ">>> Creating systemd service..."

cat > /etc/systemd/system/catscan.service << SERVICEEOF
[Unit]
Description=Cat-Scan Application
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=catscan
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker-compose -f docker-compose.gcp.yml up
ExecStop=/usr/bin/docker-compose -f docker-compose.gcp.yml down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICEEOF

systemctl daemon-reload
systemctl enable catscan

# -----------------------------------------------------------------------------
# 10. Build and Start Application
# -----------------------------------------------------------------------------
echo ">>> Building application..."

cd "$APP_DIR"

# Build Docker images
sudo -u catscan docker-compose -f docker-compose.gcp.yml build

# Start services
systemctl start catscan

# -----------------------------------------------------------------------------
# 11. Final Security Checks
# -----------------------------------------------------------------------------
echo ">>> Running security checks..."

# Verify services are NOT listening on public interfaces
echo "Checking service binding..."
sleep 30  # Wait for services to start

if netstat -tlnp | grep -E '0\.0\.0\.0:(3000|8000)' > /dev/null; then
    echo "WARNING: Services are bound to 0.0.0.0 - this is insecure!"
else
    echo "OK: Services bound to 127.0.0.1 only"
fi

# Verify nginx is the only public listener
echo "Public listeners (should only be nginx on 80/443):"
netstat -tlnp | grep '0.0.0.0' || echo "No public listeners"

# Verify OAuth2 Proxy is running
echo "OAuth2 Proxy status:"
systemctl status oauth2-proxy --no-pager || echo "WARNING: OAuth2 Proxy not running"

# -----------------------------------------------------------------------------
# Complete
# -----------------------------------------------------------------------------
echo ""
echo "=== Cat-Scan Setup Complete: $(date) ==="
echo ""
echo "AUTHENTICATION: Google OAuth via OAuth2 Proxy"
echo "All users must sign in with their Google account to access the app."
echo ""
if [ "$ENABLE_HTTPS" = "true" ] && [ -n "$DOMAIN_NAME" ]; then
    echo "Access: https://$DOMAIN_NAME"
    echo "        (You will be redirected to Google for authentication)"
else
    echo "Access: http://$DOMAIN_NAME"
fi
echo ""
echo "Next steps:"
echo "1. Visit the URL above and sign in with your Google account"
echo "2. Upload Google Authorized Buyers credentials via the Settings page"
echo "3. Configure Gmail OAuth tokens for CSV import"
echo "4. Run initial creative sync from the dashboard"
echo ""

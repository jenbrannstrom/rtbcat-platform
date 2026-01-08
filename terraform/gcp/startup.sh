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

# Variables from Terraform
APP_NAME="${app_name}"
ENVIRONMENT="${environment}"
DOMAIN_NAME="${domain_name}"
ENABLE_HTTPS="${enable_https}"
GITHUB_REPO="${github_repo}"
GITHUB_BRANCH="${github_branch}"
GCS_BUCKET="${gcs_bucket}"

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
# 3. Clone Repository
# -----------------------------------------------------------------------------
echo ">>> Cloning repository..."

if [ -d "$APP_DIR/.git" ]; then
    cd "$APP_DIR"
    sudo -u catscan git fetch origin
    sudo -u catscan git checkout "$GITHUB_BRANCH"
    sudo -u catscan git pull origin "$GITHUB_BRANCH"
else
    sudo -u catscan git clone -b "$GITHUB_BRANCH" "$GITHUB_REPO" "$APP_DIR"
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

cat > /etc/nginx/sites-available/catscan << EOF
# Cat-Scan Nginx Configuration
# SECURITY: This is the ONLY external entry point

server {
    listen 80;
    server_name ${DOMAIN_NAME:-_};

    # API routes
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Cookie \$http_cookie;
        proxy_pass_header Set-Cookie;

        # Timeouts for long operations
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Health check (direct to API)
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }

    # Dashboard (Next.js)
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/catscan /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

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

cat > /usr/local/bin/catscan-backup << EOF
#!/bin/bash
# Daily backup of SQLite database to GCS

set -euo pipefail

BACKUP_FILE="/tmp/catscan-backup-\$(date +%Y%m%d-%H%M%S).db"
GCS_PATH="gs://${GCS_BUCKET}/backups/\$(date +%Y/%m)/catscan-\$(date +%Y%m%d).db"

# Create backup using SQLite's backup command (safe for concurrent access)
sqlite3 "$DATA_DIR/catscan.db" ".backup '\$BACKUP_FILE'"

# Upload to GCS
gsutil cp "\$BACKUP_FILE" "\$GCS_PATH"

# Cleanup local backup
rm -f "\$BACKUP_FILE"

echo "Backup completed: \$GCS_PATH"
EOF

chmod +x /usr/local/bin/catscan-backup

# Add daily cron job
echo "0 3 * * * root /usr/local/bin/catscan-backup >> /var/log/catscan-backup.log 2>&1" > /etc/cron.d/catscan-backup

# -----------------------------------------------------------------------------
# 9. Systemd Service
# -----------------------------------------------------------------------------
echo ">>> Creating systemd service..."

cat > /etc/systemd/system/catscan.service << EOF
[Unit]
Description=Cat-Scan Application
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=catscan
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker-compose -f docker-compose.yml -f docker-compose.override.yml up
ExecStop=/usr/bin/docker-compose -f docker-compose.yml -f docker-compose.override.yml down
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable catscan

# -----------------------------------------------------------------------------
# 10. Build and Start Application
# -----------------------------------------------------------------------------
echo ">>> Building application..."

cd "$APP_DIR"

# Build Docker images
sudo -u catscan docker-compose build

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

# -----------------------------------------------------------------------------
# Complete
# -----------------------------------------------------------------------------
echo ""
echo "=== Cat-Scan Setup Complete: $(date) ==="
echo ""
echo "Access: http://${DOMAIN_NAME:-$(curl -s ifconfig.me)}"
if [ "$ENABLE_HTTPS" = "true" ] && [ -n "$DOMAIN_NAME" ]; then
    echo "HTTPS:  https://$DOMAIN_NAME"
fi
echo ""
echo "Next steps:"
echo "1. Upload Google credentials to $DATA_DIR/credentials/google-credentials.json"
echo "2. Configure Gmail OAuth tokens"
echo "3. Run initial creative sync from the dashboard"
echo ""

#!/bin/bash
# =============================================================================
# Cat-Scan Hardened VM Setup Script
# =============================================================================
# This script sets up a secure GCP VM for running Cat-Scan.
# Run as root or with sudo on a fresh Ubuntu 22.04/24.04 VM.
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/YOUR_ORG/rtbcat-platform/main/scripts/setup-hardened-vm.sh | sudo bash
#
# Or download and run:
#   chmod +x setup-hardened-vm.sh
#   sudo ./setup-hardened-vm.sh
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# =============================================================================
# Configuration
# =============================================================================
DEPLOY_USER="jen"
APP_DIR="/home/${DEPLOY_USER}/rtbcat-platform"
DATA_DIR="/home/${DEPLOY_USER}/.catscan"

# =============================================================================
# Pre-flight checks
# =============================================================================
log_info "Starting hardened VM setup..."

if [[ $EUID -ne 0 ]]; then
   log_error "This script must be run as root (use sudo)"
   exit 1
fi

# =============================================================================
# 1. System Updates
# =============================================================================
log_info "Updating system packages..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y

# =============================================================================
# 2. Install Required Packages
# =============================================================================
log_info "Installing required packages..."
apt-get install -y \
    git \
    curl \
    wget \
    ufw \
    fail2ban \
    nginx \
    certbot \
    python3-certbot-nginx \
    python3-pip \
    python3-venv \
    sqlite3 \
    ffmpeg \
    unattended-upgrades \
    apt-listchanges

# Install Node.js 20.x
if ! command -v node &> /dev/null; then
    log_info "Installing Node.js 20.x..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# =============================================================================
# 3. Configure Automatic Security Updates
# =============================================================================
log_info "Configuring automatic security updates..."
cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF

# =============================================================================
# 4. SSH Hardening
# =============================================================================
log_info "Hardening SSH configuration..."

# Backup original config
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Apply hardened SSH config
cat > /etc/ssh/sshd_config.d/hardened.conf << 'EOF'
# Disable password authentication (key-only)
PasswordAuthentication no
ChallengeResponseAuthentication no
UsePAM yes

# Disable root login
PermitRootLogin no

# Limit authentication attempts
MaxAuthTries 3
MaxSessions 3

# Idle timeout (10 minutes)
ClientAliveInterval 300
ClientAliveCountMax 2

# Disable X11 forwarding
X11Forwarding no

# Disable TCP forwarding (unless needed)
AllowTcpForwarding no

# Use strong ciphers only
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org

# Log more details
LogLevel VERBOSE
EOF

# Restart SSH
systemctl restart sshd

# =============================================================================
# 5. Firewall Configuration (UFW)
# =============================================================================
log_info "Configuring firewall..."

# Reset UFW to defaults
ufw --force reset

# Default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (with rate limiting)
ufw limit 22/tcp comment 'SSH with rate limiting'

# Allow HTTP and HTTPS
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

# Enable firewall
ufw --force enable

log_info "Firewall configured. Open ports: 22 (rate-limited), 80, 443"

# =============================================================================
# 6. Fail2Ban Configuration
# =============================================================================
log_info "Configuring fail2ban..."

cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 1h
findtime = 10m
maxretry = 5
backend = systemd

[sshd]
enabled = true
port = ssh
filter = sshd
maxretry = 3
bantime = 24h

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 3

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
EOF

systemctl enable fail2ban
systemctl restart fail2ban

# =============================================================================
# 7. Create Application User (if not exists)
# =============================================================================
if ! id "$DEPLOY_USER" &>/dev/null; then
    log_info "Creating application user: $DEPLOY_USER"
    useradd -m -s /bin/bash "$DEPLOY_USER"
fi

# =============================================================================
# 8. Nginx Configuration with Security Headers
# =============================================================================
log_info "Configuring nginx with security headers..."

cat > /etc/nginx/sites-available/catscan << 'EOF'
# Rate limiting zone
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
limit_req_zone $binary_remote_addr zone=general_limit:10m rate=30r/s;

server {
    listen 80;
    server_name _;

    # Redirect all HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name _;

    # SSL configuration (will be updated by certbot)
    ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;

    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self' data:; connect-src 'self';" always;

    # Hide nginx version
    server_tokens off;

    # Logging
    access_log /var/log/nginx/catscan_access.log;
    error_log /var/log/nginx/catscan_error.log;

    # Dashboard (Next.js)
    location / {
        limit_req zone=general_limit burst=50 nodelay;

        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 60s;
        proxy_connect_timeout 60s;
    }

    # API endpoints (with stricter rate limiting)
    location /api/ {
        limit_req zone=api_limit burst=20 nodelay;

        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 60s;

        # Larger body size for file uploads
        client_max_body_size 50M;
    }

    # Health check endpoint (no rate limiting)
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }

    # Block common attack paths
    location ~ /\. {
        deny all;
    }

    location ~* \.(git|env|sql|bak|backup|log)$ {
        deny all;
    }
}
EOF

# Enable the site
ln -sf /etc/nginx/sites-available/catscan /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test and reload nginx
nginx -t
systemctl reload nginx

# =============================================================================
# 9. Systemd Services
# =============================================================================
log_info "Creating systemd services..."

# API Service
cat > /etc/systemd/system/catscan-api.service << EOF
[Unit]
Description=Cat-Scan API
After=network.target

[Service]
Type=simple
User=${DEPLOY_USER}
Group=${DEPLOY_USER}
WorkingDirectory=${APP_DIR}
Environment="PATH=${APP_DIR}/venv/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
# SECURITY: Set these environment variables!
# Environment="CATSCAN_API_KEY=your-secure-api-key-here"
# Environment="RTBCAT_ADMIN_EMAIL=admin@example.com"
# Environment="RTBCAT_ADMIN_PASSWORD=secure-password-here"
ExecStart=${APP_DIR}/venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=${DATA_DIR}
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Dashboard Service
cat > /etc/systemd/system/catscan-dashboard.service << EOF
[Unit]
Description=Cat-Scan Dashboard
After=network.target catscan-api.service

[Service]
Type=simple
User=${DEPLOY_USER}
Group=${DEPLOY_USER}
WorkingDirectory=${APP_DIR}/dashboard
Environment="NODE_ENV=production"
Environment="PORT=3000"
Environment="HOSTNAME=127.0.0.1"
ExecStart=/usr/bin/node server.js
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=${APP_DIR}/dashboard/.next
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload

# =============================================================================
# 10. Create data directories with proper permissions
# =============================================================================
log_info "Creating data directories..."

mkdir -p "${DATA_DIR}/credentials"
mkdir -p "${DATA_DIR}/thumbnails"
mkdir -p "${DATA_DIR}/imports"
mkdir -p "${DATA_DIR}/logs"

chown -R ${DEPLOY_USER}:${DEPLOY_USER} "${DATA_DIR}"
chmod 700 "${DATA_DIR}/credentials"
chmod 755 "${DATA_DIR}"

# =============================================================================
# 11. Log rotation
# =============================================================================
log_info "Configuring log rotation..."

cat > /etc/logrotate.d/catscan << EOF
/var/log/nginx/catscan_*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data adm
    sharedscripts
    postrotate
        [ -f /var/run/nginx.pid ] && kill -USR1 \$(cat /var/run/nginx.pid)
    endscript
}

${DATA_DIR}/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 ${DEPLOY_USER} ${DEPLOY_USER}
}
EOF

# =============================================================================
# Summary
# =============================================================================
log_info "=============================================="
log_info "Hardened VM setup complete!"
log_info "=============================================="
echo ""
log_warn "IMPORTANT: Complete these manual steps:"
echo ""
echo "1. Clone the repository:"
echo "   sudo -u ${DEPLOY_USER} git clone https://github.com/YOUR_ORG/rtbcat-platform.git ${APP_DIR}"
echo ""
echo "2. Set up Python environment:"
echo "   cd ${APP_DIR}"
echo "   sudo -u ${DEPLOY_USER} python3 -m venv venv"
echo "   sudo -u ${DEPLOY_USER} ./venv/bin/pip install -r requirements.txt"
echo ""
echo "3. Build the dashboard:"
echo "   cd ${APP_DIR}/dashboard"
echo "   sudo -u ${DEPLOY_USER} npm ci"
echo "   sudo -u ${DEPLOY_USER} npm run build"
echo ""
echo "4. Set environment variables in /etc/systemd/system/catscan-api.service:"
echo "   - CATSCAN_API_KEY=<generate with: openssl rand -base64 32>"
echo "   - RTBCAT_ADMIN_EMAIL=your-email@example.com"
echo "   - RTBCAT_ADMIN_PASSWORD=<secure-password>"
echo ""
echo "5. Upload your NEW GCP service account key to:"
echo "   ${DATA_DIR}/credentials/"
echo ""
echo "6. Set up SSL with Let's Encrypt:"
echo "   sudo certbot --nginx -d your-domain.com"
echo ""
echo "7. Enable and start services:"
echo "   sudo systemctl enable catscan-api catscan-dashboard"
echo "   sudo systemctl start catscan-api catscan-dashboard"
echo ""
echo "8. Verify everything is running:"
echo "   sudo systemctl status catscan-api catscan-dashboard nginx"
echo ""
log_info "Security measures applied:"
echo "  - SSH: Key-only auth, no root login, rate limited"
echo "  - Firewall: Only ports 22, 80, 443 open"
echo "  - Fail2ban: Blocks repeated failed attempts"
echo "  - Nginx: Rate limiting, security headers, HTTPS only"
echo "  - Auto-updates: Security patches applied automatically"
echo "  - Services: Run as non-root with restricted permissions"

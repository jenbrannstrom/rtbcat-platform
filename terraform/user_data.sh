#!/bin/bash
# Cat-Scan EC2 User Data Script
# Installs Docker and starts the application

set -e

# Log everything
exec > >(tee /var/log/catscan-setup.log) 2>&1
echo "Starting Cat-Scan setup..."
date

# Terraform-provided variables
ENVIRONMENT="${environment}"
S3_BUCKET="${s3_bucket}"
DOMAIN_NAME="${domain_name}"
ENABLE_HTTPS="${enable_https}"

echo "Environment: $ENVIRONMENT"
echo "S3 Bucket: $S3_BUCKET"
echo "Domain: $DOMAIN_NAME"
echo "HTTPS Enabled: $ENABLE_HTTPS"

# Update system
dnf update -y

# Install Docker
dnf install -y docker git

# Start Docker
systemctl start docker
systemctl enable docker

# Install Docker Compose v2
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/download/v2.32.4/docker-compose-linux-x86_64" -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Create app user
useradd -m -s /bin/bash catscan || true
usermod -aG docker catscan

# Create data directory with permissions for container user
mkdir -p /home/catscan/.catscan
mkdir -p /home/catscan/.catscan/credentials
mkdir -p /home/catscan/.catscan/imports
chown -R catscan:catscan /home/catscan/.catscan
chmod -R 777 /home/catscan/.catscan

# Clone repository
cd /home/catscan
if [ ! -d "rtbcat-platform" ]; then
    git clone https://github.com/rtbcat/catscan.git rtbcat-platform
    chown -R catscan:catscan rtbcat-platform
fi

cd rtbcat-platform

# Get public IP
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "Public IP: $PUBLIC_IP"

# Create environment file
cat > .env << ENVEOF
# Cat-Scan Environment Configuration
ENVIRONMENT=$ENVIRONMENT
S3_BUCKET=$S3_BUCKET

# Domain for HTTPS (used by Caddy)
DOMAIN=$DOMAIN_NAME

# Data directory
DATA_DIR=/home/catscan/.catscan

# API Configuration
DATABASE_PATH=/home/catscan/.catscan/catscan.db

# API Key (generate one after deployment)
# CATSCAN_API_KEY=
ENVEOF

if [ "$ENABLE_HTTPS" = "true" ] && [ -n "$DOMAIN_NAME" ]; then
    echo "Setting up HTTPS mode with Caddy..."

    # Use production compose with Caddy
    docker compose -f docker-compose.production.yml up -d --build

    echo "Cat-Scan setup complete (HTTPS mode)!"
    echo "Dashboard: https://$DOMAIN_NAME"
    echo "API: https://$DOMAIN_NAME/api"
    echo ""
    echo "IMPORTANT: Point your DNS A record to $PUBLIC_IP"
    echo "Then set API key: echo 'CATSCAN_API_KEY=xxx' >> .env && docker compose restart"
else
    echo "Setting up HTTP mode (no Caddy)..."

    # Create production override for simple compose
    cat > docker-compose.prod.yml << COMPOSEEOF
version: '3.8'

services:
  creative-api:
    container_name: catscan-api
    restart: always
    volumes:
      - /home/catscan/.catscan:/home/rtbcat/.catscan
      - /home/catscan/.catscan/credentials:/credentials:ro
    environment:
      - GOOGLE_APPLICATION_CREDENTIALS=/credentials/google-credentials.json
      - DATABASE_PATH=/home/rtbcat/.catscan/catscan.db
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  dashboard:
    container_name: catscan-dashboard
    restart: always
    environment:
      - API_HOST=creative-api
      - NEXT_PUBLIC_API_URL=http://$PUBLIC_IP:8000
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
COMPOSEEOF

    # Build and start services
    docker compose -f docker-compose.simple.yml -f docker-compose.prod.yml up -d --build

    echo "Cat-Scan setup complete (HTTP mode)!"
    echo "Dashboard: http://$PUBLIC_IP:3000"
    echo "API: http://$PUBLIC_IP:8000"
fi

# Setup daily Gmail import cron
# Email arrives ~7am (timezone unclear), so run at 8 AM UTC to be 1 hour after
cat > /etc/cron.d/gmail-import << 'CRONEOF'
# Cat-Scan Gmail import - runs daily at 8 AM UTC (1 hour after email arrives)
0 8 * * * root docker exec catscan-api python scripts/gmail_import.py >> /var/log/gmail-import.log 2>&1
CRONEOF
chmod 644 /etc/cron.d/gmail-import

echo "Cron job installed for daily Gmail import at 8 AM UTC"
date

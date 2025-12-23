#!/bin/bash
# Cat-Scan EC2 User Data Script
# Installs Docker and starts the application

set -e

# Log everything
exec > >(tee /var/log/catscan-setup.log) 2>&1
echo "Starting Cat-Scan setup..."
date

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

# Create data directory
mkdir -p /home/catscan/.catscan
mkdir -p /home/catscan/.catscan/credentials
mkdir -p /home/catscan/.catscan/imports
chown -R catscan:catscan /home/catscan/.catscan

# Clone repository
cd /home/catscan
if [ ! -d "rtbcat-platform" ]; then
    git clone https://github.com/rtbcat/catscan.git rtbcat-platform
    chown -R catscan:catscan rtbcat-platform
fi

cd rtbcat-platform

# Create environment file with Terraform-provided values
cat > .env << 'ENVEOF'
# Cat-Scan Environment Configuration
ENVIRONMENT=${environment}
S3_BUCKET=${s3_bucket}

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Dashboard Configuration
DASHBOARD_PORT=3000

# Data paths
CATSCAN_DATA_DIR=/home/catscan/.catscan
DATABASE_PATH=/home/catscan/.catscan/catscan.db
ENVEOF

# Get public IP for API_HOST
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "Public IP: $PUBLIC_IP"

# Create production docker-compose override
cat > docker-compose.prod.yml << COMPOSEEOF
version: '3.8'

services:
  creative-api:
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

# Build and start services (API + Dashboard only, skip testing services)
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d creative-api dashboard

echo "Cat-Scan setup complete!"
echo "Dashboard: http://$PUBLIC_IP:3000"
echo "API: http://$PUBLIC_IP:8000"
date

#!/bin/bash
#
# Cat-Scan Database Backup Script
#
# Usage:
#   ./backup.sh              # Backup to local directory
#   ./backup.sh --gcs        # Backup to Google Cloud Storage
#   ./backup.sh --s3         # Backup to AWS S3
#
# Install on production VM:
#   sudo cp scripts/backup.sh /usr/local/bin/catscan-backup
#   sudo chmod +x /usr/local/bin/catscan-backup
#
# Schedule daily backup (add to crontab):
#   0 3 * * * /usr/local/bin/catscan-backup --gcs >> /var/log/catscan-backup.log 2>&1
#

set -e

# Configuration
CATSCAN_DIR="${CATSCAN_DIR:-$HOME/.catscan}"
DB_PATH="$CATSCAN_DIR/catscan.db"
BACKUP_DIR="$CATSCAN_DIR/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="catscan_backup_$DATE"

# Cloud storage settings (override via environment variables)
GCS_BUCKET="${CATSCAN_GCS_BUCKET:-catscan-backups}"
S3_BUCKET="${CATSCAN_S3_BUCKET:-rtbcat-backups}"
S3_REGION="${CATSCAN_S3_REGION:-eu-central-1}"

# Retention settings
KEEP_LOCAL_DAYS=7
KEEP_CLOUD_DAYS=30

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    log_error "Database not found at $DB_PATH"
    exit 1
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Get database size
DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
log_info "Database size: $DB_SIZE"

# Create backup using SQLite's backup command (safe for live databases)
log_info "Creating backup..."
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME.db"
sqlite3 "$DB_PATH" ".backup '$BACKUP_PATH'"

# Compress the backup
log_info "Compressing backup..."
gzip "$BACKUP_PATH"
BACKUP_PATH="$BACKUP_PATH.gz"
COMPRESSED_SIZE=$(du -h "$BACKUP_PATH" | cut -f1)
log_info "Compressed size: $COMPRESSED_SIZE"

# Upload to cloud storage if requested
case "${1:-}" in
    --gcs)
        if command -v gsutil &> /dev/null; then
            log_info "Uploading to GCS: gs://$GCS_BUCKET/"
            gsutil cp "$BACKUP_PATH" "gs://$GCS_BUCKET/daily/$BACKUP_NAME.db.gz"
            log_info "GCS upload complete"

            # Clean up old GCS backups
            log_info "Cleaning up old GCS backups (keeping $KEEP_CLOUD_DAYS days)..."
            CUTOFF_DATE=$(date -d "$KEEP_CLOUD_DAYS days ago" +%Y%m%d)
            gsutil ls "gs://$GCS_BUCKET/daily/" 2>/dev/null | while read -r file; do
                # Extract date from filename
                FILE_DATE=$(echo "$file" | grep -oP '\d{8}' | head -1)
                if [ -n "$FILE_DATE" ] && [ "$FILE_DATE" -lt "$CUTOFF_DATE" ]; then
                    log_info "Deleting old backup: $file"
                    gsutil rm "$file"
                fi
            done
        else
            log_error "gsutil not found. Install Google Cloud SDK."
            exit 1
        fi
        ;;
    --s3)
        if command -v aws &> /dev/null; then
            log_info "Uploading to S3: s3://$S3_BUCKET/"
            aws s3 cp "$BACKUP_PATH" "s3://$S3_BUCKET/daily/$BACKUP_NAME.db.gz" --region "$S3_REGION"
            log_info "S3 upload complete"

            # Clean up old S3 backups (using lifecycle policy is preferred)
            log_info "Note: Configure S3 lifecycle policy for automatic cleanup"
        else
            log_error "aws CLI not found. Install AWS CLI."
            exit 1
        fi
        ;;
    *)
        log_info "Local backup only (use --gcs or --s3 for cloud backup)"
        ;;
esac

# Clean up old local backups
log_info "Cleaning up old local backups (keeping $KEEP_LOCAL_DAYS days)..."
find "$BACKUP_DIR" -name "catscan_backup_*.db.gz" -mtime +$KEEP_LOCAL_DAYS -delete 2>/dev/null || true

# List current backups
log_info "Current backups:"
ls -lh "$BACKUP_DIR"/*.gz 2>/dev/null | tail -5 || log_warn "No local backups found"

# Summary
echo ""
log_info "═══════════════════════════════════════════════════"
log_info "Backup complete!"
log_info "  Database: $DB_PATH ($DB_SIZE)"
log_info "  Backup: $BACKUP_PATH ($COMPRESSED_SIZE)"
log_info "═══════════════════════════════════════════════════"

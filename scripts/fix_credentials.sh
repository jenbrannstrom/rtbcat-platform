#!/bin/bash
#
# Cat-Scan Credentials Consolidation Script
#
# This script finds credentials scattered across different locations
# and consolidates them to the correct place.
#
# Usage:
#   ./fix_credentials.sh              # Check and report
#   ./fix_credentials.sh --fix        # Actually fix/copy credentials
#   ./fix_credentials.sh --production # Fix on production VM (run as sudo)
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[MISSING]${NC} $1"; }
log_found() { echo -e "${BLUE}[FOUND]${NC} $1"; }

# Credential files we're looking for
GMAIL_OAUTH="gmail-oauth-client.json"
GMAIL_TOKEN="gmail-token.json"
SERVICE_ACCOUNT="catscan-service-account.json"
GOOGLE_CREDS="google-credentials.json"

# All possible locations
LOCATIONS=(
    "$HOME/.catscan/credentials"
    "/home/jen/.catscan/credentials"
    "/home/catscan/.catscan/credentials"
    "/home/rtbcat/.catscan/credentials"
    "/opt/catscan/credentials"
    "$HOME/Downloads"
    "$HOME/Desktop"
)

echo ""
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║           Cat-Scan Credentials Consolidation Tool                ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

# Determine target directory
if [[ "$1" == "--production" ]]; then
    TARGET_DIR="/home/catscan/.catscan/credentials"
    echo "Mode: Production (target: $TARGET_DIR)"
else
    TARGET_DIR="$HOME/.catscan/credentials"
    echo "Mode: Local development (target: $TARGET_DIR)"
fi
echo ""

# Create target directory if needed
mkdir -p "$TARGET_DIR" 2>/dev/null || true

# Function to find a credential file
find_credential() {
    local filename="$1"
    local found_path=""

    for loc in "${LOCATIONS[@]}"; do
        if [[ -f "$loc/$filename" ]]; then
            found_path="$loc/$filename"
            break
        fi
    done

    # Also search common download locations
    if [[ -z "$found_path" ]]; then
        # Search for recently downloaded files
        found_path=$(find "$HOME" -name "$filename" -type f 2>/dev/null | head -1)
    fi

    echo "$found_path"
}

# Check each credential file
echo "═══════════════════════════════════════════════════════════════════"
echo "Scanning for credentials..."
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Gmail OAuth Client
echo "1. Gmail OAuth Client ($GMAIL_OAUTH)"
GMAIL_OAUTH_PATH=$(find_credential "$GMAIL_OAUTH")
if [[ -n "$GMAIL_OAUTH_PATH" ]]; then
    log_found "  $GMAIL_OAUTH_PATH"
    if [[ "$GMAIL_OAUTH_PATH" != "$TARGET_DIR/$GMAIL_OAUTH" ]]; then
        log_warn "  Not in target location"
        NEEDS_GMAIL_OAUTH=1
    else
        log_info "  Already in correct location"
    fi
else
    log_error "  Not found anywhere"
    echo "       Download from: https://console.cloud.google.com/apis/credentials"
    echo "       Save as: $TARGET_DIR/$GMAIL_OAUTH"
fi
echo ""

# Gmail Token
echo "2. Gmail Token ($GMAIL_TOKEN)"
GMAIL_TOKEN_PATH=$(find_credential "$GMAIL_TOKEN")
if [[ -n "$GMAIL_TOKEN_PATH" ]]; then
    log_found "  $GMAIL_TOKEN_PATH"
    if [[ "$GMAIL_TOKEN_PATH" != "$TARGET_DIR/$GMAIL_TOKEN" ]]; then
        log_warn "  Not in target location"
        NEEDS_GMAIL_TOKEN=1
    else
        log_info "  Already in correct location"
    fi
else
    log_warn "  Not found (will be created when you authorize Gmail)"
fi
echo ""

# Service Account
echo "3. Service Account ($SERVICE_ACCOUNT or $GOOGLE_CREDS)"
SA_PATH=$(find_credential "$SERVICE_ACCOUNT")
if [[ -z "$SA_PATH" ]]; then
    SA_PATH=$(find_credential "$GOOGLE_CREDS")
fi
if [[ -n "$SA_PATH" ]]; then
    log_found "  $SA_PATH"
    if [[ "$SA_PATH" != "$TARGET_DIR/$SERVICE_ACCOUNT" && "$SA_PATH" != "$TARGET_DIR/$GOOGLE_CREDS" ]]; then
        log_warn "  Not in target location"
        NEEDS_SERVICE_ACCOUNT=1
    else
        log_info "  Already in correct location"
    fi
else
    log_error "  Not found anywhere"
    echo "       Create from: https://console.cloud.google.com/iam-admin/serviceaccounts"
fi
echo ""

# Summary
echo "═══════════════════════════════════════════════════════════════════"
echo "Summary"
echo "═══════════════════════════════════════════════════════════════════"
echo ""
echo "Target directory: $TARGET_DIR"
echo ""

# Check what's in target
if [[ -d "$TARGET_DIR" ]]; then
    echo "Current contents of target:"
    ls -la "$TARGET_DIR" 2>/dev/null || echo "  (empty or inaccessible)"
else
    echo "Target directory does not exist"
fi
echo ""

# Fix if requested
if [[ "$1" == "--fix" || "$1" == "--production" ]]; then
    echo "═══════════════════════════════════════════════════════════════════"
    echo "Fixing credentials..."
    echo "═══════════════════════════════════════════════════════════════════"
    echo ""

    mkdir -p "$TARGET_DIR"

    if [[ -n "$GMAIL_OAUTH_PATH" && "$NEEDS_GMAIL_OAUTH" == "1" ]]; then
        echo "Copying Gmail OAuth client..."
        cp "$GMAIL_OAUTH_PATH" "$TARGET_DIR/$GMAIL_OAUTH"
        log_info "Copied to $TARGET_DIR/$GMAIL_OAUTH"
    fi

    if [[ -n "$GMAIL_TOKEN_PATH" && "$NEEDS_GMAIL_TOKEN" == "1" ]]; then
        echo "Copying Gmail token..."
        cp "$GMAIL_TOKEN_PATH" "$TARGET_DIR/$GMAIL_TOKEN"
        log_info "Copied to $TARGET_DIR/$GMAIL_TOKEN"
    fi

    if [[ -n "$SA_PATH" && "$NEEDS_SERVICE_ACCOUNT" == "1" ]]; then
        echo "Copying service account..."
        cp "$SA_PATH" "$TARGET_DIR/$(basename $SA_PATH)"
        log_info "Copied to $TARGET_DIR/$(basename $SA_PATH)"
    fi

    # Fix ownership on production
    if [[ "$1" == "--production" ]]; then
        echo ""
        echo "Setting ownership to catscan user..."
        chown -R catscan:catscan /home/catscan/.catscan
        log_info "Ownership fixed"
    fi

    echo ""
    echo "Final contents:"
    ls -la "$TARGET_DIR"
else
    echo "═══════════════════════════════════════════════════════════════════"
    echo "To fix, run:"
    echo "  ./fix_credentials.sh --fix           # Local development"
    echo "  sudo ./fix_credentials.sh --production  # Production VM"
    echo "═══════════════════════════════════════════════════════════════════"
fi

echo ""
echo "Next steps:"
echo "  1. If Gmail OAuth client missing: Download from GCP Console"
echo "  2. Run: python scripts/gmail_auth.py"
echo "  3. Run: python scripts/gmail_import.py"
echo ""

#!/bin/bash

set -e

echo "======================================"
echo "  Cat-Scan Setup Script"
echo "======================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check function
check_command() {
    local cmd=$1
    local name=$2
    local install_hint=$3

    if command -v $cmd &> /dev/null; then
        version=$($cmd --version 2>&1 | head -1)
        echo -e "${GREEN}✓${NC} $name: $version"
        return 0
    else
        echo -e "${RED}✗${NC} $name: Not found"
        echo -e "  ${YELLOW}Install with:${NC} $install_hint"
        return 1
    fi
}

echo "Checking requirements..."
echo ""

MISSING=0

# Check Python
if ! check_command python3 "Python" "sudo apt install python3.11 python3.11-venv"; then
    MISSING=1
fi

# Check Node.js
if ! check_command node "Node.js" "curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install nodejs"; then
    MISSING=1
fi

# Check npm
if ! check_command npm "npm" "(included with Node.js)"; then
    MISSING=1
fi

# Check ffmpeg (optional)
if ! check_command ffmpeg "ffmpeg" "sudo apt install ffmpeg"; then
    echo -e "  ${YELLOW}(Optional - needed for video thumbnails)${NC}"
fi

# Check SQLite
if ! check_command sqlite3 "SQLite" "sudo apt install sqlite3"; then
    MISSING=1
fi

echo ""

if [ $MISSING -eq 1 ]; then
    echo -e "${RED}Some required tools are missing.${NC}"
    echo "Please install them and run this script again."
    exit 1
fi

echo -e "${GREEN}All requirements met!${NC}"
echo ""

# Setup Python environment
echo "Setting up Python environment..."
cd "$SCRIPT_DIR/creative-intelligence"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Created virtual environment"
fi

./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q
echo -e "${GREEN}✓${NC} Python dependencies installed"

# Initialize database
./venv/bin/python -c "from storage.sqlite_store import SQLiteStore; SQLiteStore()" 2>/dev/null || true
echo -e "${GREEN}✓${NC} Database initialized"

cd "$SCRIPT_DIR"

# Setup Node.js environment
echo ""
echo "Setting up Node.js environment..."
cd "$SCRIPT_DIR/dashboard"

npm install --silent 2>/dev/null || npm install
echo -e "${GREEN}✓${NC} Node.js dependencies installed"

cd "$SCRIPT_DIR"

# Create data directories
mkdir -p ~/.catscan/thumbnails
mkdir -p ~/.catscan/credentials
echo -e "${GREEN}✓${NC} Data directories created"

echo ""
echo "======================================"
echo -e "${GREEN}  Setup Complete!${NC}"
echo "======================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Start services:  ./run.sh"
echo "  2. Open browser:    http://localhost:3000"
echo "  3. Configure:       Go to /setup to add credentials"
echo ""

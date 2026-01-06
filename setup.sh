#!/bin/bash
# Cat-Scan Setup Script
# Creates Python venv, installs dependencies, initializes database

set -e

echo "=== Cat-Scan Setup ==="

# Check requirements
command -v python3 >/dev/null 2>&1 || { echo "Python 3 required"; exit 1; }
command -v node >/dev/null 2>&1 || { echo "Node.js required"; exit 1; }

# Python setup
echo "Setting up Python environment..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt

# Node setup
echo "Setting up Node.js dependencies..."
cd dashboard && npm install && cd ..

# Database init
echo "Initializing database..."
./venv/bin/python -c "from storage.sqlite_store import SQLiteStore; SQLiteStore()"
sqlite3 ~/.catscan/catscan.db "PRAGMA journal_mode=WAL;" >/dev/null 2>&1 || true

echo ""
echo "=== Setup Complete ==="
echo "Run ./run.sh to start the application"

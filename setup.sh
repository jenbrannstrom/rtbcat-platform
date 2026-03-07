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
PYTHON_REQUIREMENTS="${CATSCAN_PYTHON_REQUIREMENTS:-requirements.txt}"
if [[ ! -f "${PYTHON_REQUIREMENTS}" ]]; then
  echo "Missing Python requirements file: ${PYTHON_REQUIREMENTS}"
  exit 1
fi
./venv/bin/pip install -r "${PYTHON_REQUIREMENTS}"
if [[ "${CATSCAN_INSTALL_AI_EXTRAS:-false}" == "true" && "${PYTHON_REQUIREMENTS}" != "requirements-dev.txt" ]]; then
  ./venv/bin/pip install -r requirements-ai.txt
fi

# Node setup
echo "Setting up Node.js dependencies..."
cd dashboard && npm install && cd ..

# Database init (Postgres)
echo "Initializing database..."
if [[ -z "${POSTGRES_DSN}" && -z "${DATABASE_URL}" ]]; then
  echo "POSTGRES_DSN or DATABASE_URL must be set for Postgres."
  echo "Example: export POSTGRES_DSN=postgresql://user:pass@localhost:5432/rtbcat"
  exit 1
fi
if [[ -z "${POSTGRES_SERVING_DSN}" ]]; then
  echo "POSTGRES_SERVING_DSN must be set for serving queries."
  echo "Example: export POSTGRES_SERVING_DSN=postgresql://user:pass@localhost:5432/rtbcat"
  exit 1
fi
./venv/bin/python scripts/postgres_migrate.py

echo ""
echo "=== Setup Complete ==="
echo "Python bundle installed: ${PYTHON_REQUIREMENTS}"
if [[ "${CATSCAN_INSTALL_AI_EXTRAS:-false}" == "true" && "${PYTHON_REQUIREMENTS}" != "requirements-dev.txt" ]]; then
  echo "Optional AI extras installed from requirements-ai.txt"
fi
echo "Run ./run.sh to start the application"

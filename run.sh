#!/bin/bash

# Cat-Scan: Start everything with one command
# Usage: ./run.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_DIR="$SCRIPT_DIR/creative-intelligence"
DASHBOARD_DIR="$SCRIPT_DIR/dashboard"

echo "======================================"
echo "  Cat-Scan - Starting Services"
echo "======================================"
echo ""

# Check venv exists
if [ ! -f "$API_DIR/venv/bin/python" ]; then
    echo "ERROR: Python venv not found!"
    echo "Run: ./setup.sh"
    exit 1
fi

# Check node_modules exists
if [ ! -d "$DASHBOARD_DIR/node_modules" ]; then
    echo "ERROR: Dashboard dependencies not installed!"
    echo "Run: ./setup.sh"
    exit 1
fi

# Kill any existing processes on ports
echo "Checking for existing processes..."
lsof -ti:8000 | xargs -r kill -9 2>/dev/null || true
lsof -ti:3000 | xargs -r kill -9 2>/dev/null || true
sleep 1

# Cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $API_PID 2>/dev/null || true
    kill $DASHBOARD_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start API (using venv python directly - most reliable method)
echo "Starting API server..."
"$API_DIR/venv/bin/python" -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 --app-dir "$API_DIR" &
API_PID=$!

# Wait for API to be healthy
echo "Waiting for API to start..."
for i in {1..15}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "API is healthy!"
        break
    fi
    if [ $i -eq 15 ]; then
        echo "ERROR: API failed to start after 15 seconds"
        echo "Check logs above for errors"
        kill $API_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
done

# Start Dashboard
echo "Starting Dashboard..."
cd "$DASHBOARD_DIR"
npm run dev &
DASHBOARD_PID=$!

# Wait for Dashboard
sleep 5

echo ""
echo "======================================"
echo "  Services Running"
echo "======================================"
echo ""
echo "  API:       http://localhost:8000"
echo "  API Docs:  http://localhost:8000/docs"
echo "  Dashboard: http://localhost:3000"
echo ""
echo "  Press Ctrl+C to stop all services"
echo "======================================"
echo ""

# Wait for processes
wait

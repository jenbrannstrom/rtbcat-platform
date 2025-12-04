#!/bin/bash

# Cat-Scan: Start everything with one command
# Usage: ./run.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "======================================"
echo "  Cat-Scan - Starting Services"
echo "======================================"
echo ""

# Cleanup on exit
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $API_PID 2>/dev/null
    kill $DASHBOARD_PID 2>/dev/null
    exit 0
}
trap cleanup SIGINT SIGTERM

# Start API
echo "Starting API server..."
cd "$SCRIPT_DIR/creative-intelligence"
source venv/bin/activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000 &
API_PID=$!

# Wait for API to start
sleep 2

# Start Dashboard
echo "Starting Dashboard..."
cd "$SCRIPT_DIR/dashboard"
npm run dev &
DASHBOARD_PID=$!

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

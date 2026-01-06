#!/bin/bash
# Cat-Scan Run Script
# Starts API and Dashboard concurrently

set -e

echo "=== Starting Cat-Scan ==="

# Start API in background
echo "Starting API server on http://localhost:8000..."
./venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 &
API_PID=$!

# Wait for API to be ready
for i in {1..30}; do
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo "API ready!"
        break
    fi
    sleep 1
done

# Start Dashboard
echo "Starting Dashboard on http://localhost:3000..."
cd dashboard && npm run dev &
DASH_PID=$!

echo ""
echo "=== Cat-Scan Running ==="
echo "Dashboard: http://localhost:3000"
echo "API:       http://localhost:8000"
echo "API Docs:  http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Handle shutdown
trap "kill $API_PID $DASH_PID 2>/dev/null" EXIT
wait

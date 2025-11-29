#!/bin/bash

cd /home/jen/Documents/rtbcat-platform/creative-intelligence

# Activate virtual environment
source venv/bin/activate

# Start FastAPI backend
echo "Starting RTB.cat Creative Intelligence API..."
echo "API will be available at: http://localhost:8000"
echo "API Docs available at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

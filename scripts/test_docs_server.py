"""Minimal standalone server for testing docs endpoints only.

Usage:
    source venv/bin/activate
    python scripts/test_docs_server.py

Serves on port 8000. No Postgres needed.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routers.docs import router as docs_router

app = FastAPI(title="Docs Test Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(docs_router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

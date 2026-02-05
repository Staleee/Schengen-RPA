"""
Schengen RPA – Unified API (France + Germany)
============================================
One service, two endpoint namespaces:

  /france/*  – France-Visas: register-and-verify, login
  /germany/* – VIDEX form: fill (generate PDF)
"""

import sys
from pathlib import Path

from fastapi import FastAPI

# Repo root (where this file lives)
BASE = Path(__file__).resolve().parent

# Load France app (add France folder to path first)
_france_root = BASE / "france schengen visa application rpa"
if str(_france_root) not in sys.path:
    sys.path.insert(0, str(_france_root))
from api_server import app as france_app

# Load Germany app (add Germany folder to path first)
_germany_root = BASE / "germany schengen visa application rpa"
if str(_germany_root) not in sys.path:
    sys.path.insert(0, str(_germany_root))
from src.api import app as germany_app

# Main app
app = FastAPI(
    title="Schengen RPA API",
    description="France & Germany Schengen visa automation – one service, two endpoints.",
    version="1.0.0",
)


@app.get("/")
async def root():
    """Health + usage."""
    return {
        "status": "ok",
        "service": "Schengen RPA API",
        "endpoints": {
            "france": {
                "base": "/france",
                "register_and_verify": "POST /france/register-and-verify",
                "login": "POST /france/login",
                "health": "GET /france/health",
            },
            "germany": {
                "base": "/germany",
                "fill": "POST /germany/fill",
                "health": "GET /germany/health",
            },
        },
    }


@app.get("/health")
async def health():
    """Unified health check for Railway."""
    return {"status": "ok", "service": "Schengen RPA API"}


# Mount France at /france, Germany at /germany
app.mount("/france", france_app)
app.mount("/germany", germany_app)

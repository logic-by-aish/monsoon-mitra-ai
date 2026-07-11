"""FastAPI application entrypoint.

Serves the JSON API under /api/* and the static frontend at /. Health at /api/healthz
(NOT bare /healthz — Google's frontend reserves it on Cloud Run).
"""
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routes import advisory, hazard, meta, plan, profile

logging.basicConfig(level=logging.INFO)
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "MonsoonMitra.ai — GenAI monsoon preparedness & citizen assistance: "
        "personalized preparedness plans, weather-aware guidance, emergency "
        "checklists, travel advisories, safety recommendations, multilingual "
        "assistance, and real-time alerts."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers (registered BEFORE the static mount so /api/* wins).
app.include_router(meta.router)
app.include_router(profile.router)
app.include_router(plan.router)
app.include_router(advisory.router)
app.include_router(hazard.router)

# Static frontend at "/" (index.html, login.html, assets). Mounted last.
_frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_frontend_dir), html=True), name="frontend")

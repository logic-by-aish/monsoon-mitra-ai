"""Public endpoints: health + non-secret web config for the browser."""
from fastapi import APIRouter, Depends

from ..config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/healthz")
def healthz():
    """Health/readiness. Use /api/healthz — Google's frontend reserves bare /healthz."""
    return {"status": "ok"}


@router.get("/config")
def web_config(settings: Settings = Depends(get_settings)):
    """Firebase WEB config: public identifiers, safe to hand to the browser."""
    return settings.firebase_web_config()

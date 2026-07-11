"""📸 Photo Hazard Scanner — multimodal safety recommendations with upload guards."""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from .. import orchestrator
from ..config import Settings, get_settings
from ..deps import get_current_user, get_gemini_client
from ..gemini_client import GeminiClient
from ..schemas import HazardReport, User

router = APIRouter(prefix="/api", tags=["hazard"])


@router.post("/hazard-scan", response_model=HazardReport)
async def hazard_scan(
    photo: UploadFile = File(...),
    language: str = Form(default="English", max_length=40),
    _user: User = Depends(get_current_user),
    gemini: GeminiClient = Depends(get_gemini_client),
    settings: Settings = Depends(get_settings),
):
    if photo.content_type not in settings.allowed_image_types_list:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported image type; use one of {settings.allowed_image_types}.",
        )
    data = await photo.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty upload.")
    if len(data) > settings.max_image_bytes:
        raise HTTPException(status_code=413, detail="Image exceeds the 6 MB limit.")

    try:
        return orchestrator.scan_hazards(gemini, data, photo.content_type, language[:40])
    except ValueError:
        raise HTTPException(status_code=502, detail="AI response could not be parsed; please retry.")

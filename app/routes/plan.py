"""Personalized preparedness plan + emergency checklist endpoints."""
import logging

from fastapi import APIRouter, Depends, HTTPException

from .. import orchestrator
from ..deps import get_current_user, get_gemini_client, get_repository
from ..gemini_client import GeminiClient
from ..repository import Repository
from ..schemas import KitRequest, PackedKit, PlanRequest, PlanResponse, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["plan"])


@router.post("/plan", response_model=PlanResponse)
async def create_plan(
    body: PlanRequest,
    user: User = Depends(get_current_user),
    gemini: GeminiClient = Depends(get_gemini_client),
    repo: Repository = Depends(get_repository),
):
    try:
        result = await orchestrator.generate_plan(gemini, body)
    except ValueError:
        # Malformed model output is a bad-gateway condition, never a crash.
        raise HTTPException(status_code=502, detail="AI response could not be parsed; please retry.")
    try:
        repo.save_record(user.uid, "plan", result.model_dump())
    except Exception:
        logger.warning("Firestore plan save failed for %s", user.uid)
    return result


@router.post("/kit", response_model=PackedKit)
def create_kit(
    body: KitRequest,
    user: User = Depends(get_current_user),
    gemini: GeminiClient = Depends(get_gemini_client),
    repo: Repository = Depends(get_repository),
):
    try:
        result = orchestrator.build_kit(gemini, body)
    except ValueError:
        raise HTTPException(status_code=502, detail="AI response could not be parsed; please retry.")
    try:
        repo.save_record(user.uid, "kit", result.model_dump())
    except Exception:
        logger.warning("Firestore kit save failed for %s", user.uid)
    return result

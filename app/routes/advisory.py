"""Real-time alerts + travel advisories (Google Search grounding, cited)."""
from fastapi import APIRouter, Depends

from .. import orchestrator
from ..deps import get_current_user, get_gemini_client
from ..gemini_client import GeminiClient
from ..schemas import (
    AdvisoryRequest,
    AdvisoryResponse,
    AlertsRequest,
    AlertsResponse,
    User,
)

router = APIRouter(prefix="/api", tags=["advisory"])


@router.post("/alerts", response_model=AlertsResponse)
def alerts(
    body: AlertsRequest,
    _user: User = Depends(get_current_user),
    gemini: GeminiClient = Depends(get_gemini_client),
):
    return AlertsResponse(brief=orchestrator.get_alerts(gemini, body))


@router.post("/advisory", response_model=AdvisoryResponse)
def advisory(
    body: AdvisoryRequest,
    _user: User = Depends(get_current_user),
    gemini: GeminiClient = Depends(get_gemini_client),
):
    return AdvisoryResponse(brief=orchestrator.get_advisory(gemini, body))

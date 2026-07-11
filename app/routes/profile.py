"""Household profile endpoints (Firestore-backed, best-effort persistence)."""
import logging

from fastapi import APIRouter, Depends

from ..deps import get_current_user, get_repository
from ..repository import Repository
from ..schemas import HouseholdProfile, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/me")
def get_me(
    user: User = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
):
    profile = None
    try:
        profile = repo.get_profile(user.uid)
    except Exception:  # persistence is best-effort — never fails a request
        logger.warning("Firestore profile read failed for %s", user.uid)
    return {"user": user.model_dump(), "profile": profile}


@router.put("/me")
def put_me(
    body: HouseholdProfile,
    user: User = Depends(get_current_user),
    repo: Repository = Depends(get_repository),
):
    body.uid = user.uid  # identity comes from the verified token, never the body
    try:
        repo.upsert_profile(body)
    except Exception:
        logger.warning("Firestore profile write failed for %s", user.uid)
    return {"profile": body.model_dump()}

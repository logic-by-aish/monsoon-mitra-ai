"""FastAPI dependency providers.

Every external dependency (settings, Gemini, Firestore, the authenticated user) is
provided here. Routes depend on these; tests override them via
`app.dependency_overrides`, so the API is exercisable with no cloud access.
"""
from functools import lru_cache
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from .config import Settings, get_settings
from .gemini_client import GeminiClient
from .repository import Repository
from .schemas import User
from .security import verify_firebase_token


@lru_cache
def get_gemini_client() -> GeminiClient:
    return GeminiClient()


@lru_cache
def get_repository() -> Repository:
    return Repository()


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> User:
    """Resolve identity from a verified Firebase ID token (Email/Password or Google).

    With auth_required=False (local dev only) a demo user is returned. Production
    MUST run with auth_required=True.
    """
    if not settings.auth_required:
        return User(uid="demo-user", email="demo@example.com", display_name="Demo User")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = verify_firebase_token(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    firebase_info = claims.get("firebase", {}) or {}
    return User(
        uid=claims.get("uid") or claims.get("user_id"),
        email=claims.get("email"),
        display_name=claims.get("name"),
        photo_url=claims.get("picture"),
        provider=firebase_info.get("sign_in_provider"),
    )

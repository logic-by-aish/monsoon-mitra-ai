"""Auth: server-side Firebase ID token verification on every protected route."""
import pytest
from fastapi import HTTPException

from app import deps
from app.config import Settings


def _settings(auth_required=True) -> Settings:
    return Settings(auth_required=auth_required, _env_file=None)


def test_missing_token_401():
    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(authorization=None, settings=_settings())
    assert exc.value.status_code == 401


def test_wrong_scheme_401():
    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(authorization="Basic abc123", settings=_settings())
    assert exc.value.status_code == 401


def test_invalid_token_401(monkeypatch):
    def boom(token):
        raise ValueError("bad token")

    monkeypatch.setattr(deps, "verify_firebase_token", boom)
    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(authorization="Bearer not-a-real-token", settings=_settings())
    assert exc.value.status_code == 401


def test_valid_token_maps_identity(monkeypatch):
    claims = {
        "uid": "user-42", "email": "priya@example.com", "name": "Priya",
        "picture": "https://example.com/p.jpg",
        "firebase": {"sign_in_provider": "google.com"},
    }
    monkeypatch.setattr(deps, "verify_firebase_token", lambda t: claims)
    user = deps.get_current_user(authorization="Bearer good-token", settings=_settings())
    assert user.uid == "user-42" and user.email == "priya@example.com"
    assert user.provider == "google.com"


def test_dev_bypass_returns_demo_user_only_when_auth_disabled():
    user = deps.get_current_user(authorization=None, settings=_settings(auth_required=False))
    assert user.uid == "demo-user"

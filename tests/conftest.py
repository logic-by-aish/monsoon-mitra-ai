"""Shared fixtures. Cloud clients are dependency-injected fakes, so the suite runs
with no Firebase/Gemini credentials — and independently of any local .env
(auth stays REQUIRED in tests even when a dev .env disables it)."""
import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.config import Settings, get_settings
    from app.main import app

    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()

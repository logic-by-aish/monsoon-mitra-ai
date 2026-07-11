"""Shared fixtures. Cloud clients are dependency-injected fakes, so the suite runs
with no Firebase/Gemini credentials."""
import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()

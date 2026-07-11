"""API smoke tests via TestClient — cloud clients replaced through DI overrides."""
import io

from app.deps import get_current_user, get_gemini_client, get_repository
from app.main import app
from app.schemas import User
from tests.factories import FakeGemini, FakeRepo


def _sign_in(fake_gemini=None, fake_repo=None):
    app.dependency_overrides[get_current_user] = lambda: User(
        uid="u1", email="test@example.com", display_name="Test"
    )
    app.dependency_overrides[get_gemini_client] = lambda: fake_gemini or FakeGemini()
    app.dependency_overrides[get_repository] = lambda: fake_repo or FakeRepo()


def test_healthz(client):
    resp = client.get("/api/healthz")
    assert resp.status_code == 200 and resp.json()["status"] == "ok"


def test_config_is_public_and_non_secret(client):
    resp = client.get("/api/config")
    assert resp.status_code == 200
    assert "apiKey" in resp.json()  # Firebase WEB key — public identifier by design


def test_protected_route_without_token_401(client):
    resp = client.post("/api/plan", json={"city": "Mumbai"})
    assert resp.status_code == 401


def test_plan_returns_all_artifacts_and_persists(client):
    repo = FakeRepo()
    _sign_in(fake_repo=repo)
    resp = client.post("/api/plan", json={"city": "Mumbai", "infants": 1, "language": "Hindi"})
    assert resp.status_code == 200
    body = resp.json()
    assert {s["phase"] for s in body["plan"]["sections"]} == {"before", "during", "after"}
    assert body["weather_brief"]["citations"]
    assert repo.records["u1"][0]["label"] == "plan"


def test_kit_returns_packed_overflow_and_score(client):
    _sign_in()
    resp = client.post("/api/kit", json={"city": "Pune", "budget_inr": 3000})
    assert resp.status_code == 200
    body = resp.json()
    assert body["within_budget"] is True
    assert body["readiness_score"] > 0
    assert body["packed"] and body["overflow"] == []
    assert body["refinement_rounds"] == 1


def test_kit_rejects_invalid_budget_422(client):
    _sign_in()
    resp = client.post("/api/kit", json={"city": "Pune", "budget_inr": 5})
    assert resp.status_code == 422


def test_alerts_endpoint_returns_citations(client):
    _sign_in()
    resp = client.post("/api/alerts", json={"city": "Chennai", "language": "Tamil"})
    assert resp.status_code == 200
    assert resp.json()["brief"]["citations"][0]["uri"].startswith("https://")


def test_hazard_scan_rejects_bad_mime_415(client):
    _sign_in()
    resp = client.post(
        "/api/hazard-scan",
        files={"photo": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 415


def test_hazard_scan_rejects_empty_upload_400(client):
    _sign_in()
    resp = client.post(
        "/api/hazard-scan",
        files={"photo": ("street.png", io.BytesIO(b""), "image/png")},
    )
    assert resp.status_code == 400


def test_hazard_scan_happy_path(client):
    _sign_in()
    resp = client.post(
        "/api/hazard-scan",
        files={"photo": ("street.png", io.BytesIO(b"\x89PNG fake image bytes"), "image/png")},
        data={"language": "English"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["identified"] is True and body["hazards"]

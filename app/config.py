"""Application settings, loaded from environment / .env.

No secrets or project-specific values are hard-coded — everything comes from the
environment (12-factor + security).
"""
from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # ---- App ----
    app_name: str = "MonsoonMitra.ai"
    allowed_origins: str = "*"
    # When False (local dev only) auth is bypassed with a demo user. MUST be True in prod.
    auth_required: bool = True

    # ---- Gemini ----
    gemini_model: str = "gemini-2.5-flash"  # verified live; this key's 3.5 quota is exhausted
    gemini_model_fallback: str = "gemini-2.0-flash"  # auto-retry when primary 404s/503s/429s
    # False → Gemini Developer API (API key). True → Vertex AI (ADC, no key).
    use_vertexai: bool = False
    google_cloud_project: str = ""
    google_cloud_location: str = "us-central1"
    gemini_api_key: str = ""  # injected from Secret Manager in prod; never committed
    google_maps_api_key: str = ""

    # ---- Firebase (web config is public / non-secret) ----
    firebase_project_id: str = ""
    firebase_web_api_key: str = ""
    firebase_auth_domain: str = ""
    firebase_app_id: str = ""

    # ---- Upload guards ----
    max_image_bytes: int = 6 * 1024 * 1024  # 6 MB
    allowed_image_types: str = "image/jpeg,image/png,image/webp"

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def allowed_image_types_list(self) -> List[str]:
        return [t.strip() for t in self.allowed_image_types.split(",") if t.strip()]

    def firebase_web_config(self) -> dict:
        """Non-secret config handed to the browser to initialise Firebase Auth."""
        return {
            "apiKey": self.firebase_web_api_key,
            "authDomain": self.firebase_auth_domain
            or f"{self.firebase_project_id}.firebaseapp.com",
            "projectId": self.firebase_project_id,
            "appId": self.firebase_app_id,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()

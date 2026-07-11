"""Server-side verification of Firebase ID tokens.

`verify_firebase_token` is a small seam: the real implementation calls the Firebase
Admin SDK; tests monkeypatch this one function to exercise auth without Firebase or
network. Works for both Email/Password and Google sign-in (same ID token).
"""


def verify_firebase_token(id_token: str) -> dict:
    """Verify a Firebase ID token and return its decoded claims. Raises on invalid."""
    from firebase_admin import auth

    from .firebase_app import ensure_firebase_app

    ensure_firebase_app()
    return auth.verify_id_token(id_token)

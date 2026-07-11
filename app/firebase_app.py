"""Lazy, idempotent Firebase Admin initialisation.

On Cloud Run this uses Application Default Credentials (the runtime service
account) — no key file. Deferred until first use so importing the app needs no
SDK or credentials (keeps tests credential-free).
"""
_initialized = False


def ensure_firebase_app() -> None:
    global _initialized
    if _initialized:
        return

    import firebase_admin

    if not firebase_admin._apps:
        from .config import get_settings

        settings = get_settings()
        options = {}
        if settings.firebase_project_id:
            options["projectId"] = settings.firebase_project_id
        firebase_admin.initialize_app(options=options or None)

    _initialized = True

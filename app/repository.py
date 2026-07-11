"""Cloud Firestore data access.

`google.cloud.firestore` is imported lazily inside methods, so importing the app
needs no credentials (tests inject FakeRepo). All persistence is best-effort:
callers wrap saves in try/except so a Firestore hiccup never fails a user request.
"""
from typing import Any, Dict, List, Optional


class Repository:
    def __init__(self, client: Any = None):
        self._client = client

    def _db(self):
        if self._client is None:
            from firebase_admin import firestore  # lazy

            from .firebase_app import ensure_firebase_app

            ensure_firebase_app()
            self._client = firestore.client()
        return self._client

    # ---- profiles ----
    def get_profile(self, uid: str) -> Optional[Dict[str, Any]]:
        doc = self._db().collection("users").document(uid).get()
        return doc.to_dict() if doc.exists else None

    def upsert_profile(self, profile) -> None:
        self._db().collection("users").document(profile.uid).set(
            profile.model_dump(), merge=True
        )

    # ---- domain records (rename per project: trips/plans/sessions/...) ----
    def save_record(self, uid: str, label: str, payload: Dict[str, Any]) -> str:
        ref = (
            self._db()
            .collection("users")
            .document(uid)
            .collection("records")
            .document()
        )
        ref.set({"label": label, "payload": payload})
        return ref.id

    def list_records(self, uid: str, limit: int = 20) -> List[Dict[str, Any]]:
        docs = (
            self._db()
            .collection("users")
            .document(uid)
            .collection("records")
            .limit(limit)
            .stream()
        )
        return [d.to_dict() | {"id": d.id} for d in docs]

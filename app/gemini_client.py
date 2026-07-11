"""Wrapper around the google-genai SDK.

Design:
  * `google.genai` is imported LAZILY (inside methods) so importing this module —
    and the whole app — needs no SDK or cloud credentials. Tests inject a fake.
  * `generate_structured` uses response_schema for validated Pydantic output.
  * `generate_grounded` enables the Google Search tool and returns text + the web
    citations from grounding metadata (real, current info — anti-hallucination).
  * `generate_text` / `image_part` support long-form and multimodal (photo) input.

NOTE: Search grounding and a strict response_schema CANNOT be combined on one
request — use a grounded pass then a structuring pass (two calls) when you need both.
"""
from typing import Any, Dict, List, Type

from pydantic import BaseModel

from .config import Settings, get_settings


def _is_model_availability_error(exc: Exception) -> bool:
    """404 (model id retired) or 503 (model overloaded) — retry-able on fallback."""
    msg = str(exc)
    return any(m in msg for m in ("404", "NOT_FOUND", "not found", "503", "UNAVAILABLE", "overloaded"))


class GeminiClient:
    def __init__(self, raw_client: Any = None, model: str = None):
        settings: Settings = get_settings()
        self.model = model or settings.gemini_model
        self.fallback_model = settings.gemini_model_fallback
        if raw_client is not None:
            self._client = raw_client
            return
        from google import genai  # lazy

        if settings.use_vertexai:
            self._client = genai.Client(
                vertexai=True,
                project=settings.google_cloud_project or None,
                location=settings.google_cloud_location,
            )
        else:
            self._client = genai.Client(api_key=settings.gemini_api_key)

    def _generate(self, contents: List[Any], config: Any) -> Any:
        """One retry on the pinned fallback model when the primary id 404s/503s
        (a real failure mode we hit in rehearsal)."""
        try:
            return self._client.models.generate_content(
                model=self.model, contents=contents, config=config
            )
        except Exception as exc:  # noqa: BLE001 — inspect and re-raise if not availability
            if self.fallback_model and self.fallback_model != self.model and _is_model_availability_error(exc):
                return self._client.models.generate_content(
                    model=self.fallback_model, contents=contents, config=config
                )
            raise

    # ---- multimodal ----
    def image_part(self, data: bytes, mime_type: str) -> Any:
        from google.genai import types

        return types.Part.from_bytes(data=data, mime_type=mime_type)

    # ---- structured JSON ----
    def generate_structured(
        self, *, system_instruction: str, contents: List[Any],
        response_schema: Type[BaseModel], temperature: float = 0.6,
    ) -> BaseModel:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=temperature,
        )
        resp = self._generate(contents, config)
        parsed = getattr(resp, "parsed", None)
        if isinstance(parsed, response_schema):
            return parsed
        import json

        text = getattr(resp, "text", None)
        if not text:
            raise ValueError("Gemini returned no parseable content.")
        return response_schema.model_validate(json.loads(text))

    # ---- long-form text ----
    def generate_text(
        self, *, system_instruction: str, contents: List[Any], temperature: float = 0.8
    ) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_instruction, temperature=temperature
        )
        resp = self._generate(contents, config)
        return getattr(resp, "text", "") or ""

    # ---- grounded (Google Search) ----
    def generate_grounded(
        self, *, system_instruction: str, contents: List[Any], temperature: float = 0.4
    ) -> Dict[str, Any]:
        """Return {'text': str, 'citations': [{'title','uri'}]} using Search grounding."""
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
        resp = self._generate(contents, config)
        return {"text": getattr(resp, "text", "") or "", "citations": _extract_citations(resp)}


def _extract_citations(resp: Any) -> List[Dict[str, str]]:
    """Pull web sources from grounding metadata, tolerant to SDK shape changes."""
    out: List[Dict[str, str]] = []
    seen = set()
    try:
        candidates = getattr(resp, "candidates", None) or []
        for cand in candidates:
            meta = getattr(cand, "grounding_metadata", None)
            for chunk in (getattr(meta, "grounding_chunks", None) or []):
                web = getattr(chunk, "web", None)
                uri = getattr(web, "uri", "") or ""
                title = getattr(web, "title", "") or ""
                if uri and uri not in seen:
                    seen.add(uri)
                    out.append({"title": title, "uri": uri})
    except Exception:  # noqa: BLE001 — citations are best-effort metadata
        pass
    return out

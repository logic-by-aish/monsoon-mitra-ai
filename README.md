# 🌧️ MonsoonMitra.ai — Monsoon Preparedness & Citizen Assistance

MonsoonMitra.ai helps individuals, families, and communities **prepare for the monsoon season** with GenAI: **personalized preparedness plans** phased **before, during, and after severe weather events**, **weather-aware guidance** and **real-time alerts** grounded in live Google Search with citations, budget-fitted **emergency checklists**, route-specific **travel advisories**, photo-based **safety recommendations** (📸 Hazard Scanner), and **multilingual assistance** in 12 Indian languages.

Built for **PromptWar (Google × Hack2skill) — MAIN ROUND**.

> Full product spec: [SPEC.md](SPEC.md)

---

## Required capabilities → features

| Required capability (verbatim) | MonsoonMitra.ai feature | Gemini technique |
|---|---|---|
| personalized preparedness plans | `/api/plan` — plan tuned to household, home type & city | structured output (`response_schema`) |
| weather-aware guidance | live weather brief attached to every plan | **Google Search grounding** (cited) |
| emergency checklists | `/api/kit` — budget-packed kit, agentic refine loop | structured output + **deterministic packer** |
| travel advisories | `/api/advisory` — road/rail/air route guidance | Google Search grounding (cited) |
| safety recommendations | 📸 `/api/hazard-scan` — photo → hazards + fixes | **multimodal** image input |
| multilingual assistance | `language` on every endpoint; 12 languages in UI | prompt-level language control |
| real-time alerts | `/api/alerts` — current official warnings per city | Google Search grounding (cited) |
| before, during, and after severe weather events | plan sections typed `Literal["before","during","after"]` | structured output enum |

**The split that makes it trustworthy:** Gemini *suggests* (which items suit a family with an infant and a diabetic elder); pure Python *decides* (quantity math, greedy priority-per-rupee budget packing, readiness score). The LLM never does silent arithmetic; overflow items are surfaced, never dropped.

**Agentic element:** the kit endpoint runs a **bounded feedback loop** — Gemini suggests, the deterministic evaluator checks budget/essential coverage, and on failure Gemini retries **once** with concrete numbers ("over by ₹740; missing: medical"). Max 2 rounds, honest `within_budget` flag if it still doesn't fit. The plan endpoint is a **two-call fan-out** (`asyncio.gather`): a structured pass + a grounded pass, because Search grounding and a strict `response_schema` cannot combine in one request.

---

## Architecture (Google Cloud)

```
Browser ──HTTPS──▶ Cloud Run (FastAPI + static frontend, asia-south1)
  │ Firebase Auth (Email/Password) → ID token
  │ every /api call: Authorization: Bearer <ID token>
  ▼
Cloud Run backend ──verify token──▶ Firebase Admin SDK (Auth)
  │ ADC (runtime SA)                ├── Cloud Firestore  (profiles, saved plans & kits)
  ▼                                 └── Gemini via google-genai
Gemini: response_schema · Google Search grounding · multimodal image input
Secrets: Gemini API key in Secret Manager (never in repo)
```

- **Model:** `gemini-3.5-flash` (env-pinned, verified against the live API at deploy). Automatic fallback retry on `gemini-2.5-flash` when the primary id 404s/503s — a failure mode we actually hit in rehearsal.
- **LLM vs. deterministic split:** Gemini suggests, `app/kit_core.py` packs, scores, and verdicts.

## Project layout

```
app/
  main.py           FastAPI app, routers, static mount, /api/healthz
  config.py         env-driven settings (12-factor, no hard-coded values)
  schemas.py        Pydantic models — inputs capped/bounded; LLM outputs strict
  kit_core.py       deterministic kit packer + readiness score (pure, unit-tested)
  orchestrator.py   GenAI orchestration: 2-call plan fan-out, bounded kit loop,
                    grounded alerts/advisories, multimodal hazard scan, injection fencing
  gemini_client.py  google-genai wrapper: structured · grounded · multimodal (lazy import)
  security.py       Firebase ID token verification
  repository.py     Firestore data access (best-effort persistence)
  deps.py           dependency-injection providers (overridable in tests)
  routes/           meta · profile · plan+kit · alerts+advisory · hazard-scan
frontend/           login.html · app.html · index.html · app.js · firebase-init.js · styles.css
tests/              42-case pytest suite (runs with NO cloud credentials)
Dockerfile · requirements*.txt · .env.example · SPEC.md
```

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env    # fill GEMINI_API_KEY + FIREBASE_* (or AUTH_REQUIRED=false for a quick look)
uvicorn app.main:app --reload --port 8080
```

## Test

```bash
pytest        # 42 passed — all cloud clients are dependency-injected fakes, no credentials needed
```

## Deploy to Cloud Run

```bash
PROJECT=project-7dd8dd18-ed36-467b-a8c
REGION=asia-south1

gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
  artifactregistry.googleapis.com firestore.googleapis.com secretmanager.googleapis.com --project $PROJECT

printf '%s' "$GEMINI_API_KEY" | gcloud secrets create monsoonmitra-gemini-key --data-file=- --project $PROJECT

gcloud run deploy monsoonmitra --source . --region $REGION --allow-unauthenticated --memory 1Gi \
  --project $PROJECT \
  --set-env-vars "AUTH_REQUIRED=true,GEMINI_MODEL=gemini-3.5-flash,GEMINI_MODEL_FALLBACK=gemini-2.5-flash,FIREBASE_PROJECT_ID=$PROJECT,FIREBASE_WEB_API_KEY=<web-key>,FIREBASE_AUTH_DOMAIN=$PROJECT.firebaseapp.com,FIREBASE_APP_ID=<app-id>" \
  --set-secrets "GEMINI_API_KEY=monsoonmitra-gemini-key:latest"

# least-privilege runtime SA
SA=$(gcloud run services describe monsoonmitra --region $REGION --project $PROJECT --format 'value(spec.template.spec.serviceAccountName)')
gcloud projects add-iam-policy-binding $PROJECT --member="serviceAccount:$SA" --role=roles/datastore.user --condition=None
gcloud secrets add-iam-policy-binding monsoonmitra-gemini-key --member="serviceAccount:$SA" --role=roles/secretmanager.secretAccessor --project $PROJECT
```

### One-time Firebase Auth setup
Firebase Console → Authentication → enable **Email/Password** (the one provider step that can't be done via API). A one-click **demo account** (`test@gmail.com`) is also wired into the login page for instant access.

**Firestore rules** (defense in depth — server already scopes every read/write to the verified uid):
```
rules_version = '2';
service cloud.firestore {
  match /databases/{db}/documents {
    match /users/{uid}/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
  }
}
```

---

## Security

- **No secrets in the repo or client** — Gemini key lives in Secret Manager; Firebase *web* config is public by design.
- **Server-side auth** — Firebase ID token verified via Admin SDK on every protected route (`401` otherwise).
- **Least-privilege runtime SA** — `roles/datastore.user` + `secretAccessor` on one secret only.
- **Input validation as security** — size caps on every free-text field, bounds on every number; uploads: MIME allowlist → `415`, 6 MB cap → `413`, empty → `400`.
- **Prompt-injection defense** — all user free text is fenced `<<<USER_DATA … USER_DATA>>>` and labeled untrusted; every system prompt carries an explicit SECURITY instruction; `response_schema` constrains output shape. Covered by a test that feeds `"ignore previous instructions"` and asserts the fence.
- **Anti-hallucination** — alerts/advisories are Search-grounded with citations and instructed "never invent an alert"; the hazard scanner must return `identified=false` rather than fabricate.
- **XSS defense** — every user/LLM string is `escapeHtml()`-ed before DOM insertion.

## How this maps to the judging criteria

| Criterion | Where |
|---|---|
| **Problem alignment** | All 8 required capabilities are first-class features (table above) using the problem statement's exact vocabulary; the 📸 Hazard Scanner is the memorable, on-theme wow. |
| **Code quality** | Layered DI modules, typed Pydantic models, LLM-vs-deterministic split, lazy cloud imports, bounded agentic loop with honest flags. |
| **Security** | Section above — implemented and tested (401s, 415/413/400, injection fencing), not just claimed. |
| **Testing** | `pytest`: 42 credential-free cases — pure core (12) + schemas (6) + orchestration with a fake Gemini (9) + auth (5) + API smoke (10). |
| **Google Cloud alignment** | Cloud Run (asia-south1) + Gemini structured/grounded/multimodal + Firebase Auth + Firestore + Secret Manager; one-command source deploy. |

## Lessons applied from previous rounds

Health endpoint is **`/api/healthz`** (bare `/healthz` is reserved by Google's frontend) · Firebase providers enabled before build · billing verified before deploy · Gemini key only in Secret Manager · model id pinned via env **with an automatic fallback retry** after a real 503 in rehearsal.

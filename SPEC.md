# PRD — MonsoonMitra.ai: Monsoon Preparedness & Citizen Assistance

> **Event:** PromptWar (Google × Hack2skill) — MAIN ROUND
> **One-liner:** MonsoonMitra.ai is a GenAI-powered companion that helps individuals, families, and communities prepare for the monsoon season with **personalized preparedness plans**, **weather-aware guidance**, **emergency checklists**, **travel advisories**, **safety recommendations**, **multilingual assistance**, and **real-time alerts** — before, during, and after severe weather events.
> **Stack (locked):** Python + FastAPI on **Cloud Run** · **Gemini** via `google-genai` on **Vertex AI** (structured output + Google Search grounding + multimodal) · **Firebase Auth** (Email/Password) · **Cloud Firestore** · **Secret Manager**.
> **Evaluation criteria (design targets):** code quality, problem-statement alignment, security, testing, Google Cloud alignment.

---

## 1. Problem Statement

Every year the Indian monsoon displaces families, floods streets, and cuts power — yet most households prepare with generic checklists that ignore their city's actual flood risk, their family's composition (infants, elderly, pets), and their budget. Weather alerts are scattered across apps and mostly in English, excluding millions of non-English speakers. MonsoonMitra.ai collapses that pain into one GenAI flow: a **personalized preparedness plan** phased **before, during, and after severe weather events**, a budget-aware **emergency checklist**, **real-time alerts** and **travel advisories** grounded in live Google Search results with citations, a photo-based home hazard scanner for **safety recommendations**, and **multilingual assistance** in 12 Indian languages.

## 2. Goals

1. **Ship a live, judge-testable Cloud Run demo** where a signed-in user gets a personalized plan, packed emergency kit, live alerts, travel advisory, and photo hazard scan in their chosen language.
2. **Cover every required capability from the problem statement as a first-class, visible feature** (see §5 mapping).
3. **Ground factual output** (real-time alerts, weather guidance, travel advisories) with Google Search grounding — cited, not hallucinated.
4. **Showcase multimodal Gemini**: the 📸 **Hazard Scanner** — photograph your home/street and get monsoon-specific hazards with severity and fixes.
5. **Keep a deterministic, unit-tested core** — the emergency-kit **budget packer** and **readiness score** are pure Python: *the LLM suggests, plain Python decides*.
6. **Score across all criteria by design** (§13).

## 3. Non-Goals (out of scope for v1)

- **Push/SMS notification delivery** — requires telecom integration and opt-in flows; the demo surfaces live alerts in-app.
- **Government IMD/NDMA API integrations** — no public stable APIs with hackathon-friendly quotas; Search grounding covers current advisories.
- **Community coordination features (shelters, volunteer matching)** — separate, heavy product; premature for a demo.
- **Offline/PWA mode** — valuable in disasters but orthogonal to the GenAI evaluation.
- **Native mobile apps** — the responsive web app demos the same flows.
- **Payments/e-commerce for kit items** — regulated and out of scope; we output a costed shopping list instead.

## 4. User Stories

**Priya, 34 — mother of two in Mumbai (flood-prone ground-floor flat)**
- As a parent, I want a preparedness plan tailored to my family (an infant, an elderly parent) so that I don't discover missing essentials mid-flood.
- As a budget-conscious shopper, I want an emergency checklist that fits ₹4,000 so that I buy the highest-impact items first.
- As a Marathi speaker, I want the entire plan in Marathi so that my mother-in-law can follow it too.

**Arjun, 26 — daily commuter, Pune → Mumbai**
- As a commuter, I want a travel advisory for my route during heavy rain so that I can decide between road and rail today.
- As a traveler, I want real-time alerts for my destination city with sources so that I can trust what I'm reading.

**Meera, 58 — resident welfare association lead, Chennai**
- As a community lead, I want to photograph our building's entrance and drains so that I get concrete safety recommendations before the season peaks.
- As an organizer, I want a readiness score so that I can track which households are prepared.

**Edge / negative** (do not skip — judges score these)
- Empty/absurd input (0-member household, ₹0 budget) → validation error, not a broken result.
- A photo with no recognizable monsoon hazards → graceful "nothing identified", never fabricated hazards.
- Kit suggestions exceeding budget → overflow surfaced explicitly with an honest `within_budget` flag, never silently dropped.
- Unauthenticated request to a protected endpoint → `401`.
- "Ignore previous instructions" typed into free-text fields → treated as fenced untrusted data, not commands.

## 5. Required capabilities → concrete features (alignment map)

| # | Required capability (verbatim) | MonsoonMitra.ai feature | Gemini technique |
|---|---|---|---|
| 1 | personalized preparedness plans | `/api/plan` — household-profiled plan, phased before/during/after | structured output (`response_schema`) |
| 2 | weather-aware guidance | live weather brief attached to every plan | **Google Search grounding** + citations |
| 3 | emergency checklists | `/api/kit` — budget-packed emergency kit (agentic loop) | structured output + **deterministic pure-Python packer** |
| 4 | travel advisories | `/api/advisory` — route advisory (road/rail/air) | Google Search grounding + citations |
| 5 | safety recommendations | 📸 `/api/hazard-scan` — photo → hazards with severity & fix | **multimodal** (image + text) |
| 6 | multilingual assistance | `language` on every endpoint; 12 Indian languages in UI | prompt-level language control |
| 7 | real-time alerts | `/api/alerts` — current warnings for a city, cited | Google Search grounding + citations |
| 8 | before, during, and after severe weather events | plan sections are `Literal["before","during","after"]` | structured output enum |

## 6. Core flow

```
[0] AUTH        Firebase ID token (Email/Password) verified server-side
[1] PLAN        Gemini structured pass (personalized, phased) ∥ grounded pass (live weather brief)
                — the two passes run concurrently (asyncio.gather); grounding and
                  response_schema cannot combine in one request, so this is 2 calls by design
[2] KIT         Gemini suggests costed items → pure-Python packer packs within budget
                → if essential categories missing/over budget: retry with CONCRETE numbers
                  ("over by ₹740; missing: medical") — max 2 rounds, honest flag on failure
[3] SCAN        user photographs home/street → Gemini multimodal → hazards (or honest "none found")
[4] SCORE       pure Python readiness score from packed kit coverage
[5] PERSIST     plan/kit saved to Firestore (best-effort, never fails the request)
```

**Key design decision (tell the judges):** Gemini does the creative/knowledge work (which items suit a family with an infant and a diabetic elder); **deterministic Python does the arithmetic and the verdict** — quantity scaling, budget packing, coverage scoring. The math is correct, explainable, and unit-tested; the LLM never does silent arithmetic and never silently drops a user's essentials.

```python
def pack_kit(items, budget_inr):
    """Greedy pack by priority-per-rupee, essentials first. Deterministic."""
    essentials = [i for i in items if i.category in ESSENTIAL_CATEGORIES]
    others     = [i for i in items if i.category not in ESSENTIAL_CATEGORIES]
    packed, overflow, spent = [], [], 0
    for item in sorted(essentials, key=value_density, reverse=True) + \
                sorted(others,     key=value_density, reverse=True):
        cost = item.unit_cost_inr * item.quantity
        if spent + cost <= budget_inr:
            packed.append(item); spent += cost
        else:
            overflow.append(item)          # surfaced, never silently dropped
    return packed, overflow, spent
```

## 7. Data model & API

**Firestore layout**
```
users/{uid}              → household profile (city, members, language)
users/{uid}/records/{id} → saved plans & kits
```

**API** (all `/api/*` except health/config require a valid Firebase ID token)
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/healthz` | public | health (**not** bare `/healthz` — Google's frontend reserves it) |
| GET | `/api/config` | public | Firebase web config (non-secret) |
| GET/PUT | `/api/me` | ✅ | household profile |
| POST | `/api/plan` | ✅ | personalized preparedness plan + grounded weather brief |
| POST | `/api/kit` | ✅ | emergency checklist — agentic budget-packing loop |
| POST | `/api/alerts` | ✅ | real-time alerts for a city (grounded, cited) |
| POST | `/api/advisory` | ✅ | travel advisory for a route (grounded, cited) |
| POST | `/api/hazard-scan` | ✅ | multimodal photo → safety recommendations |

## 8. Requirements

### Must-Have — P0
| # | Requirement | Acceptance criteria |
|---|---|---|
| P0-1 | Auth: Email/Password | Sign-in works (plus a one-click demo account); protected APIs → `401` without a valid token. |
| P0-2 | Personalized preparedness plan | ≥3 phased sections (before/during/after), each action with a personalized rationale, in the chosen language. |
| P0-3 | Weather-aware guidance | Plan includes a live weather brief with ≥0 real citations; grounding failure degrades gracefully. |
| P0-4 | Emergency checklist | Kit packed within budget; overflow listed; `within_budget` honest; readiness score 0–100. |
| P0-5 | Travel advisories | Route advisory with citations for origin→destination and mode. |
| P0-6 | Safety recommendations (multimodal) | Photo upload → hazards with severity + fix, or honest "none identified"; MIME/size guards (415/413). |
| P0-7 | Multilingual assistance | `language` respected on every endpoint; 12 languages selectable in UI. |
| P0-8 | Real-time alerts | Current city warnings, cited, refreshable. |
| P0-9 | Structured Gemini output | `response_schema` everywhere; malformed output never 500s. |
| P0-10 | Deployed on Cloud Run | Public URL; `GET /api/healthz` → 200. |
| P0-11 | Security baseline | No secrets in repo; server-side token verify; least-privilege SA; input + upload validation; prompt-injection fencing. |

### Should-Have — P1
- Saved plans/kits per user in Firestore, listed in the UI.
- Agentic retry loop surfaces its rounds ("refined once to fit your budget").
- Model fallback: primary Gemini model id pinned via env, automatic retry on a fallback id.

### Could-Have — P2
- Shareable community plan link.
- Voice input for low-literacy users.
- Map overlay of city flood zones.

## 9. Google Cloud architecture

```
Browser ──HTTPS──▶ Cloud Run (FastAPI + static frontend)
  │ Firebase Auth (Email/Password) → ID token
  │ every /api call: Authorization: Bearer <ID token>
  ▼
Cloud Run backend ──verify token──▶ Firebase Admin SDK (Auth)
  │ ADC (runtime SA)                ├── Cloud Firestore  (plans, kits, profiles)
  ▼                                 └── Gemini (google-genai)
Gemini: response_schema · Google Search grounding · multimodal image input
Secrets: Gemini API key in Secret Manager (never in repo)
Region: asia-south1 (Mumbai — where the monsoon actually is)
```

## 10. Testing strategy (`pytest`)

- **`test_kit_core.py`** (pure, no mocks — the crown jewel): happy pack within budget; infeasible budget → everything overflows + flag; boundary (exact budget); empty item list; zero-guard (0 budget rejected upstream, packer never divides by zero); essentials packed before luxuries; overflow never silently dropped; readiness score monotonicity; quantity scaling by family size.
- **`test_schemas.py`**: valid parse; oversized/absurd input rejected; enum enforcement; round-trip.
- **`test_orchestrator.py`** (FakeGemini): plan returns structured sections + grounded citations; agentic loop retries exactly once on budget failure (`fake.calls == 2`); grounding failure → graceful empty citations; **injection test: "ignore previous instructions" in notes → fenced `<<<USER_DATA` in prompt**; language propagated into prompt.
- **`test_security.py`**: missing token → 401; wrong scheme → 401; invalid token → 401; valid token → identity mapped; dev bypass → demo user.
- **`test_api.py`** (TestClient + dependency overrides): healthz 200; config 200; plan returns all artifacts; kit returns packed/overflow/score; protected route without token → 401; bad upload MIME → 415.
- All cloud clients dependency-injected → suite runs with **no cloud credentials**.

## 11. Security

- **No secrets in code/repo/client.** Gemini key in Secret Manager. Firebase web config is non-secret by design.
- **Auth server-side:** Firebase ID token verified via Admin SDK on every protected route.
- **Least privilege:** runtime SA limited to `roles/datastore.user` + `roles/secretmanager.secretAccessor`.
- **Firestore rules:** `request.auth.uid == uid` only.
- **Input validation:** Pydantic size caps on every string, bounds on every number; image MIME allowlist (415), 6 MB cap (413), empty upload (400).
- **Prompt-injection mitigation:** all user free text inserted as `<<<USER_DATA … USER_DATA>>>` labeled untrusted; every system prompt ends with an explicit SECURITY instruction; `response_schema` constrains output shape.
- **Grounding = anti-hallucination:** alerts/advisories cite real sources; grounded prompts instruct "never invent alerts — say none found".
- **Multimodal honesty:** hazard prompts instruct "if not confident, set identified=false — never fabricate hazards".
- **Transport/CORS:** HTTPS on Cloud Run; CORS configurable via env; `.env` git-ignored.

## 12. Lessons applied from previous rounds

| Past issue | Fix baked in |
|---|---|
| Bare `/healthz` intercepted by Google's frontend | `/api/healthz` from the start |
| Firebase Auth providers not enabled (`CONFIGURATION_NOT_FOUND`) | Providers enabled in console before build |
| Billing not linked | Verified before deploy |
| Key pasted in chat/repo | Secret Manager only; rotate post-event |
| Model ID uncertainty (real 503 in rehearsal) | Model id pinned via env, verified live at deploy, automatic fallback model retry in the client |

## 13. How this maps to the judging criteria

| Criterion | How we win it |
|---|---|
| **Problem-statement alignment** | All 8 required capabilities are explicit P0 features (§5) using the statement's exact vocabulary; the 📸 Hazard Scanner is the memorable on-theme wow. |
| **Code quality** | Layered, dependency-injected modules; typed Pydantic models; LLM-vs-deterministic split; lazy cloud imports; bounded agentic loop with honest flags. |
| **Security** | §11 — implemented, not just claimed, with tests (401s, 415/413, injection fencing). |
| **Testing** | ~30 credential-free cases: pure core + mocked-LLM orchestration + auth + API smoke. |
| **Google Cloud alignment** | Cloud Run (asia-south1) + Gemini + Search grounding + Firebase Auth + Firestore + Secret Manager; one-command source deploy. |

## 14. Success metrics (demo-day)

- Full flow (sign-in → plan → kit → scan → alerts) completes in < ~15 s of model time per step.
- Alerts/advisory responses include ≥1 real citation when grounding is available.
- `pytest`: all green, zero cloud credentials.
- Live Cloud Run URL healthy at submission.

## 15. Open questions

- Should alerts auto-refresh on an interval in the UI? (Owner: frontend — deferred, manual refresh ships.)
- Vertex AI vs Developer API key for Gemini? (Owner: infra — Developer API key via Secret Manager ships; Vertex is a config flip.)
- Persist hazard-scan images? (Owner: privacy — v1 stores only the text report, never the photo.)

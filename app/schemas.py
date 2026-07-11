"""Pydantic models.

Two deliberate families:

1. LLM-OUTPUT models (used as Gemini response_schema):
   - required fields only — NO Optional, NO defaults (reliable structured output)
   - use Literal[...] for enums
   - these double as API response shapes

2. INPUT / app models:
   - defaults + validators + SIZE CAPS on every free-text field
   - caps are a security feature (prompt-injection surface + abuse control)
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

SUPPORTED_LANGUAGES = [
    "English", "Hindi", "Marathi", "Bengali", "Tamil", "Telugu",
    "Kannada", "Malayalam", "Gujarati", "Odia", "Punjabi", "Urdu",
]

ESSENTIAL_CATEGORIES = {"water", "food", "medical", "documents"}

KitCategory = Literal[
    "water", "food", "medical", "documents", "power_light",
    "hygiene", "baby", "elderly", "pet", "tools",
]


# ---------- app / identity ----------
class User(BaseModel):
    uid: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    photo_url: Optional[str] = None
    provider: Optional[str] = None


# ---------- INPUT models (validated, capped) ----------
class HouseholdProfile(BaseModel):
    uid: str = ""
    city: str = Field(default="", max_length=120)
    adults: int = Field(default=2, ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    infants: int = Field(default=0, ge=0, le=10)
    elderly: int = Field(default=0, ge=0, le=20)
    pets: int = Field(default=0, ge=0, le=20)
    home_type: Literal["apartment", "independent_house", "ground_floor", "basement_level"] = "apartment"
    language: str = Field(default="English", max_length=40)


class PlanRequest(BaseModel):
    city: str = Field(min_length=2, max_length=120)
    adults: int = Field(default=2, ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    infants: int = Field(default=0, ge=0, le=10)
    elderly: int = Field(default=0, ge=0, le=20)
    pets: int = Field(default=0, ge=0, le=20)
    home_type: Literal["apartment", "independent_house", "ground_floor", "basement_level"] = "apartment"
    special_needs: str = Field(default="", max_length=500)  # untrusted free text
    language: str = Field(default="English", max_length=40)


class KitRequest(BaseModel):
    city: str = Field(min_length=2, max_length=120)
    adults: int = Field(default=2, ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    infants: int = Field(default=0, ge=0, le=10)
    elderly: int = Field(default=0, ge=0, le=20)
    pets: int = Field(default=0, ge=0, le=20)
    budget_inr: int = Field(ge=500, le=200000)
    notes: str = Field(default="", max_length=500)  # untrusted free text (diet, meds…)
    language: str = Field(default="English", max_length=40)


class AlertsRequest(BaseModel):
    city: str = Field(min_length=2, max_length=120)
    language: str = Field(default="English", max_length=40)


class AdvisoryRequest(BaseModel):
    origin: str = Field(min_length=2, max_length=120)
    destination: str = Field(min_length=2, max_length=120)
    travel_date: str = Field(default="today", max_length=40)
    mode: Literal["road", "rail", "air", "any"] = "any"
    language: str = Field(default="English", max_length=40)


# ---------- LLM-OUTPUT models (Gemini response_schema) ----------
class PlanAction(BaseModel):
    action: str
    why_for_you: str  # personalized rationale tied to this household
    priority: Literal["high", "medium", "low"]


class PlanSection(BaseModel):
    phase: Literal["before", "during", "after"]
    title: str
    actions: List[PlanAction]


class PreparednessPlan(BaseModel):
    summary: str
    sections: List[PlanSection]


class KitItem(BaseModel):
    name: str
    category: KitCategory
    quantity: int
    unit_cost_inr: int
    priority: int  # 1 (nice to have) … 5 (critical)
    why_for_you: str


class KitSuggestion(BaseModel):
    items: List[KitItem]


class Hazard(BaseModel):
    label: str
    severity: Literal["low", "moderate", "severe"]
    why_risky: str
    fix: str


class HazardReport(BaseModel):
    identified: bool  # False when nothing recognizable — never fabricate
    hazards: List[Hazard]
    overall_assessment: str


# ---------- API response envelopes (assembled server-side) ----------
class Citation(BaseModel):
    title: str = ""
    uri: str


class GroundedBrief(BaseModel):
    text: str
    citations: List[Citation]


class PlanResponse(BaseModel):
    plan: PreparednessPlan
    weather_brief: GroundedBrief


class PackedKit(BaseModel):
    packed: List[KitItem]
    overflow: List[KitItem]  # surfaced, never silently dropped
    total_cost_inr: int
    budget_inr: int
    within_budget: bool
    essential_coverage: List[str]  # essential categories covered
    missing_essentials: List[str]
    readiness_score: int  # 0–100, deterministic
    refinement_rounds: int  # agentic loop rounds actually used


class AlertsResponse(BaseModel):
    brief: GroundedBrief


class AdvisoryResponse(BaseModel):
    brief: GroundedBrief

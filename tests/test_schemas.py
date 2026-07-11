"""Input validation is a security feature: size caps + bounds on everything."""
import pytest
from pydantic import ValidationError

from app.schemas import (
    HazardReport,
    KitRequest,
    PackedKit,
    PlanRequest,
    PreparednessPlan,
)
from tests.factories import make_hazard_report, make_plan


def test_plan_request_parses_with_defaults():
    req = PlanRequest(city="Mumbai")
    assert req.adults == 2 and req.language == "English" and req.home_type == "apartment"


def test_plan_request_rejects_oversized_free_text():
    with pytest.raises(ValidationError):
        PlanRequest(city="Mumbai", special_needs="x" * 501)


def test_kit_request_rejects_absurd_budget_and_members():
    with pytest.raises(ValidationError):
        KitRequest(city="Pune", budget_inr=0)  # below the ₹500 floor
    with pytest.raises(ValidationError):
        KitRequest(city="Pune", budget_inr=3000, adults=0)  # 0-member household


def test_plan_section_phase_enum_enforced():
    plan = make_plan()
    assert {s.phase for s in plan.sections} == {"before", "during", "after"}
    with pytest.raises(ValidationError):
        PreparednessPlan.model_validate(
            {"summary": "s", "sections": [{"phase": "someday", "title": "t", "actions": []}]}
        )


def test_llm_output_round_trip():
    report = make_hazard_report()
    again = HazardReport.model_validate(report.model_dump())
    assert again == report


def test_packed_kit_envelope_round_trip():
    kit = PackedKit(
        packed=[], overflow=[], total_cost_inr=0, budget_inr=1000,
        within_budget=False, essential_coverage=[], missing_essentials=["water"],
        readiness_score=0, refinement_rounds=1,
    )
    assert PackedKit.model_validate(kit.model_dump()) == kit

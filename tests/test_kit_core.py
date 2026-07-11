"""Pure deterministic core — no mocks, no cloud, the crown jewel of the suite."""
from app.kit_core import (
    covered_essentials,
    evaluate_suggestion,
    item_cost,
    missing_essentials,
    pack_kit,
    readiness_score,
)
from tests.factories import make_affordable_suggestion, make_expensive_suggestion, make_kit_item


def test_happy_pack_within_budget():
    items = make_affordable_suggestion().items
    packed, overflow, spent = pack_kit(items, 3000)
    assert packed and not overflow
    assert spent == sum(item_cost(i) for i in items)
    assert spent <= 3000


def test_infeasible_budget_everything_overflows_nothing_lost():
    items = make_expensive_suggestion().items
    packed, overflow, spent = pack_kit(items, 500)
    assert packed == []
    assert len(overflow) == len(items)  # surfaced, never silently dropped
    assert spent == 0


def test_boundary_exact_budget_fits():
    items = [make_kit_item("Water", "water", 1, 1000, 5)]
    packed, overflow, spent = pack_kit(items, 1000)
    assert len(packed) == 1 and not overflow and spent == 1000


def test_empty_item_list():
    packed, overflow, spent = pack_kit([], 5000)
    assert packed == [] and overflow == [] and spent == 0


def test_zero_budget_guard():
    items = make_affordable_suggestion().items
    packed, overflow, spent = pack_kit(items, 0)
    assert packed == [] and len(overflow) == len(items) and spent == 0


def test_zero_cost_item_is_surfaced_not_packed():
    items = [make_kit_item("Suspicious freebie", "tools", 1, 0, 3)]
    packed, overflow, _ = pack_kit(items, 1000)
    assert packed == [] and len(overflow) == 1


def test_essentials_packed_before_higher_density_luxuries():
    essential = make_kit_item("First-aid kit", "medical", 1, 900, 3)
    luxury = make_kit_item("Power bank", "power_light", 1, 300, 5)  # better density
    packed, overflow, _ = pack_kit([luxury, essential], 1000)
    assert [i.name for i in packed] == ["First-aid kit"]
    assert [i.name for i in overflow] == ["Power bank"]


def test_partial_pack_keeps_totals_conserved():
    items = make_expensive_suggestion().items
    packed, overflow, spent = pack_kit(items, 20000)
    assert len(packed) + len(overflow) == len(items)
    assert spent == sum(item_cost(i) for i in packed)
    assert spent <= 20000


def test_essential_coverage_helpers():
    items = make_affordable_suggestion().items
    packed, _, _ = pack_kit(items, 3000)
    assert covered_essentials(packed) == ["documents", "food", "medical", "water"]
    assert missing_essentials(packed) == []


def test_readiness_score_bounds_and_monotonicity():
    items = make_affordable_suggestion().items
    full, _, _ = pack_kit(items, 100000)
    partial, _, _ = pack_kit(items, 800)
    assert readiness_score([], items) == 0
    assert 0 < readiness_score(partial, items) <= readiness_score(full, items) <= 100


def test_evaluate_suggestion_accepts_affordable():
    ok, feedback = evaluate_suggestion(make_affordable_suggestion().items, 3000)
    assert ok and feedback == ""


def test_evaluate_suggestion_rejects_with_concrete_numbers():
    items = make_expensive_suggestion().items
    ok, feedback = evaluate_suggestion(items, 3000)
    assert not ok
    total = sum(item_cost(i) for i in items)
    assert f"INR {total}" in feedback  # concrete totals, not vibes
    assert "INR 3000" in feedback
    assert "water" in feedback or "medical" in feedback

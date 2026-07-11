"""Deterministic emergency-kit engine (pure Python, no I/O, fully unit-tested).

The split that makes the app trustworthy: Gemini SUGGESTS kit items (names,
costs, quantities, priorities suited to this household); this module DECIDES —
what fits the budget, what overflows, what's missing, and the readiness score.
The LLM never does arithmetic; nothing a user needs is silently dropped.
"""
from typing import Iterable, List, Tuple

from .schemas import ESSENTIAL_CATEGORIES, KitItem

# Readiness score weights: covering the 4 essential categories dominates.
_ESSENTIAL_WEIGHT = 60
_PRIORITY_WEIGHT = 40


def item_cost(item: KitItem) -> int:
    return item.unit_cost_inr * item.quantity


def _value_density(item: KitItem) -> float:
    """Priority per rupee — what to pack first when money is tight."""
    return item.priority / max(item_cost(item), 1)


def pack_kit(items: Iterable[KitItem], budget_inr: int) -> Tuple[List[KitItem], List[KitItem], int]:
    """Greedy pack by priority-per-rupee, essentials strictly first.

    Returns (packed, overflow, total_cost). Overflow is every suggested item
    that did not fit — surfaced to the user, never silently dropped.
    """
    if budget_inr <= 0:
        all_items = list(items)
        return [], all_items, 0

    essentials = [i for i in items if i.category in ESSENTIAL_CATEGORIES]
    others = [i for i in items if i.category not in ESSENTIAL_CATEGORIES]

    packed: List[KitItem] = []
    overflow: List[KitItem] = []
    spent = 0
    ordered = sorted(essentials, key=_value_density, reverse=True) + sorted(
        others, key=_value_density, reverse=True
    )
    for item in ordered:
        cost = item_cost(item)
        if cost <= 0:
            overflow.append(item)  # free/absurd pricing is suspect — surface it
            continue
        if spent + cost <= budget_inr:
            packed.append(item)
            spent += cost
        else:
            overflow.append(item)
    return packed, overflow, spent


def covered_essentials(packed: Iterable[KitItem]) -> List[str]:
    return sorted({i.category for i in packed} & ESSENTIAL_CATEGORIES)


def missing_essentials(packed: Iterable[KitItem]) -> List[str]:
    return sorted(ESSENTIAL_CATEGORIES - {i.category for i in packed})


def readiness_score(packed: List[KitItem], all_suggested: List[KitItem]) -> int:
    """0–100. Essential-category coverage dominates (60), then how much of the
    total suggested priority mass actually fit the budget (40). Deterministic
    and monotonic: packing more never lowers the score."""
    if not packed:
        return 0
    essential_part = _ESSENTIAL_WEIGHT * len(covered_essentials(packed)) / len(ESSENTIAL_CATEGORIES)
    total_priority = sum(i.priority for i in all_suggested)
    packed_priority = sum(i.priority for i in packed)
    priority_part = _PRIORITY_WEIGHT * packed_priority / max(total_priority, 1)
    return round(essential_part + priority_part)


def evaluate_suggestion(items: List[KitItem], budget_inr: int) -> Tuple[bool, str]:
    """Deterministic evaluator for the agentic loop.

    Returns (acceptable, feedback). Not acceptable when packing the suggestion
    leaves an essential category uncovered — the feedback gives the LLM CONCRETE
    numbers to fix, not vibes.
    """
    packed, _overflow, spent = pack_kit(items, budget_inr)
    missing = missing_essentials(packed)
    if not missing:
        return True, ""
    total = sum(item_cost(i) for i in items)
    over_by = max(total - budget_inr, 0)
    feedback = (
        f"Your suggestion totals INR {total} against a budget of INR {budget_inr} "
        f"(over by INR {over_by}). After priority packing, these ESSENTIAL categories "
        f"are still uncovered: {', '.join(missing)}. Propose a revised list that fits "
        f"INR {budget_inr}: reduce quantities, pick cheaper alternatives, and make sure "
        f"every essential category (water, food, medical, documents) has at least one "
        f"affordable item."
    )
    return False, feedback

"""Test builders and in-memory fakes (no cloud dependencies).

* make_*() builders return realistic canned Pydantic objects.
* FakeGemini dispatches on response_schema type and RECORDS every call
  (calls / systems / contents_log) so tests can assert on prompts —
  e.g. that untrusted user text is fenced inside <<<USER_DATA ... USER_DATA>>>.
* FakeRepo is a dict-backed stand-in for Firestore.
* Inject both via app.dependency_overrides[get_gemini_client / get_repository].
"""
from typing import List, Optional

from app.schemas import (
    Hazard,
    HazardReport,
    KitItem,
    KitSuggestion,
    PlanAction,
    PlanSection,
    PreparednessPlan,
)


def make_kit_item(
    name="Drinking water (20L can)", category="water", quantity=2,
    unit_cost_inr=100, priority=5, why="3 days of water for your family of 4.",
) -> KitItem:
    return KitItem(
        name=name, category=category, quantity=quantity,
        unit_cost_inr=unit_cost_inr, priority=priority, why_for_you=why,
    )


def make_affordable_suggestion() -> KitSuggestion:
    """Fits comfortably in a ₹3000 budget and covers all essentials."""
    return KitSuggestion(items=[
        make_kit_item("Drinking water (20L can)", "water", 2, 100, 5),
        make_kit_item("Ready-to-eat meals", "food", 6, 80, 5),
        make_kit_item("First-aid kit", "medical", 1, 450, 5),
        make_kit_item("Waterproof document pouch", "documents", 1, 150, 4),
        make_kit_item("LED torch + batteries", "power_light", 2, 200, 4),
        make_kit_item("ORS sachets", "medical", 10, 15, 4),
    ])


def make_expensive_suggestion() -> KitSuggestion:
    """Blows any reasonable budget — essentials can't all be packed."""
    return KitSuggestion(items=[
        make_kit_item("Premium water purifier", "water", 1, 15000, 5),
        make_kit_item("Freeze-dried gourmet rations", "food", 10, 900, 5),
        make_kit_item("Full trauma medical kit", "medical", 1, 12000, 5),
        make_kit_item("Fireproof document safe", "documents", 1, 8000, 4),
    ])


def make_plan() -> PreparednessPlan:
    def act(a, w, p="high"):
        return PlanAction(action=a, why_for_you=w, priority=p)

    return PreparednessPlan(
        summary="A monsoon plan tuned for your ground-floor Mumbai home with an infant.",
        sections=[
            PlanSection(phase="before", title="Before the rains", actions=[
                act("Move documents and valuables above knee height",
                    "Ground-floor homes in your area flood first."),
                act("Stock 3 days of infant formula and water",
                    "You have an infant; supplies vanish during flood warnings."),
            ]),
            PlanSection(phase="during", title="During heavy rain", actions=[
                act("Switch off mains power if water enters",
                    "Your home is at street level — electrocution risk is real."),
            ]),
            PlanSection(phase="after", title="After the water recedes", actions=[
                act("Boil or purify all drinking water",
                    "Post-flood water contamination causes most illness.", "medium"),
            ]),
        ],
    )


def make_hazard_report(identified=True) -> HazardReport:
    if not identified:
        return HazardReport(
            identified=False, hazards=[],
            overall_assessment="No monsoon-specific hazards recognizable in this photo.",
        )
    return HazardReport(
        identified=True,
        hazards=[
            Hazard(label="Clogged storm drain", severity="severe",
                   why_risky="Blocked drains cause street flooding within minutes of heavy rain.",
                   fix="Clear debris now and ask your ward office for a pre-monsoon desilting."),
            Hazard(label="Exposed junction-box wiring", severity="moderate",
                   why_risky="Rainwater on live wiring risks shock and fire.",
                   fix="Get an electrician to seal the box with an IP-rated cover."),
        ],
        overall_assessment="Two actionable hazards found; fix the drain before the first spell.",
    )


class FakeGemini:
    """Dispatches on response_schema; records every call for prompt assertions."""

    def __init__(
        self,
        plan: Optional[PreparednessPlan] = None,
        kit_rounds: Optional[List[KitSuggestion]] = None,
        hazard: Optional[HazardReport] = None,
        grounded_text: str = "No severe weather warnings currently active.",
        citations: Optional[List[dict]] = None,
        grounded_raises: bool = False,
    ):
        self.plan = plan or make_plan()
        self.kit_rounds = list(kit_rounds) if kit_rounds else [make_affordable_suggestion()]
        self.hazard = hazard or make_hazard_report()
        self.grounded_text = grounded_text
        self.citations = citations if citations is not None else [
            {"title": "IMD district forecast", "uri": "https://mausam.imd.gov.in/example"}
        ]
        self.grounded_raises = grounded_raises
        self.calls = 0
        self.grounded_calls = 0
        self.systems: List[str] = []
        self.contents_log: List[list] = []

    def image_part(self, data: bytes, mime_type: str):
        return {"__image__": len(data), "mime": mime_type}

    def generate_structured(self, *, system_instruction, contents, response_schema, temperature=0.6):
        self.calls += 1
        self.systems.append(system_instruction)
        self.contents_log.append(contents)
        from app.schemas import HazardReport as HR
        from app.schemas import KitSuggestion as KS
        from app.schemas import PreparednessPlan as PP

        if response_schema is PP:
            return self.plan
        if response_schema is KS:
            return self.kit_rounds.pop(0) if len(self.kit_rounds) > 1 else self.kit_rounds[0]
        if response_schema is HR:
            return self.hazard
        raise AssertionError(f"Unexpected schema {response_schema}")

    def generate_grounded(self, *, system_instruction, contents, temperature=0.4):
        self.grounded_calls += 1
        self.systems.append(system_instruction)
        self.contents_log.append(contents)
        if self.grounded_raises:
            raise RuntimeError("grounding unavailable")
        return {"text": self.grounded_text, "citations": self.citations}

    def generate_text(self, *, system_instruction, contents, temperature=0.8):
        return "some text"


class FakeRepo:
    def __init__(self):
        self.profiles = {}
        self.records = {}

    def get_profile(self, uid):
        return self.profiles.get(uid)

    def upsert_profile(self, profile):
        self.profiles[profile.uid] = profile.model_dump()

    def save_record(self, uid, label, payload):
        self.records.setdefault(uid, []).append({"label": label, "payload": payload})
        return "record-id"

    def list_records(self, uid, limit=20):
        return self.records.get(uid, [])

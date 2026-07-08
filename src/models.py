"""Core data model for prospect-signal.

The pipeline moves a `Company` (raw seed data) through three pure stages:

    enrich  -> Signals       (derived facts, incl. one optional live signal)
    score   -> ScoreResult   (transparent weighted rubric + reasons)
    generate-> str           (a tailored first-touch email)

`Lead` bundles all of the above for the dashboard.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal


def _slugify(name: str) -> str:
    """`"Scale AI"` -> `"scale-ai"`. Stable, filesystem-safe, no collisions in the seed set."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "company"


@dataclass(frozen=True)
class Company:
    """Raw ICP seed data for a single target account.

    Fields map one-to-one onto `data/companies.json`. This object is immutable;
    every derived fact lives on `Signals`, keeping the raw inputs auditable.
    """

    name: str
    stage: str
    funded_last_12mo: bool
    eng_headcount: int
    oncall_tools: list[str]
    stack: list[str]
    status_page_url: str | None
    recent_incidents: int
    persona: str

    @property
    def slug(self) -> str:
        return _slugify(self.name)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Company":
        """Build a `Company` from a JSON record, validating required fields and types."""
        required = {
            "name": str,
            "stage": str,
            "funded_last_12mo": bool,
            "eng_headcount": int,
            "oncall_tools": list,
            "stack": list,
            "recent_incidents": int,
            "persona": str,
        }
        for key, expected in required.items():
            if key not in raw:
                raise ValueError(f"company record missing required field: {key!r}")
            if not isinstance(raw[key], expected):
                raise ValueError(
                    f"field {key!r} on {raw.get('name', '?')!r} should be {expected.__name__}, "
                    f"got {type(raw[key]).__name__}"
                )
        return cls(
            name=raw["name"],
            stage=raw["stage"],
            funded_last_12mo=raw["funded_last_12mo"],
            eng_headcount=raw["eng_headcount"],
            oncall_tools=list(raw["oncall_tools"]),
            stack=list(raw["stack"]),
            status_page_url=raw.get("status_page_url"),
            recent_incidents=raw["recent_incidents"],
            persona=raw["persona"],
        )


@dataclass(frozen=True)
class Signals:
    """Derived facts produced by the enrichment layer.

    Everything here is computed from a `Company` (plus one optional live fetch).
    Scoring reads these rather than re-deriving thresholds, so the two layers
    stay decoupled and independently testable.
    """

    incident_tools: list[str]      # on-call tools that signal budget + admitted pain
    modern_infra: list[str]        # stack markers (k8s / microservices / multi-cloud)
    incident_count: int            # resolved incident count (live if available, else seed)
    incident_count_source: Literal["live", "seed"]


@dataclass(frozen=True)
class ScoreReason:
    """One rubric rule that fired: the points it added and why, in plain language."""

    points: int
    text: str


@dataclass(frozen=True)
class ScoreResult:
    """A company's propensity score (0-100) and the ordered reasons behind it."""

    score: int
    reasons: list[ScoreReason]


@dataclass
class Lead:
    """A fully-processed account: raw company + every derived layer + its email."""

    company: Company
    signals: Signals
    score: ScoreResult
    email: str = ""

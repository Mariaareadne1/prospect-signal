"""Scoring engine: a transparent weighted rubric.

Each rule inspects the company's real signals, and when it fires it records both
the points it adds and a plain-language reason that names those signals. The
reasons travel with the score to the dashboard — the number is only as useful as
the "why" behind it.

Weights (see README for the rationale):

    incident tooling in use ........ +30
    engineering headcount > 200 .... +20
    funded in last 12 months ....... +15
    modern distributed stack ....... +15
    3+ recent public incidents ..... +20

Total is capped at 100.
"""

from __future__ import annotations

from .models import Company, ScoreReason, ScoreResult, Signals

# Tunable weights, kept together so the rubric is easy to read and adjust.
POINTS_INCIDENT_TOOLING = 30
POINTS_LARGE_ENG_ORG = 20
POINTS_RECENTLY_FUNDED = 15
POINTS_MODERN_INFRA = 15
POINTS_FREQUENT_INCIDENTS = 20

ENG_HEADCOUNT_THRESHOLD = 200
INCIDENT_THRESHOLD = 3
SCORE_CAP = 100


def score_company(company: Company, signals: Signals) -> ScoreResult:
    """Apply the rubric to one company. Returns its score and the reasons that fired."""
    reasons: list[ScoreReason] = []

    if signals.incident_tools:
        tools = ", ".join(signals.incident_tools)
        reasons.append(
            ScoreReason(
                POINTS_INCIDENT_TOOLING,
                f"Already pays for incident tooling ({tools}) — budget plus admitted pain",
            )
        )

    if company.eng_headcount > ENG_HEADCOUNT_THRESHOLD:
        reasons.append(
            ScoreReason(
                POINTS_LARGE_ENG_ORG,
                f"Engineering org of ~{company.eng_headcount} — on-call load is a real, recurring cost",
            )
        )

    if company.funded_last_12mo:
        reasons.append(
            ScoreReason(
                POINTS_RECENTLY_FUNDED,
                f"Raised in the last 12 months ({company.stage}) — fresh budget, pressure to keep "
                "reliability ahead of growth",
            )
        )

    if signals.modern_infra:
        infra = ", ".join(signals.modern_infra)
        reasons.append(
            ScoreReason(
                POINTS_MODERN_INFRA,
                f"Distributed stack ({infra}) — more failure modes, noisier on-call",
            )
        )

    if signals.incident_count >= INCIDENT_THRESHOLD:
        origin = "live status page" if signals.incident_count_source == "live" else "public record"
        reasons.append(
            ScoreReason(
                POINTS_FREQUENT_INCIDENTS,
                f"{signals.incident_count} recent public incidents ({origin}) — visible, admitted "
                "reliability pain",
            )
        )

    # Present strongest signals first; cap the total.
    reasons.sort(key=lambda r: r.points, reverse=True)
    total = min(SCORE_CAP, sum(r.points for r in reasons))
    return ScoreResult(score=total, reasons=reasons)


def score_all(companies: list[Company], signals: list[Signals]) -> list[ScoreResult]:
    """Score a batch, pairing each company with its signals (same order)."""
    if len(companies) != len(signals):
        raise ValueError("companies and signals must be the same length and order")
    return [score_company(c, s) for c, s in zip(companies, signals)]

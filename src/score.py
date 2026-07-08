"""Scoring engine: a transparent weighted rubric.

Each rule adds points and records a human-readable reason. The reasons are as
important as the number, so they travel with the score all the way to the UI.
"""

from __future__ import annotations

from .models import Company, ScoreResult, Signals

# Implemented in Step 4.

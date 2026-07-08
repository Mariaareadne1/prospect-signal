"""Outreach generator: a signal-aware first-touch email per company.

Uses the Anthropic API (claude-fable-5, falling back to claude-opus-4-8). The
API key is read from the ANTHROPIC_API_KEY environment variable and never
committed. Results are cached so re-runs don't re-call the API for unchanged
companies.
"""

from __future__ import annotations

from .models import Company, ScoreResult, Signals

# Implemented in Step 5.

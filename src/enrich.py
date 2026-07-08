"""Enrichment layer: derive SDR-relevant signals from raw seed data.

Pure and testable. The one impure edge — an optional live status-page fetch —
is isolated in `fetch_live_incident_count` and can never break the run.
"""

from __future__ import annotations

from .models import Company, Signals

# Implemented in Step 3.

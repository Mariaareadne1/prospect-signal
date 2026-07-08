"""Enrichment layer: derive SDR-relevant signals from raw seed data.

Everything here is a pure function of a `Company` except one isolated edge —
`fetch_live_incident_count`, which reaches out to a public status page. That
call is wrapped so a network failure, timeout, or unparseable page can never
break the run: it returns `None` and the caller falls back to the seeded count.
"""

from __future__ import annotations

import re
import urllib.request

from .models import Company, Signals

# On-call tools that signal an existing incident-tooling budget (and admitted pain).
INCIDENT_TOOLING = {"pagerduty", "opsgenie", "datadog", "splunk"}

# Stack markers for distributed systems — more failure modes, noisier on-call.
MODERN_INFRA = {"kubernetes", "microservices", "multi-cloud"}

# Atlassian Statuspage (which most of these companies use) tags each past
# incident in the "Past Incidents" section with this class. Counting them is a
# reasonable proxy for "recent public incidents".
_INCIDENT_MARKER = re.compile(r'class="[^"]*\bincident-title\b', re.IGNORECASE)

_USER_AGENT = "prospect-signal/1.0 (+https://github.com/Mariaareadne1/prospect-signal)"
_MAX_BYTES = 500_000


def incident_tools(company: Company) -> list[str]:
    """The company's on-call tools that count as incident tooling, order preserved."""
    return [t for t in company.oncall_tools if t.lower() in INCIDENT_TOOLING]


def modern_infra_markers(company: Company) -> list[str]:
    """The stack entries that mark modern distributed infrastructure, order preserved."""
    return [s for s in company.stack if s.lower() in MODERN_INFRA]


def count_incidents_in_html(html: str) -> int | None:
    """Count recent incidents in a status page's HTML.

    Returns the count when the page uses a recognizable incident layout, or
    `None` when nothing recognizable is found — so the caller falls back to the
    seeded number rather than trusting a misparsed zero.
    """
    matches = _INCIDENT_MARKER.findall(html)
    return len(matches) if matches else None


def fetch_live_incident_count(url: str, timeout: float = 5.0) -> int | None:
    """Fetch a status page and count recent incidents. Never raises.

    Any failure — DNS, connection, timeout, non-200, decode error, or an
    unrecognized page layout — resolves to `None`, signaling the caller to fall
    back to the seeded incident count.
    """
    try:
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            html = response.read(_MAX_BYTES).decode("utf-8", errors="replace")
    except Exception:
        return None
    return count_incidents_in_html(html)


def enrich(company: Company, live: bool = True, timeout: float = 5.0) -> Signals:
    """Derive `Signals` for one company.

    With `live=True` (the default) and a status-page URL present, attempt a live
    incident count and use it if it succeeds; otherwise use the seeded count.
    The rest of the derivation is pure and deterministic.
    """
    incident_count = company.recent_incidents
    source: str = "seed"

    if live and company.status_page_url:
        live_count = fetch_live_incident_count(company.status_page_url, timeout)
        if live_count is not None:
            incident_count = live_count
            source = "live"

    return Signals(
        incident_tools=incident_tools(company),
        modern_infra=modern_infra_markers(company),
        incident_count=incident_count,
        incident_count_source=source,  # type: ignore[arg-type]
    )


def enrich_all(companies: list[Company], live: bool = True, timeout: float = 5.0) -> list[Signals]:
    """Enrich a batch of companies, preserving order."""
    return [enrich(c, live=live, timeout=timeout) for c in companies]

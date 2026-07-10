"""Enrichment layer: derive SDR-relevant signals from raw seed data.

Everything here is a pure function of a `Company` except one isolated edge —
`_fetch_status_html`, which reaches out to a public status page. That call is
wrapped so a network failure, timeout, or unparseable page can never break the
run: it returns `None` and the caller falls back to seeded values.

Two live signals come off the status page when it's reachable: the recent
incident count and the recency of the most recent dated incident
(`days_since_last_incident`). Recency is only ever derived from a real date on
the page; when no date can be parsed it stays `None` rather than being invented.
"""

from __future__ import annotations

import re
import urllib.request
from datetime import date

from .models import Company, Signals

# On-call tools that signal an existing incident-tooling budget (and admitted pain).
INCIDENT_TOOLING = {"pagerduty", "opsgenie", "datadog", "splunk"}

# Stack markers for distributed systems — more failure modes, noisier on-call.
MODERN_INFRA = {"kubernetes", "microservices", "multi-cloud"}

# Atlassian Statuspage (which most of these companies use) tags each past
# incident in the "Past Incidents" section with this class. Counting them is a
# reasonable proxy for "recent public incidents".
_INCIDENT_MARKER = re.compile(r'class="[^"]*\bincident-title\b', re.IGNORECASE)

# Dates on a status page, used to date the most recent incident. We accept both
# ISO (2026-07-03) and "Mon DD, YYYY" (Jul 3, 2026) forms.
# Lookarounds (not \b): a trailing "T" in an ISO datetime is a word char, so \b
# would fail to close the match on "2026-07-06T10:00:00Z".
_ISO_DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_TEXT_DATE = re.compile(
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\b",
    re.IGNORECASE,
)
_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

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


def parse_latest_incident_date(html: str, today: date) -> date | None:
    """The most recent dated incident on a status page, or `None` if undatable.

    Collects ISO and "Mon DD, YYYY" dates, discards anything in the future
    (scheduled maintenance), and returns the latest remaining date. Pure.
    """
    candidates: list[date] = []

    for year, month, day in _ISO_DATE.findall(html):
        try:
            parsed = date(int(year), int(month), int(day))
        except ValueError:
            continue
        if parsed <= today:
            candidates.append(parsed)

    for month_name, day, year in _TEXT_DATE.findall(html):
        month = _MONTHS.get(month_name.lower()[:3])
        if month is None:
            continue
        try:
            parsed = date(int(year), month, int(day))
        except ValueError:
            continue
        if parsed <= today:
            candidates.append(parsed)

    return max(candidates) if candidates else None


def _fetch_status_html(url: str, timeout: float = 5.0) -> str | None:
    """Fetch a status page's HTML. Never raises — any failure resolves to `None`."""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(_MAX_BYTES).decode("utf-8", errors="replace")
    except Exception:
        return None


def enrich(
    company: Company,
    live: bool = True,
    timeout: float = 5.0,
    today: date | None = None,
) -> Signals:
    """Derive `Signals` for one company.

    With `live=True` (the default) and a status-page URL present, fetch the page
    once and read two signals off it: the incident count and the date of the most
    recent incident (turned into `days_since_last_incident`). Either falls back
    gracefully — the count to the seeded number, the recency to `None`. The rest
    of the derivation is pure and deterministic.
    """
    today = today or date.today()
    incident_count = company.recent_incidents
    source: str = "seed"
    days_since: int | None = None

    if live and company.status_page_url:
        html = _fetch_status_html(company.status_page_url, timeout)
        if html:
            live_count = count_incidents_in_html(html)
            if live_count is not None:
                incident_count = live_count
                source = "live"
                # Only date the recency when we actually recognized incidents.
                latest = parse_latest_incident_date(html, today)
                if latest is not None:
                    days_since = max(0, (today - latest).days)

    return Signals(
        incident_tools=incident_tools(company),
        modern_infra=modern_infra_markers(company),
        incident_count=incident_count,
        incident_count_source=source,  # type: ignore[arg-type]
        days_since_last_incident=days_since,
    )


def enrich_all(
    companies: list[Company],
    live: bool = True,
    timeout: float = 5.0,
    today: date | None = None,
) -> list[Signals]:
    """Enrich a batch of companies, preserving order."""
    return [enrich(c, live=live, timeout=timeout, today=today) for c in companies]

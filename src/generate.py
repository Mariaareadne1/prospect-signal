"""Outreach generator: a signal-aware first-touch email per company.

Each email is drafted by the Anthropic API against that company's *actual*
signals — its tools, funding, headcount, and incidents — never a template. The
model is ``claude-fable-5`` with a graceful fallback to ``claude-opus-4-8`` on a
refusal or error, so one failure never kills the batch.

Design notes:
  - The API key is read only from the ANTHROPIC_API_KEY environment variable.
    It is never hardcoded and never committed.
  - Fable 5 has thinking always on, so the ``thinking`` parameter is omitted
    (an explicit value would 400), and sampling params are not used.
  - Results are cached by a hash of the inputs that shape the email, so re-runs
    don't re-call the API for unchanged companies.
  - If the key or SDK is missing, generation is skipped with a clear message;
    scoring, ranking, and the dashboard still run.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .models import Company, ScoreResult, Signals

PRIMARY_MODEL = "claude-fable-5"
FALLBACK_MODEL = "claude-opus-4-8"
MAX_TOKENS = 1024

# Bump when the prompt/voice changes so cached drafts regenerate.
_VOICE_VERSION = 4

DRAFTS_DIR = Path("drafts")
CACHE_PATH = Path(".cache/emails.json")

SYSTEM_PROMPT = """\
You are a sales development rep at Resolve AI. Resolve builds an AI production \
engineer that helps engineering teams with incident response: it investigates \
alerts, correlates signals across their tooling, and cuts down the pain of \
on-call rotations. Your buyers are engineering leaders and SREs who feel that \
pain directly.

Write a first-touch cold email to one specific company. You are given real \
public signals about their production setup. Reference the specifics that were \
provided; do not invent details you were not given.

Voice rules (these matter a lot):
- Sound like a real person typing to another person. Not marketing copy.
- Never write "I hope this email finds you", "I wanted to reach out", or \
"I'm excited to". No fake enthusiasm.
- No em-dashes anywhere. No bullet points in the body.
- Short: 4 to 6 sentences, hard maximum. Cover three things in whatever order \
feels natural for this specific company: something concrete about their \
production reality, why Resolve is relevant to it, and one clear ask for 15 \
minutes with the right person. Do not follow an identical template across \
companies.
- Do not open with the word "Noticed" or by stating an incident count. Vary \
your opening across emails. Enter through a different detail each time: \
sometimes the team's scale, sometimes their stack, sometimes a specific tool, \
sometimes the persona's day-to-day. The first sentence should not be \
structurally interchangeable with a first sentence written for a different \
company.
- Never use the phrases "wall of dashboards", "first pass", or "grounded \
starting point". Describe what Resolve does in fresh words each time.
- Only mention recent funding if the signals explicitly say they raised in the \
last 12 months. If they did not, do not reference funding at all.
- Warm, grounded, specific, understated. Never presumptuous or cocky. Do not \
claim to know their internal pain better than they do.
- Address the email to the given buyer persona and pitch at the level that \
persona cares about (an SRE cares about toil and alert noise; an eng leader \
cares about reliability, team focus, and cost of downtime).

Output only the email body, starting with a greeting line. No subject line, no \
sign-off name placeholder brackets, no commentary before or after."""

_DASH_RE = re.compile(r"\s*[—–]\s*")


@dataclass
class GenerationReport:
    """Summary of a generation run, for an informative terminal message."""

    generated: int = 0
    cached: int = 0
    skipped: int = 0
    used_api: bool = False
    reason: str = ""  # why generation was skipped, if it was
    errors: list[str] = field(default_factory=list)


def _enforce_voice(text: str) -> str:
    """Defensive guard for the one voice rule worth enforcing in code: no em-dashes."""
    return _DASH_RE.sub(", ", text).strip()


def _build_user_prompt(company: Company, signals: Signals, score: ScoreResult) -> str:
    """Assemble the per-company brief the model writes from — its real signals."""
    incident_note = (
        f"{signals.incident_count} recent public incidents "
        f"({'from their live status page' if signals.incident_count_source == 'live' else 'on public record'})"
    )
    reasons = "\n".join(f"- {r.text}" for r in score.reasons)
    return f"""\
Write the email to this company.

Company: {company.name}
Write to: {company.persona}
Funding stage: {company.stage}
Engineering headcount: about {company.eng_headcount}
On-call and incident tooling they use: {", ".join(company.oncall_tools)}
Production stack: {", ".join(company.stack)}
Incident history: {incident_note}

Why we think they're a fit (use these to ground the email, don't list them):
{reasons}"""


def _cache_key(company: Company, signals: Signals, score: ScoreResult) -> str:
    """Stable hash of everything that shapes the email. Any change busts the cache."""
    payload = {
        "voice": _VOICE_VERSION,
        "model": PRIMARY_MODEL,
        "name": company.name,
        "persona": company.persona,
        "stage": company.stage,
        "headcount": company.eng_headcount,
        "oncall_tools": company.oncall_tools,
        "stack": company.stack,
        "incident_count": signals.incident_count,
        "incident_source": signals.incident_count_source,
        "reasons": [r.text for r in score.reasons],
    }
    blob = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True))


def _make_client() -> tuple[object | None, str]:
    """Build an Anthropic client, or return None plus a human-readable reason why not."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None, "ANTHROPIC_API_KEY is not set"
    try:
        import anthropic
    except ImportError:
        return None, "the 'anthropic' package is not installed (pip install anthropic)"
    try:
        return anthropic.Anthropic(), ""
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"could not initialize the Anthropic client: {exc}"


def _generate_one(
    client: object, company: Company, signals: Signals, score: ScoreResult
) -> tuple[str, str]:
    """Draft one email, trying Fable 5 then falling back to Opus 4.8. Returns (email, error)."""
    user_prompt = _build_user_prompt(company, signals, score)
    last_error = ""

    for model in (PRIMARY_MODEL, FALLBACK_MODEL):
        try:
            # Fable 5 has thinking always on: omit the `thinking` param entirely
            # (an explicit value 400s), and don't pass sampling params.
            response = client.messages.create(  # type: ignore[attr-defined]
                model=model,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
        except Exception as exc:
            last_error = f"{model}: {exc}"
            continue

        # A safety classifier can decline with HTTP 200 + stop_reason "refusal";
        # fall through to the next model rather than reading empty content.
        if getattr(response, "stop_reason", None) == "refusal":
            last_error = f"{model}: refused"
            continue

        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        if text:
            return _enforce_voice(text), ""
        last_error = f"{model}: empty response"

    return "", last_error


def generate_all(
    companies: list[Company],
    signals: list[Signals],
    scores: list[ScoreResult],
    use_api: bool = True,
) -> tuple[dict[str, str], GenerationReport]:
    """Generate (or reuse cached) emails for every company.

    Returns a ``{slug: email}`` map plus a report for the terminal. Emails are
    written to ``drafts/<slug>.txt`` and kept in memory for the dashboard. A
    company whose email cannot be produced maps to an empty string; the rest of
    the pipeline is unaffected.
    """
    report = GenerationReport()
    cache = _load_cache()
    emails: dict[str, str] = {}
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    client: object | None = None
    client_reason = ""
    client_attempted = False

    for company, sig, score in zip(companies, signals, scores):
        key = _cache_key(company, sig, score)
        cached = cache.get(company.slug)

        if cached and cached.get("key") == key and cached.get("email"):
            email = cached["email"]
            report.cached += 1
        elif not use_api:
            email = ""
            report.skipped += 1
            report.reason = "live generation disabled"
        else:
            if not client_attempted:
                client, client_reason = _make_client()
                client_attempted = True
                report.used_api = client is not None
            if client is None:
                email = ""
                report.skipped += 1
                report.reason = client_reason
            else:
                email, error = _generate_one(client, company, sig, score)
                if email:
                    report.generated += 1
                    cache[company.slug] = {"key": key, "email": email}
                else:
                    report.skipped += 1
                    if error:
                        report.errors.append(f"{company.name}: {error}")

        emails[company.slug] = email
        if email:
            (DRAFTS_DIR / f"{company.slug}.txt").write_text(email + "\n")

    _save_cache(cache)
    return emails, report

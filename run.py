"""prospect-signal entry point.

Runs the whole pipeline end-to-end:

    load -> enrich -> score -> generate -> build dashboard

Then prints a ranked summary to the terminal and writes:
  - drafts/<company>.txt  (one outreach email per company)
  - index.html            (the dashboard; open it directly in a browser)

Usage:
    python run.py                 # full run, live status fetch on
    python run.py --no-live       # skip the live status fetch, use seeded counts
    python run.py --no-emails     # skip Anthropic email generation
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from src import dashboard, enrich, generate, score
from src.models import Company, Lead

DATA_PATH = Path("data/companies.json")


def load_companies(path: Path | str) -> list[Company]:
    """Load and validate the seed dataset, failing with a clear message."""
    path = Path(path)
    try:
        raw = json.loads(path.read_text())
    except FileNotFoundError:
        raise SystemExit(f"error: seed data not found at {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"error: {path} is not valid JSON ({exc})")
    try:
        return [Company.from_dict(record) for record in raw]
    except (ValueError, TypeError) as exc:
        raise SystemExit(f"error: invalid company record in {path} ({exc})")


def _tier_label(score_value: int) -> str:
    if score_value >= 90:
        return "High intent"
    if score_value >= 80:
        return "Strong"
    return "Moderate"


def _print_summary(leads: list[Lead]) -> None:
    """Print a ranked table (company, score) sorted by propensity."""
    ranked = sorted(leads, key=lambda l: l.score.score, reverse=True)
    name_w = max((len(l.company.name) for l in ranked), default=7)

    print()
    print(f"  {'#':>2}  {'SCORE':>5}  {'TIER':<11}  {'COMPANY':<{name_w}}  DRAFT")
    print(f"  {'-' * 2}  {'-' * 5}  {'-' * 11}  {'-' * name_w}  {'-' * 5}")
    for rank, lead in enumerate(ranked, start=1):
        draft = "yes" if lead.email else "-"
        print(
            f"  {rank:>2}  {lead.score.score:>5}  {_tier_label(lead.score.score):<11}  "
            f"{lead.company.name:<{name_w}}  {draft}"
        )
    print()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Lead scoring and outreach pipeline for Resolve AI's ICP.")
    parser.add_argument("--no-live", action="store_true",
                        help="disable the live status-page fetch; use seeded incident counts")
    parser.add_argument("--no-emails", action="store_true",
                        help="skip Anthropic email generation (scoring and dashboard still run)")
    parser.add_argument("--timeout", type=float, default=5.0,
                        help="per-request timeout in seconds for the live status fetch (default: 5)")
    parser.add_argument("--data", default=str(DATA_PATH), help="path to the seed dataset")
    parser.add_argument("--output", default="index.html", help="path to write the dashboard")
    args = parser.parse_args(argv)

    live = not args.no_live

    # 1. Load
    companies = load_companies(args.data)
    print(f"Loaded {len(companies)} companies from {args.data}")

    # 2. Enrich
    print(f"Enriching signals (live status fetch: {'on' if live else 'off'}) ...")
    signals = enrich.enrich_all(companies, live=live, timeout=args.timeout)
    if live:
        live_hits = sum(1 for s in signals if s.incident_count_source == "live")
        print(f"  live incident counts: {live_hits}/{len(companies)} "
              f"(the rest fell back to seeded counts)")

    # 3. Score
    scores = score.score_all(companies, signals)
    print("Scored all companies against the propensity rubric")

    # 4. Generate outreach
    print(f"Generating outreach emails (Anthropic API: {'off' if args.no_emails else 'on'}) ...")
    emails, report = generate.generate_all(companies, signals, scores, use_api=not args.no_emails)
    if report.used_api:
        print(f"  drafted {report.generated}, reused {report.cached} cached, skipped {report.skipped}")
        for err in report.errors[:5]:
            print(f"  ! {err}")
    elif report.cached:
        print(f"  reused {report.cached} cached drafts; new generation skipped ({report.reason})")
    else:
        print(f"  skipped email generation: {report.reason}")

    # 5. Build dashboard
    leads = [Lead(c, s, sc, emails[c.slug]) for c, s, sc in zip(companies, signals, scores)]
    generated_note = (
        f"Generated {datetime.now():%Y-%m-%d %H:%M} · {len(leads)} accounts "
        f"· live status fetch {'on' if live else 'off'}"
    )
    api_note = (
        "Emails drafted with claude-fable-5 (fallback claude-opus-4-8)."
        if report.generated or report.cached
        else "Emails not generated this run."
    )
    out_path = dashboard.render_dashboard(
        leads, out_path=args.output, generated_note=generated_note, api_note=api_note
    )

    # Terminal summary
    _print_summary(leads)
    drafts_ready = sum(1 for l in leads if l.email)
    print(f"Dashboard: {out_path.resolve()}")
    print(f"Drafts:    {drafts_ready} email(s) in ./drafts/")
    print("Open index.html in a browser to explore the ranked leads.")


if __name__ == "__main__":
    main()

"""Dashboard: render the ranked leads to a single static index.html.

No server, no framework, no external assets — the file opens directly from disk.
The score is a magnitude, so it's drawn as a sequential single-hue ring gauge
(darker teal = higher propensity); tier identity is carried by a labelled dot,
never colour alone. Restrained neutral surface, tabular numerals, generous
spacing: it should read like an internal GTM tool, not a tutorial.
"""

from __future__ import annotations

import html
import math
from pathlib import Path

from .models import Lead, is_triggered

OUTPUT_PATH = Path("index.html")


def _esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def _tier(score: int) -> tuple[str, str]:
    """Map a score to a (label, css-class) tier. Class drives the sequential hue."""
    if score >= 90:
        return "High intent", "tier-high"
    if score >= 80:
        return "Strong", "tier-strong"
    return "Moderate", "tier-moderate"


def _ring(score: int, tier_class: str) -> str:
    """A compact SVG ring gauge: track + arc proportional to score, number centered."""
    size, stroke = 68, 7
    radius = (size - stroke) / 2
    circumference = 2 * math.pi * radius
    filled = circumference * score / 100
    center = size / 2
    return f"""\
<svg class="ring {tier_class}" viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="Propensity score {score} of 100">
  <circle class="ring-track" cx="{center}" cy="{center}" r="{radius:.2f}" fill="none" stroke-width="{stroke}"/>
  <circle class="ring-value" cx="{center}" cy="{center}" r="{radius:.2f}" fill="none" stroke-width="{stroke}"
          stroke-linecap="round" stroke-dasharray="{filled:.2f} {circumference:.2f}"
          transform="rotate(-90 {center} {center})"/>
  <text class="ring-num" x="{center}" y="{center}" dominant-baseline="central" text-anchor="middle">{score}</text>
</svg>"""


def _chip(label: str, value: str) -> str:
    return f'<span class="chip"><span class="chip-k">{_esc(label)}</span>{_esc(value)}</span>'


def _reasons_html(lead: Lead) -> str:
    if not lead.score.reasons:
        return '<p class="empty">No scoring rules fired for this account.</p>'
    rows = "\n".join(
        f'<li><span class="pts">+{r.points}</span><span class="reason">{_esc(r.text)}</span></li>'
        for r in lead.score.reasons
    )
    return f'<ol class="reasons">{rows}</ol>'


def _email_html(lead: Lead, triggered: bool) -> str:
    if not triggered:
        return (
            '<p class="empty">Held for signal. No draft is written until this account has a '
            "recent public incident or crosses a score of 90 &mdash; the queue only reaches out "
            "when there's a reason to.</p>"
        )
    if not lead.email:
        return (
            '<p class="empty">Email not generated yet. Set <code>ANTHROPIC_API_KEY</code> '
            "and re-run <code>python run.py</code>.</p>"
        )
    return f'<div class="email"><pre>{_esc(lead.email)}</pre></div>'


def _recency(signals) -> tuple[str, bool]:
    """A 'why now' recency line and whether the incident is fresh (worth this week)."""
    days = signals.days_since_last_incident
    if days is None:
        return "No recent public incident", False
    if days == 0:
        return "Last incident today", True
    label = f"Last incident {days} day{'' if days == 1 else 's'} ago"
    return label, days <= 14  # fresh = a timely, contact-this-week trigger


def _status_label(status: str) -> str:
    """Humanize the stubbed outreach_status, e.g. 'not_contacted' -> 'Not contacted'."""
    return status.replace("_", " ").capitalize()


def _card(rank: int, lead: Lead) -> str:
    c, s = lead.company, lead.score
    tier_label, tier_class = _tier(s.score)
    panel_id = f"panel-{c.slug}"
    recency_text, fresh = _recency(lead.signals)
    recency_sort = lead.signals.days_since_last_incident
    recency_sort = recency_sort if recency_sort is not None else 100000
    triggered = is_triggered(lead.signals, s)
    hold_class = "" if triggered else " hold"
    hold_chip = "" if triggered else '<span class="hold">Hold for signal</span>'
    draft_heading = "First-touch draft" if triggered else "Outreach"
    chips = "".join(
        [
            _chip("Stage", c.stage),
            _chip("Eng", f"~{c.eng_headcount}"),
            _chip("On-call", ", ".join(c.oncall_tools)),
            _chip("Incidents", f"{lead.signals.incident_count}"),
        ]
    )
    return f"""\
<article class="card {tier_class}{hold_class}" data-score="{s.score}" data-recency="{recency_sort}">
  <button class="row" aria-expanded="false" aria-controls="{panel_id}">
    <span class="rank">{rank}</span>
    {_ring(s.score, tier_class)}
    <span class="meta">
      <span class="name-line">
        <span class="name">{_esc(c.name)}</span>
        <span class="tier"><span class="dot"></span>{_esc(tier_label)}</span>
        <span class="status">{_esc(_status_label(lead.outreach_status))}</span>
        {hold_chip}
      </span>
      <span class="recency{' fresh' if fresh else ''}">{_esc(recency_text)}</span>
      <span class="chips">{chips}</span>
    </span>
    <span class="persona">{_esc(c.persona)}</span>
    <span class="chevron" aria-hidden="true"></span>
  </button>
  <section class="panel" id="{panel_id}" hidden>
    <div class="panel-grid">
      <div class="panel-col">
        <h3>Why it scored {s.score}</h3>
        {_reasons_html(lead)}
      </div>
      <div class="panel-col">
        <h3>{draft_heading} <span class="to">to {_esc(c.persona)}</span></h3>
        {_email_html(lead, triggered)}
      </div>
    </div>
  </section>
</article>"""


def _summary(leads: list[Lead]) -> str:
    n = len(leads)
    high = sum(1 for l in leads if l.score.score >= 90)
    in_queue = sum(1 for l in leads if is_triggered(l.signals, l.score))
    drafts = sum(1 for l in leads if is_triggered(l.signals, l.score) and l.email)

    def tile(value: str, label: str) -> str:
        return f'<div class="tile"><div class="tile-num">{_esc(value)}</div><div class="tile-label">{_esc(label)}</div></div>'

    return (
        '<div class="tiles">'
        + tile(str(n), "Accounts")
        + tile(str(high), "High intent")
        + tile(str(in_queue), "In queue")
        + tile(str(drafts), "Drafts ready")
        + "</div>"
    )


_STYLE = """\
:root {
  /* Warm cream surface, near-black warm ink, acid-chartreuse accent used on
     solid fills only (paired with near-black text); score rings use a cohesive
     lime ramp so tiers stay distinguishable and the thin arcs stay legible. */
  --page: #f4f1ea; --card: #ffffff; --ink: #1a1a1a; --muted: #6c6559;
  --faint: #9b9285; --line: #e5dfd2; --chip-bg: #efeade; --accent: #d4f500;
  --accent-ink: #111111; --accent-deep: #5b7307;
  --high: #4d7c0f; --strong: #7cb518; --moderate: #b3c95a; --track: #e7e1d4;
  --pts-bg: #eef5d6; --pts-ink: #3f5308; --paper: #f8f5ec;
  --shadow: 0 1px 2px rgba(26,22,15,.05), 0 4px 16px rgba(26,22,15,.06);
}
@media (prefers-color-scheme: dark) {
  :root {
    --page: #17140d; --card: #201d15; --ink: #f0ece1; --muted: #a39a88;
    --faint: #6f685a; --line: #2e2a1f; --chip-bg: #272319; --accent: #d4f500;
    --accent-ink: #111111; --accent-deep: #c3e600;
    --high: #a3e635; --strong: #84cc16; --moderate: #6b8a2f; --track: #2c2820;
    --pts-bg: #2a3312; --pts-ink: #cbe88a; --paper: #1b1810;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 6px 20px rgba(0,0,0,.4);
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--page); color: var(--ink);
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  font-variant-numeric: tabular-nums; -webkit-font-smoothing: antialiased;
  line-height: 1.5;
}
.wrap { max-width: 940px; margin: 0 auto; padding: 56px 24px 96px; }

header { margin-bottom: 8px; }
.eyebrow { font-size: 12px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--accent-deep); margin: 0 0 10px; }
h1 { font-family: Georgia, "Times New Roman", serif; font-size: 35px; font-weight: 700; letter-spacing: -.005em; margin: 0 0 8px; }
.sub { color: var(--muted); font-size: 15px; margin: 0; max-width: 60ch; }
.genline { color: var(--faint); font-size: 12.5px; margin: 14px 0 0; }

.tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 32px 0 28px; }
.tile { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; box-shadow: var(--shadow); }
.tile-num { font-size: 26px; font-weight: 680; letter-spacing: -.02em; }
.tile-label { color: var(--muted); font-size: 12.5px; margin-top: 3px; letter-spacing: .01em; }

.controls { display: flex; align-items: center; justify-content: space-between; gap: 16px 24px; flex-wrap: wrap; margin: 0 2px 14px; }
.legend { display: flex; gap: 18px; align-items: center; color: var(--muted); font-size: 12.5px; }
.legend .k { display: inline-flex; align-items: center; gap: 7px; }
.legend .dot { width: 9px; height: 9px; border-radius: 50%; }
.sort { display: inline-flex; align-items: center; gap: 9px; color: var(--faint); font-size: 12.5px; }
.sort-label { font-weight: 600; letter-spacing: .02em; }
.sort .seg { display: inline-flex; border: 1px solid var(--ink); border-radius: 0; overflow: hidden; }
.sort .seg button { border: 0; background: var(--card); color: var(--ink); font: inherit; font-size: 12.5px; font-weight: 550; padding: 5px 14px; cursor: pointer; }
.sort .seg button + button { border-left: 1px solid var(--ink); }
.sort .seg button:hover { background: color-mix(in srgb, var(--accent) 18%, var(--card)); }
.sort .seg button[aria-pressed="true"] { background: var(--accent); color: var(--accent-ink); font-weight: 640; }

.list { display: flex; flex-direction: column; gap: 12px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; box-shadow: var(--shadow); overflow: hidden; }
.row {
  display: grid; grid-template-columns: 30px 68px 1fr auto 18px; align-items: center; gap: 18px;
  width: 100%; padding: 16px 20px; background: none; border: 0; cursor: pointer;
  text-align: left; color: inherit; font: inherit;
}
.row:hover { background: color-mix(in srgb, var(--accent) 4%, var(--card)); }
.row:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
.rank { color: var(--faint); font-size: 14px; font-weight: 600; text-align: center; }

.ring-track { stroke: var(--track); }
.tier-high .ring-value { stroke: var(--high); }
.tier-strong .ring-value { stroke: var(--strong); }
.tier-moderate .ring-value { stroke: var(--moderate); }
.ring-num { fill: var(--ink); font-size: 20px; font-weight: 680; }

.meta { min-width: 0; }
.name-line { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.name { font-size: 17px; font-weight: 640; letter-spacing: -.01em; }
.tier { display: inline-flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); font-weight: 550; }
.tier .dot { width: 8px; height: 8px; border-radius: 50%; }
.tier-high .tier .dot { background: var(--high); }
.tier-strong .tier .dot { background: var(--strong); }
.tier-moderate .tier .dot { background: var(--moderate); }
.status { font-size: 11px; color: var(--faint); background: var(--chip-bg); padding: 2px 8px; border-radius: 6px; font-weight: 550; letter-spacing: .02em; }
.recency { display: block; font-size: 12px; color: var(--muted); margin-top: 6px; }
.recency.fresh { display: inline-block; background: var(--accent); color: var(--accent-ink); font-weight: 640; padding: 2px 8px; border-radius: 2px; }
.hold { font-size: 11px; color: var(--faint); border: 1px solid var(--line); padding: 1px 8px; border-radius: 2px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; }
.card.hold { opacity: .9; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 9px; }
.chip { display: inline-flex; align-items: center; gap: 6px; background: var(--chip-bg); color: var(--ink); font-size: 12px; padding: 3px 9px; border-radius: 7px; white-space: nowrap; }
.chip-k { color: var(--faint); font-weight: 600; letter-spacing: .02em; }
.persona { color: var(--muted); font-size: 13px; white-space: nowrap; }

.chevron { width: 9px; height: 9px; border-right: 2px solid var(--faint); border-bottom: 2px solid var(--faint); transform: rotate(45deg); transition: transform .18s ease; justify-self: end; }
.row[aria-expanded="true"] .chevron { transform: rotate(-135deg); }

.panel { border-top: 1px solid var(--line); padding: 22px 20px 24px; }
.panel-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 30px; }
.panel h3 { font-size: 12px; font-weight: 640; letter-spacing: .08em; text-transform: uppercase; color: var(--faint); margin: 0 0 14px; }
.panel h3 .to { text-transform: none; letter-spacing: 0; font-weight: 500; color: var(--faint); }

.reasons { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 11px; }
.reasons li { display: grid; grid-template-columns: 42px 1fr; gap: 12px; align-items: start; }
.pts { background: var(--pts-bg); color: var(--pts-ink); font-size: 12.5px; font-weight: 660; text-align: center; padding: 2px 0; border-radius: 6px; }
.reason { font-size: 13.5px; color: var(--ink); }

.email { background: var(--paper); border: 1px solid var(--line); border-radius: 10px; padding: 18px 20px; }
.email pre { margin: 0; white-space: pre-wrap; font-family: inherit; font-size: 13.5px; line-height: 1.62; color: var(--ink); }
.empty { color: var(--muted); font-size: 13.5px; margin: 0; }
.empty code, .panel code { background: var(--chip-bg); padding: 1px 5px; border-radius: 4px; font-size: 12.5px; }

footer { color: var(--faint); font-size: 12px; margin-top: 40px; line-height: 1.7; }

@media (max-width: 760px) {
  .tiles { grid-template-columns: repeat(2, 1fr); }
  .panel-grid { grid-template-columns: 1fr; gap: 24px; }
  .row { grid-template-columns: 24px 60px 1fr 18px; }
  .persona { display: none; }
}"""

_SCRIPT = """\
document.querySelectorAll('.row').forEach(function (row) {
  row.addEventListener('click', function () {
    var open = row.getAttribute('aria-expanded') === 'true';
    row.setAttribute('aria-expanded', String(!open));
    var panel = document.getElementById(row.getAttribute('aria-controls'));
    if (panel) panel.hidden = open;
  });
});

// Sort toggle: reorder the cards by score (default) or by incident recency.
var list = document.querySelector('.list');
var buttons = document.querySelectorAll('.sort .seg button');
function applySort(key) {
  var cards = Array.prototype.slice.call(list.querySelectorAll('.card'));
  cards.sort(function (a, b) {
    if (key === 'recency') {
      // Freshest incident first; unknowns (large sentinel) sink to the bottom.
      return Number(a.dataset.recency) - Number(b.dataset.recency);
    }
    return Number(b.dataset.score) - Number(a.dataset.score);
  });
  cards.forEach(function (c) { list.appendChild(c); });
}
buttons.forEach(function (btn) {
  btn.addEventListener('click', function () {
    buttons.forEach(function (b) { b.setAttribute('aria-pressed', String(b === btn)); });
    applySort(btn.dataset.sort);
  });
});"""


def render_dashboard(
    leads: list[Lead],
    out_path: Path | str = OUTPUT_PATH,
    generated_note: str = "",
    api_note: str = "",
) -> Path:
    """Render ranked leads to a single static HTML file and return its path."""
    ranked = sorted(leads, key=lambda l: l.score.score, reverse=True)
    cards = "\n".join(_card(i, lead) for i, lead in enumerate(ranked, start=1))

    genline = f'<p class="genline">{_esc(generated_note)}</p>' if generated_note else ""
    footer_bits = ["Enrichment is seeded with manually gathered public signals; incident counts are fetched live from status pages when reachable."]
    if api_note:
        footer_bits.append(_esc(api_note))

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>prospect-signal · Resolve AI ICP</title>
<style>{_STYLE}</style>
</head>
<body>
<div class="wrap">
  <header>
    <p class="eyebrow">prospect-signal</p>
    <h1>Resolve AI &middot; ICP propensity</h1>
    <p class="sub">Target accounts ranked by buying propensity for incident response and on-call relief, each with the signals that drove the score and a tailored first-touch email.</p>
    {genline}
  </header>
  {_summary(ranked)}
  <div class="controls">
    <div class="legend">
      <span class="k"><span class="dot" style="background:var(--high)"></span>High intent &ge; 90</span>
      <span class="k"><span class="dot" style="background:var(--strong)"></span>Strong 80&ndash;89</span>
      <span class="k"><span class="dot" style="background:var(--moderate)"></span>Moderate &lt; 80</span>
    </div>
    <div class="sort">
      <span class="sort-label">Sort</span>
      <div class="seg" role="group" aria-label="Sort order">
        <button type="button" data-sort="score" aria-pressed="true">Score</button>
        <button type="button" data-sort="recency" aria-pressed="false">Recency</button>
      </div>
    </div>
  </div>
  <main class="list">
{cards}
  </main>
  <footer>{"<br>".join(footer_bits)}</footer>
</div>
<script>{_SCRIPT}</script>
</body>
</html>
"""
    path = Path(out_path)
    path.write_text(doc, encoding="utf-8")
    return path

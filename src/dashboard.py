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

from .models import Lead

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


def _email_html(lead: Lead) -> str:
    if not lead.email:
        return (
            '<p class="empty">Email not generated yet. Set <code>ANTHROPIC_API_KEY</code> '
            "and re-run <code>python run.py</code>.</p>"
        )
    return f'<div class="email"><pre>{_esc(lead.email)}</pre></div>'


def _card(rank: int, lead: Lead) -> str:
    c, s = lead.company, lead.score
    tier_label, tier_class = _tier(s.score)
    panel_id = f"panel-{c.slug}"
    chips = "".join(
        [
            _chip("Stage", c.stage),
            _chip("Eng", f"~{c.eng_headcount}"),
            _chip("On-call", ", ".join(c.oncall_tools)),
            _chip("Incidents", f"{lead.signals.incident_count}"),
        ]
    )
    return f"""\
<article class="card {tier_class}">
  <button class="row" aria-expanded="false" aria-controls="{panel_id}">
    <span class="rank">{rank}</span>
    {_ring(s.score, tier_class)}
    <span class="meta">
      <span class="name-line">
        <span class="name">{_esc(c.name)}</span>
        <span class="tier"><span class="dot"></span>{_esc(tier_label)}</span>
      </span>
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
        <h3>First-touch draft <span class="to">to {_esc(c.persona)}</span></h3>
        {_email_html(lead)}
      </div>
    </div>
  </section>
</article>"""


def _summary(leads: list[Lead]) -> str:
    n = len(leads)
    high = sum(1 for l in leads if l.score.score >= 90)
    drafts = sum(1 for l in leads if l.email)
    avg = round(sum(l.score.score for l in leads) / n) if n else 0

    def tile(value: str, label: str) -> str:
        return f'<div class="tile"><div class="tile-num">{_esc(value)}</div><div class="tile-label">{_esc(label)}</div></div>'

    return (
        '<div class="tiles">'
        + tile(str(n), "Accounts")
        + tile(str(high), "High intent")
        + tile(str(avg), "Avg score")
        + tile(str(drafts), "Drafts ready")
        + "</div>"
    )


_STYLE = """\
:root {
  --page: #f6f7f8; --card: #ffffff; --ink: #14181d; --muted: #626b76;
  --faint: #8a929c; --line: #e6e8ec; --chip-bg: #f1f3f5; --accent: #0f766e;
  --high: #0d6b60; --strong: #2f9488; --moderate: #86b3ac; --track: #edf0f1;
  --pts-bg: #e6f2f0; --pts-ink: #0c5a52; --paper: #fbfaf7;
  --shadow: 0 1px 2px rgba(20,24,29,.04), 0 4px 16px rgba(20,24,29,.05);
}
@media (prefers-color-scheme: dark) {
  :root {
    --page: #0f1214; --card: #171b1f; --ink: #e9edf0; --muted: #98a2ad;
    --faint: #6e7883; --line: #262c31; --chip-bg: #1f252a; --accent: #3fb8ab;
    --high: #43c2b4; --strong: #2f9488; --moderate: #4f736e; --track: #232a2f;
    --pts-bg: #13322e; --pts-ink: #6fd6c8; --paper: #12171a;
    --shadow: 0 1px 2px rgba(0,0,0,.3), 0 6px 20px rgba(0,0,0,.35);
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
.eyebrow { font-size: 12px; font-weight: 600; letter-spacing: .14em; text-transform: uppercase; color: var(--accent); margin: 0 0 10px; }
h1 { font-size: 30px; font-weight: 680; letter-spacing: -.02em; margin: 0 0 6px; }
.sub { color: var(--muted); font-size: 15px; margin: 0; max-width: 60ch; }
.genline { color: var(--faint); font-size: 12.5px; margin: 14px 0 0; }

.tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 32px 0 28px; }
.tile { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; box-shadow: var(--shadow); }
.tile-num { font-size: 26px; font-weight: 680; letter-spacing: -.02em; }
.tile-label { color: var(--muted); font-size: 12.5px; margin-top: 3px; letter-spacing: .01em; }

.legend { display: flex; gap: 18px; align-items: center; color: var(--muted); font-size: 12.5px; margin: 0 2px 14px; }
.legend .k { display: inline-flex; align-items: center; gap: 7px; }
.legend .dot { width: 9px; height: 9px; border-radius: 50%; }

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
  <div class="legend">
    <span class="k"><span class="dot" style="background:var(--high)"></span>High intent &ge; 90</span>
    <span class="k"><span class="dot" style="background:var(--strong)"></span>Strong 80&ndash;89</span>
    <span class="k"><span class="dot" style="background:var(--moderate)"></span>Moderate &lt; 80</span>
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

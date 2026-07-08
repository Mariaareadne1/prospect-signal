# prospect-signal

A lead-scoring and outreach pipeline for [Resolve AI](https://resolve.ai)'s
ideal customer profile: engineering teams running painful on-call rotations.

It takes a list of target companies, enriches each with public signals an SDR
cares about, scores them 0–100 for buying propensity **with transparent
reasons**, drafts a tailored first-touch email per company, and renders
everything to a clean, single-file dashboard.

Built as a portfolio piece — the point is to do the SDR job (find the right
accounts, know why they're right, and open a real conversation) end to end.

## Why these signals

Resolve AI sells incident response and production engineering. The strongest
buying signal is a team that **already pays for on-call tooling and still feels
the pain**: a large-enough engineering org, modern distributed infrastructure,
and a public track record of incidents. The rubric encodes exactly that.

## Scoring rubric

Each rule that fires adds points **and** records a plain-language reason. The
reasons ship all the way to the dashboard — the number is only as useful as the
"why" behind it. Scores are capped at 100.

| Signal | Points | Why it matters |
| --- | ---: | --- |
| Uses PagerDuty / Opsgenie / Datadog / Splunk on-call | +30 | Already pays for incident tooling — budget plus admitted pain |
| Engineering headcount > 200 | +20 | Enough scale that on-call load is a real, recurring cost |
| Raised funding in the last 12 months | +15 | Fresh budget and pressure to keep reliability ahead of growth |
| Kubernetes / microservices / multi-cloud in the stack | +15 | Distributed systems mean more failure modes and noisier on-call |
| 3+ recent public incidents | +20 | Visible, admitted reliability pain — a timely reason to reach out |

## How to run

```bash
python run.py
```

That single command runs the whole pipeline: `load → enrich → score →
generate → build dashboard`. It prints a ranked summary to the terminal, writes
one email per company to `drafts/`, and builds `index.html` (open it directly
in a browser — no server needed).

Useful flags:

```bash
python run.py --no-live      # skip the live status-page fetch, use seeded counts
python run.py --no-emails    # skip email generation (scoring + dashboard still run)
python run.py --timeout 3    # per-request timeout for the live fetch (seconds)
```

### Outreach generation (optional API step)

Email drafting calls the Anthropic API. Set your key first:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

The key is read only from the environment — it is never hardcoded or committed.
Generated emails are cached, so re-runs don't re-call the API for unchanged
companies. If the key is missing, the pipeline still scores and ranks; it just
skips email generation and says so.

## Project layout

```
prospect-signal/
  data/companies.json   ICP seed dataset
  src/models.py         Company / Signals / ScoreResult / Lead data model
  src/enrich.py         Derived signals + optional live status-page fetch
  src/score.py          Transparent weighted scoring rubric
  src/generate.py       Signal-aware outreach email generation
  src/dashboard.py      Static index.html renderer
  run.py                Orchestration + terminal summary
```

## A note on the data (honest)

The enrichment layer is seeded with **manually gathered public signals** —
funding stage, engineering headcount, on-call tooling, and stack are
hand-collected estimates for a demo. The one exception is incident counts: the
pipeline will optionally fetch a company's public status page live and count
recent incidents, falling back to the seeded number if the fetch fails.

In production this layer would connect to real enrichment sources — Apollo or
Clearbit for firmographics, job-posting and status-page APIs for tooling and
reliability signals — instead of a static seed file.

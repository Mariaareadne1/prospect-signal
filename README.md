# prospect-signal

I built this for the Growth & Strategy role at Resolve AI. Resolve's buyers are
engineering teams whose on-call is genuinely painful, and the hardest part of an
SDR's job isn't writing emails, it's deciding who's worth writing to and when.
That decision usually lives in someone's head. This makes it explicit.

prospect-signal takes a set of target accounts, scores each one on how much on-call
pain it's likely feeling, and only drafts outreach for the accounts where there's a
real reason to reach out right now. The output is a ranked dashboard: who to contact,
why they scored the way they did, and a first email that references their actual
production setup.

## The idea

A lead score on its own is a guess. What makes an account worth an email today isn't
just that it fits the profile, it's that it's showing a signal it published itself.
A company's status page is the most honest thing about it: when incidents show up
there, the team is provably feeling the exact pain Resolve solves, and it's a public
fact, so referencing it isn't creepy, it's relevant.

So this isn't a list, it's a queue. It watches for the signals a company broadcasts
when it's hurting and surfaces those accounts first. Accounts with no recent incident
and nothing but a decent profile score get held, not spammed. The tool reaching out
only when there's a reason is the point, not a limitation.

## How it scores

Every account gets 0–100 from a transparent rubric. Each rule adds points and states
its reason in plain language, because the first question anyone asks about a lead
score is "says who, based on what."

- Already pays for incident tooling (PagerDuty, Datadog, Opsgenie, Splunk): +30.
  Budget exists and the pain is admitted.
- Engineering org over 200: +20. On-call load scales with headcount.
- Raised in the last 12 months: +15. Fresh budget, pressure to keep reliability
  ahead of growth.
- Distributed stack (Kubernetes, microservices, multi-cloud): +15. More failure
  modes, noisier on-call.
- Three or more recent public incidents: +20. Visible, self-reported reliability pain.

An account is drafted only if it has a public incident in the last 14 days or scores
90+. Everything else is held for signal.

## What a draft looks like

Emails reference the account's real signals and are written to sound like a person,
not marketing. Here's the draft for an account with an incident that day:

> Saw your status page has an active incident today, so I'll keep this brief and
> won't pretend the timing is great. Resolve builds an AI production engineer that
> investigates alerts on its own, pulling context from Datadog and PagerDuty and
> tracing the failure across Kubernetes services before an engineer even opens a
> laptop. With three public incidents recently and roughly 400 engineers sharing the
> pager, the investigation hours add up fast. Teams use it to shrink that time and
> give on-call a head start on root cause. Would you be open to 15 minutes next week,
> once things settle, to see how it works on a stack like yours?

## Running it

Run the pipeline with:

    python run.py

Loads the accounts, enriches them (including a live status-page fetch that degrades
gracefully if a page is unreachable), scores them, drafts emails for triggered
accounts, and builds index.html. Open that to see the ranked queue. Email
generation reads ANTHROPIC_API_KEY from the environment.

## Honest notes

The enrichment layer is seeded with public signals I gathered by hand. In production
it would pull from Apollo, Clearbit, and status-page APIs directly. The scoring
weights are a starting hypothesis, not gospel: the intended next step is a feedback
loop that tracks which signals actually predicted a reply and tunes the weights from
what converts. Right now every account shows an outreach_status field stubbed for
exactly that.

## Structure

- data/companies.json — the seed accounts
- src/enrich.py — signal derivation + live status-page fetch
- src/score.py — the transparent scoring rubric
- src/generate.py — signal-aware email drafting
- src/dashboard.py — the static dashboard
- run.py — orchestrates the pipeline

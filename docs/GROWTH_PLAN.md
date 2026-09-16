# Neon Node: audience growth plan

Start: the first deployed run carrying `growth.strategy = builders-v1`.
Review after 30 days of publishing, extending the window when observations
are sparse. This is a positioning hypothesis, not a promise of virality.

## Audience and promise

Initial audience: developers and hands-on AI builders deciding what to use,
what a change will cost, and what can break their software. This is inferred
from the channel's existing technical content; it is not measured demographic
data. Speak plainly enough for a junior developer, with enough evidence for an
experienced one. Organic distribution cannot target an exact audience on demand.

Channel promise: **Understand the tools, trade-offs, and failures that affect
what you build.** Each reel earns a save or a send to a teammate by explaining
one source-backed consequence, not merely reporting that a company did something.

Three repeatable editorial series:

| Series | Selection question | Reward for watching |
| --- | --- | --- |
| Build with it | What concrete capability changed in a named developer tool? | Mechanism + use case + limitation |
| Know the trade-off | What changes latency, compute, memory, or infrastructure cost? | Measured result + test conditions + decision boundary |
| Before it breaks | What named dependency, incident, or security issue affects a workflow? | Cause + affected scope + documented mitigation, when available |

Prefer these over broad company drama, consumer gadget chatter, abstract AI
predictions, and unrelated viral curiosities. Selection remains after existing
dedup/freshness/cooldown checks. Keyword matching is an explainable first-pass
proxy, not proof of relevance. When nothing matches, keep the existing eligible
pool and log the fallback; never invent a developer angle. Source grounding and
the existing script gate remain responsible for factual specificity.

## Editorial contract

1. Pick one affected workflow and one supported consequence before writing.
2. In scene 0, open a factual gap with a shock stat, broken assumption, or
   stakes reveal. Include a workflow cue in narration or visible text: API,
   dependency, local model, database, build, deployment. No greeting; do not
   begin the narration with the product name. Name the subject elsewhere in
   that scene. Keep the existing max-12-word narration and overlay budgets.
3. Deliver a useful source-backed fact in the next scene. The hook promises
   exactly what the closing explains. Do not withhold all value until the end.
4. Explain the mechanism and one meaningful limitation/test condition. A
   vendor benchmark is a vendor claim, not our independent test. Never invent
   experience, urgency, numbers, quotes, affected users, or a mitigation.
5. Close with who benefits and under which conditions, before any optional
   content-specific CTA. Preserve quiz/ranking reveal rules where applicable.

Illustrative hook shapes, **not publishable claims without matching sources**:
“Your dependency can run code during documentation builds.” / “That benchmark
doesn't measure your workload.” / “Your local model needs more than disk space.”
Each needs a named source, demonstrated mechanism and exact scope. Avoid
“Everyone's code is unsafe” or “This AI replaces developers.”

Use existing metric/comparison/list scenes when source facts support them.
Stock footage supplies atmosphere, not evidence. A simulated UI is not a real
product demonstration. A later visual experiment can test real source captures;
this release does not pretend to have implemented source screenshots.

## Thirty-day sequence

| Window | Action | Decision |
| --- | --- | --- |
| Before rollout | Save local baseline report; inspect Account Status/recommendation eligibility in Instagram if accessible | Content changes cannot fix an account eligibility restriction |
| Days 1–7 | Ship the same audience promise through all existing formats; inspect early outputs for source fidelity and recognizable workflow cues | Fix copy failures, not the entire strategy after one low-view post |
| Days 8–14 | Review measured posts by series and existing runtime experiment arm | Improve the weakest promise/proof step; keep cadence and runtime settings stable |
| Days 15–21 | Develop distinct follow-up stories in the strongest useful series, only when new evidence exists | No duplicate reposts or forced quota of thin stories |
| Days 22–30 | Compare mature post distributions against the saved baseline | Continue, revise the audience hypothesis, or investigate distribution separately |

No new posting cadence, automated comments, DMs, paid promotion, or mass reposts.
The current schedule and delivery code remain as configured. Series mix is
reported, not enforced as a quota that can force weak stories.

Optional profile copy for the account owner: “Tools, trade-offs & failures for
people building with code and AI. One concrete takeaway per reel.” Pin three
representative, evidence-rich reels when they exist. Profile edits and pinning
are external actions and are not performed by this implementation.

## Measurement and experiment discipline

Run `python3 growth_report.py --days 30`. This is offline and read-only. For
machine-readable results add `--json`; use `--as-of 2026-09-16T00:00:00Z` for a
reproducible review. `--days 0` includes the entire retained ledger. The ledger
is capped, so it is not necessarily the account's lifetime history.

Compare only recorded `snap72` snapshots whose actual collection age is 48h–7d.
This is an approximate age window, not an exact 72-hour measurement; report
the observed ages and coverage. Missing snapshots/metrics are unknown, not zero.
Deleted posts and backfills are excluded. Never fall back to lifetime latest
metrics for a supposedly age-matched comparison.

Report per-post medians for views, absolute watch seconds, shares per 1,000
reached and saves per 1,000 reached. For quality metrics require at least 20
views; rates additionally need at least 20 reached. Show metric sample counts.
These floors limit obvious noise, not prove statistical significance. Shares
are total shares, not a measurement of DM sends; watch/runtime is not completion
rate. Saves/shares indicate utility, not the profession of the viewer. Follows,
profile visits, non-follower reach and the 3-second retention curve are unknown
unless separately collected in account Insights; do not manufacture them.

Keep the existing feedback clamps, exploration rate, cold-start gate and runtime
experiment intact. Growth revision is descriptive metadata, not a bandit bucket.
Historical topics are labelled retrospective classification, not randomized
arms. Changes in this rollout happen together, so before/after differences
cannot isolate the effect of one prompt line.

At least 20 mature, measured posts **per arm** are needed before even considering
an experiment result; quality endpoints need their own coverage. Below that,
report insufficient evidence and continue observing. Above that, examine
medians, spread, similar series/format composition and repeated improvement;
20 is not automatic statistical significance. A tentative useful improvement
is higher absolute watch time without collapsing reach and saves/shares on
multiple distinct posts. If all utility counts remain zero, there is no
evidence yet that the intended audience finds the content useful.

When a later hook test is justified, vary only the framing (stakes versus
broken assumption), keep audience/format/runtime stable, and use the existing
experiment assignment machinery. No new hook A/B is silently started here:
the existing runtime assignment must not be overwritten.

## Implementation and rollback

`growth_strategy.py` owns the audience vocabulary and grounded writing brief.
The existing topic selectors prefer matching fresh candidates; the editorial
judges and news/tech prompt builders receive the brief. The shared automated
render path also adds it, covering quiz/ranking and fallback entry points.
Manual arbitrary-topic renders stay unchanged. Additive render ledger metadata
records the strategy and inferred series; protected dispatch code is untouched.
`GROWTH_STRATEGY=off` restores the old selection/prompt behavior and omits growth
metadata. New dependencies, API permissions and paid services are unnecessary.

## Evidence and limits

Meta describes recommendations as personalized, including topic/genre signals:
[recommendation systems](https://ai.meta.com/blog/ai-unconnected-content-recommendations-facebook-instagram/).
Our inference is that a clear recurring audience promise gives both people and
the recommendation system clearer signals; this is not a disclosed ranking
formula. The formula in AGENTS.md is an editorial heuristic, not a verified
Instagram equation.

Meta explains that [Trial Reels](https://about.fb.com/news/2024/12/trial-reels-try-content-non-followers-first-see-what-perfoms-best/)
can expose trials to non-followers. They are an optional later experiment,
not precise audience targeting and not enabled by this change. Instagram also
has [recommendation eligibility guidelines](https://about.fb.com/news/2020/08/recommendation-guidelines/).
Low reach by itself does not diagnose a restriction or a “shadowban.”

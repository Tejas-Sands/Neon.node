# Audience Growth Implementation Plan

**Goal:** Make the existing automated channel consistently useful to developers
and AI builders, and measure attention and utility honestly.

**Architecture:** Reuse the current topic, prompt, ledger and experiment paths.
A pure standard-library strategy module provides transparent topic signals and
one shared editorial brief. A standalone read-only reporter summarizes mature
snapshots without importing the application or touching credentials.

**Tech stack:** Python standard library plus existing application dependencies.

**Spec:** `docs/GROWTH_PLAN.md`. User authorized planning and implementation.

## Constraints

- Preserve protected publishing/caption code and dispatch call sites.
- No new dependencies, live posts, external messages or workflow changes.
- Preserve fabrication guards, dedup, cooldown and feedback floors/clamps.
- Existing runtime experiments remain independent; no new randomized test.
- `GROWTH_STRATEGY=off` disables all strategy behavior.

## Tasks

- [x] Add `test_growth_strategy.py`: realistic relevant/irrelevant candidate
  fixtures, word-boundary false positives, dedup-before-preference integration,
  no-match fallback, disabled behavior and prompt wiring. Run it red.
- [x] Implement `growth_strategy.py`: `classify_topic(text) -> dict`,
  `prefer_audience_candidates(candidates) -> list`,
  `audience_directive() -> str`, `growth_metadata(topic) -> dict`.
  Integrate those into existing selectors, judges, script prompts and render
  metadata in `main.py`; leave the delivery region unchanged. Run tests green.
- [x] Add `test_growth_report.py`: mature snapshot ages, missing/zero metrics,
  low exposure, deleted/backfilled posts, malformed data, cohort isolation.
  Run red, implement `growth_report.py` with `build_report(ledger, now, days)`
  and CLI `--ledger`, `--days`, `--as-of`, `--json`, then run green.
- [x] Generate a reproducible baseline from the local ledger and record its
  limits in `docs/GROWTH_BASELINE.md`; document usage and the rollback switch.
- [x] Run the existing offline content/selection/feedback/format/experiment
  suites, review the diff for protected-region changes, and report local
  completion separately from deployment and measured growth.

## Verification record

- 14 new offline unit tests pass (strategy and report).
- Nine existing suites pass: script gate, topic judge, topic selection, topic
  sources, feedback scoring, experiments, format packs, captions, TTS providers.
- Legacy selector tests now explicitly set `GROWTH_STRATEGY=off`; audience-on
  tests separately verify freshness, dedup and cooldown precedence.
- TypeScript `tsc --noEmit`, Python 3.9 syntax parsing for the new modules,
  JSON report/baseline agreement and `git diff --check` pass.
- AST comparison confirms only seven intended content/render functions changed;
  the render delivery block is byte-identical and other function bodies are
  unchanged. No workflow/caption/dispatch modifications.
- No live generation, rendering, publishing, profile edits or deployment was
  performed; credentials and paid services are not needed for these checks.

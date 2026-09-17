# Voice Pace and Brag Motion Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax. Work inline; delegation is not needed.

**Goal:** Produce livelier, clearer narrated reels and adapt Brag's focused visual storytelling into the existing renderer, with matched review artifacts and measurable rollout.

**Architecture:** Keep the Edge/Kokoro synthesis seam and Remotion pipeline. Improve speech selection and timing before extending the existing story-motion components. Compare one variable at a time and retain publishing safeguards.

**Tech Stack:** Python, Edge-TTS, optional existing Kokoro worker, FFmpeg/ffprobe, React/TypeScript, Remotion 4.0.482; no new runtime dependencies.

**Spec:** [voice-and-brag-motion-design.md](../specs/2026-09-17-voice-and-brag-motion-design.md).

**Status:** Implemented and checked locally, 2026-09-17, on `feat/voice-brag-motion`.
The user selected Aria at +12% after auditions. See the
[execution record](../../VOICE_MOTION_REVIEW.md) for artifacts, measurements and
deviations. Final mix listening, deployment and audience validation remain pending.
Unchecked mixed review items below are intentionally not claimed complete.

## Global constraints

- Keep Remotion; add no renderer, animation dependency or paid TTS requirement.
- Spoken hook at most 12 words; title at most four; hook text at most eight.
- Preserve source grounding, anti-repetition and the builder audience strategy.
- Preserve final post-TTS word alignment, failure guards and provider fallback.
- Preserve frame-zero cover, HookPunch, still ending, contrast and word integrity.
- Preserve seeded draw order and quiz/ranking reveal rules; unsupported scenes fall back.
- Preserve format-pack budgets, any configured runtime experiment and feedback floors.
- Publishing, captions, schedules, tokens and delivery workflows remain frozen.

## File ownership

| Files | Purpose |
| --- | --- |
| `scripts/preview_editorial.py` | Local-only voice matrix and review artifact generation |
| `scripts/measure_spoken_rate.py` | Calibration using actual scene-shaped fixtures |
| `main.py` synthesis / estimator / spoken prompts only | Voice timing and writing; no posting-region changes |
| `test_voice_identity.py`, `test_tts_providers.py`, new `test_voice_pacing.py` | Pin precedence, timing and failure behavior |
| `src/remotion/MyComp/StoryScene.tsx`, `storyMotion.ts` | Adapt visual direction and readable action timing |
| `src/remotion/MyComp/Main.tsx` | Minimal integration of existing audio/caption/layer owners |
| `scripts/check-story-motion.ts`, `tests/fixtures/story-motion.json` | Deterministic assertions and preview fixture |
| `.env.example`, `AI_CONTEXT.md`, `docs/VOICE_MOTION_REVIEW.md` | Settings, calibration evidence, review decisions and rollback |

Do not edit `generate_now.py`, posting functions, caption builders, workflows or
credentials to complete these tasks. Existing `.github/workflows/generate_video.yml`
is read-only evidence: it explicitly exports `VOICEOVER_RATE=+5%` by default.

## Task 1 — Matched voice auditions and baseline

**Modify:** `scripts/preview_editorial.py`, `scripts/measure_spoken_rate.py`.
**Create:** `docs/VOICE_MOTION_REVIEW.md` during implementation.
**Inputs:** Existing source-grounded editorial fixture and at least two saved
production-shaped scripts with their source references, kept local if untracked.
**Outputs:** Local MP3s, per-scene timing JSON, matched preview props and a review
table recording voice, rate, pitch, timings and perceptual observations.

- [x] Save `git status --short` and the current preview settings. Run the offline
  baseline report without fetching account data:

  ```bash
  python3 growth_report.py --as-of 2026-09-16T00:00:00Z --days 30
  ```

- [x] Extend the existing audition loop to preserve individual scenes rather
  than concatenate narration; deep-copy scenes before each synthesis because
  `_generate_voiceover_with_engine` mutates durations. Initial candidates:

  ```python
  candidates = [
      ("control", "en-US-JennyNeural", "+5%", "+0Hz"),
      ("jenny-fast", "en-US-JennyNeural", "+12%", "+0Hz"),
      ("aria-fast", "en-US-AriaNeural", "+12%", "+0Hz"),
      ("guy-fast", "en-US-GuyNeural", "+12%", "+0Hz"),
  ]
  ```

- [x] Use explicit synthesis arguments so inherited env settings cannot change
  the comparison. Keep the script, mix and loudness identical. Write the real
  resolved voice/provider, not just the requested candidate name, into the
  manifest so fallback samples cannot masquerade as successful auditions.
- [ ] Save per-scene first-word onset, last-word end, decoded duration, scene
  duration and hold after speech. Use ffprobe for clip duration and FFmpeg
  `silencedetect=noise=-45dB:d=0.08` as a silence diagnostic; listen before using
  that threshold for trimming. Distinguish detected silence from reading holds.
- [ ] Run `python3 scripts/preview_editorial.py`; review raw narration and matched
  mixes at phone volume. Score naturalness, momentum and pronunciation on a
  simple 1–5 scale; no broadcaster cadence or clipped key term may pass.
- [ ] Compare the best faster candidate at +8%/+16%. If available, compare
  existing Kokoro af_heart/af_bella at 1.12 through the current seam. Record
  unavailable Kokoro as unavailable; do not install another engine by default.
- [x] Record the recommended voice/rate plus files the user can actually play.
  If listening is unavailable, explicitly mark perceptual acceptance pending;
  do not infer voice quality from speed numbers. Commit only code/docs when
  appropriate; generated audio remains a local artifact.

**Acceptance:** Reproducible auditions varying only delivery, truthful metadata,
and a reviewable recommendation. This task alone does not change production.

## Task 2 — Speech timing without dead holds or clipped words

**Modify:** `main.py::_generate_voiceover_with_engine`, `_estimate_spoken_seconds`,
`scripts/measure_spoken_rate.py`, `test_voice_identity.py`.
**Create:** `test_voice_pacing.py`.
**Inputs:** Task 1 measurements and selected delivery; original WordBoundary data.
**Outputs:** Correctly refitted scene durations, aligned captions, calibration
report and a legacy timing escape hatch `VOICE_PACING=legacy` (new process env).

- [x] Add failing behavior tests to `test_voice_pacing.py` using the existing
  mocked synthesis pattern. Required cases: short audio does not acquire a
  blanket three-second hold; long audio remains complete; explicit rate wins;
  leading trim shifts every boundary equally; failed/empty audio still aborts.
  A small pure helper in `main.py` may own the shared frame calculation:

  ```python
  import math

  # Proposed interface; called only after any safe exterior-silence trim.
  def _fit_voice_scene_frames(audio_end_sec, read_floor_frames, fps=30):
      return max(math.ceil(audio_end_sec * fps), read_floor_frames)

  # Tests for actual boundaries, not a mirrored implementation.
  self.assertEqual(_fit_voice_scene_frames(1.1, 60), 60)
  self.assertEqual(_fit_voice_scene_frames(4.01, 60), 121)
  self.assertEqual(_fit_voice_scene_frames(1.1, 108), 108)
  ```

- [x] Run `python3 -m unittest test_voice_pacing`; confirm the new cases fail for
  the intended behavior before implementing them. Keep precedence tests for
  request > environment > selected default; preserve natural-pitch identity.
- [x] Compare 0.18s tail to 0.35s on the audition corpus. Decode to local PCM for
  trimming only if exterior silence is confirmed. Retain at least 60ms before
  first speech and never trim before the last WordBoundary end; extend further
  if audible speech decay remains. Keep unmodified audio if uncertain. Calculate
  new timestamps from the actual leading trim; a shortened duration without
  trimming the underlying clip can overlap adjacent speech and is unacceptable.
- [x] Replace the 90-frame minimum on the new path with max(audio coverage,
  reading budget, 60). Use the longest required visible read for the floor:
  settled headline max(1.2s, 0.3s × words), plus its entrance; sequential panels
  require the total read or fallback. The caption track still follows speech.
  Preserve exactly the old calculation when `VOICE_PACING=legacy`.
- [x] Refit with `ceil` at 30fps; derive mix offsets and global word timestamps
  from those same final durations. No final-mix `atempo`, independent subtitle
  scaling, loss of the REQUIRE_VOICEOVER guard or provider restart behavior.
- [x] Recalibrate using the same individual scenes for old/new settings. Extend
  `measure_spoken_rate.py` to accept a props fixture and explicit voice/rate/pitch.
  Account for selected rate and legacy/new timing in the estimator. Separate
  raw speaking time from minimum reading holds; do not use few-shot corpus
  ratios alone to claim production accuracy. Record estimate versus actual for
  at least three scripts; investigate errors above 10% before promotion.
- [ ] Recheck post-TTS hook/body/pack durations. Overlong copy goes through the
  existing bounded revision path; never cap duration underneath speech. If a
  faster read undershoots a pack, improve substantive explanation, never filler.
- [x] Run:

  ```bash
  python3 -m unittest test_voice_identity test_voice_pacing
  python3 test_tts_providers.py
  python3 test_format_packs.py
  python3 test_script_gate.py
  ```

**Acceptance:** No swallowed endings, sentence overlap or caption drift; short
scenes lose avoidable holds while longer reads remain readable. Task 1 artifacts
include before/after gaps. Update changed duration expectations intentionally.

## Task 3 — Conversational copy and Brag-inspired visual comparison

**Modify:** `main.py::_SPOKEN_WARMTH_RULES` / corresponding news tone block only
if auditions reveal a concrete writing failure; `StoryScene.tsx`, `storyMotion.ts`,
minimal `Main.tsx` integration; `scripts/check-story-motion.ts` and existing fixture.
**Inputs:** Final narration, existing scene fields, post-TTS durations and seed.
**Outputs:** Matched current/proposed visual previews with no new public schema.

- [x] Select three grounded scripts: tool workflow, numerical trade-off and
  reliability/security scope. Record the source for every claim. Use existing
  eligible `split`, `metric`, `comparison` scenes. Correct formal passages using
  concrete verbs and contractions; preserve hook/reaction/question limits and
  give proof in scene 1. Compare copy changes separately from Task 1 audio.
- [x] Before changing the renderer, render and retain the current visual output
  for each script using Task 2's final audio and props. These are the visual
  controls; switching `deriveStoryMotion` off would instead select the older
  generic layouts, which is not an honest control for today's story renderer.
- [x] Establish a compact storyboard per script: promise → first proof →
  surprising mechanism → useful close. Specify one visible action per scene.
  Choose a verified local source capture where it genuinely demonstrates the
  claim, or the existing labelled schematic. No automatic capture service.
- [x] Add deterministic assertions before editing timing logic, including a
  short scene with no legal reading/reveal window:

  ```typescript
  const shortEnergy = [
    {landEnd: 26, kineticStart: 60, still: false},
    {landEnd: 26, kineticStart: 40, still: false},
    {landEnd: 26, kineticStart: 45, still: true},
  ];
  const shortScenes = [
    {type: "hero", text: "A concrete question", durationInFrames: 120},
    {type: "metric", text: "32-bit", durationInFrames: 60},
    {type: "split", text: "A concrete answer", durationInFrames: 90},
  ];
  assert.equal(deriveStoryMotion(shortScenes, [], shortEnergy, 30)[1].kind, "legacy");
  ```

  Retain existing tests for exact units, no negated compression, early/unmatched
  timestamps, quiz/ranking protection, determinism and fully settled final state.
- [x] Refine `StoryScene.tsx` around one dominant idea: stronger display type,
  less decorative furniture, one evidence panel and one semantic transformation.
  Reuse existing kinds and `storyStage`, `fitStackScale`, `fitStoryFont`; avoid a
  second theme system. Compare against the saved control renders above. Keep
  `deriveStoryMotion(..., enabled)` for its existing eligibility/fallback purpose;
  no new API enum or permanent parallel renderer is needed.
- [x] Preserve a static full cover and still close. Do not stack new effects on
  HookPunch. A source/UI image must fit without cutting off the evidence; label
  reconstructions. Do not add Brag branding, fabricated UI data or audio assets.
- [x] Reuse existing word cues and `storyMusicVolume`. Count already-active
  cues before adding sound. At most one meaningful emphasis action per scene;
  skip a music snap that would move the action away from the spoken fact or
  shorten reading time. No beat detector or continuous audio-reactive layer.
- [x] Run:

  ```bash
  ./node_modules/.bin/tsc --noEmit
  ./node_modules/.bin/tsc --module commonjs --target es2020 --esModuleInterop --skipLibCheck --outDir /tmp/story-motion-check scripts/check-story-motion.ts
  node /tmp/story-motion-check/scripts/check-story-motion.js
  node scripts/check-text-safety.mjs
  ./node_modules/.bin/tsc --module commonjs --target es2020 --esModuleInterop --skipLibCheck --outDir /tmp/contrast-check scripts/check-contrast.ts
  node /tmp/contrast-check/scripts/check-contrast.js
  bash scripts/check-cover-frame.sh
  ```

**Acceptance:** Phone-readable matched previews demonstrate a clearer fact or
mechanism, rather than simply more motion. Existing unsupported layouts retain
their safe renderer. No claimed retention improvement before audience evidence.

## Task 4 — Review artifacts, promotion and measurement

**Modify:** `docs/VOICE_MOTION_REVIEW.md`, `.env.example`, `AI_CONTEXT.md`.
**Inputs:** Tasks 1–3 passing checks and matched preview assets.
**Outputs:** A playable local review set, exact settings, calibration evidence,
rollout/rollback record and a mature-metrics readout when enough data exists.

- [x] Generate half-resolution previews with the existing helper, for example:

  ```bash
  bash scripts/render_preview.sh public/test-editorial-preview.json out/editorial-preview.mp4
  ```

  Produce paired current/proposed files per story using identical final audio,
  words, seed and runtime. Document the comparison switch/settings in the review
  file so another developer can reproduce it without guessing.
- [ ] Inspect frame 0, frame 3, settled text, reveal peak, both sides of cuts and
  final frame. Play muted and with voice/music. Note exact clipping, timing or
  pronunciation problems; resolve them before calling the candidate ready.
- [x] Render the selected candidate once at full resolution with the existing
  Remotion CLI entry point. Keep publishing disabled; do not invoke `post_now.py`
  or `generate_now.py` to test rendering.
- [x] Record the chosen voice/rate/pitch, old settings, pacing mode, calibration,
  commit and rollout boundary. Update docs to distinguish code defaults from
  resolved workflow/repository settings. Do not claim a local change is live.
- [ ] At an authorized rollout, set already-exported rate/pitch repository
  Variables to the chosen values; do not edit the frozen workflow. The workflow
  does not export `VOICEOVER_VOICE`. If another consistent voice wins, update
  the Python consistent narrator default and `test_voice_identity.py`, retaining
  request/env overrides; do not claim a new repository Variable reaches CI.
  Promote voice and visuals in
  separate revisions and record the boundary. If remote configuration is not
  authorized, leave a concrete ready-to-apply settings record and local artifacts.
  `VOICE_PACING=legacy` provides local/process rollback; reverting the pacing
  commit is the rollback if CI does not export that new variable. Do not imply
  that adding a GitHub Variable automatically exports a new environment key.
- [ ] Revert the visual commit if visual QA regresses; disabling story direction
  is not equivalent to restoring the prior story treatment. Retain prior voice
  settings and calibration together
  for audio rollback. Any restored settings must preserve timestamp correctness.
- [ ] Use `python3 growth_report.py --days 30` for age-matched observation after
  rollout. Record revision dates alongside existing series/runtime arms; do not
  add feedback buckets, change ledger dispatch call sites or replace an active
  experiment. Before/after observations cannot isolate a causal effect.
- [ ] Report medians and coverage for absolute watch seconds, views, shares and
  saves under existing exposure floors. Under 20 mature measured posts per arm,
  report insufficient evidence. Missing three-second retention/follows remain
  unknown. Continue audience strategy rather than chasing one low-view post.

**Acceptance:** Review artifacts are accessible, settings and rollback are exact,
and any deployed claim is supported by evidence from that deployment. Voice
preference can be judged locally; reach improvement requires subsequent data.

## Planning self-review

- Voice complaint: Tasks 1–2 isolate delivery, silence and calibration.
- Brag feasibility: design records inspected sources, examples and reuse boundary.
- Visual integration: Task 3 extends existing owners with fallback checks.
- Agent clarity: all three AGENTS files reference this plan and the current limits.
- Measurement and rollback: Task 4 preserves runtime experiments and publishing.
- No task requires a new renderer, paid account, posting refactor or fabricated evidence.

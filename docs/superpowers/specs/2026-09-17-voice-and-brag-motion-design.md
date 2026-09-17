# Voice pace and Brag-inspired motion: design

Date: 2026-09-17. Status: implemented locally after user approval; not deployed.
See [review and measurements](../../VOICE_MOTION_REVIEW.md). The user selected
Aria at +12% after auditions. Evidence below records the pre-change baseline.
User request: investigate Brag, address overly professional/slow narration and
weak results despite fresh news, and first write a plan and update AGENTS files.

## Decision

Keep Remotion and adapt Brag's direction into the existing story-motion layer.
Start with voice and pacing; then compare a focused visual treatment using the
same narration. Deliver local review artifacts before promoting defaults.

| Approach | Benefit | Cost / decision |
| --- | --- | --- |
| Existing renderer + selected Brag techniques | Reuses alignment, rendering and delivery safeguards | Recommended; improve a few scene treatments |
| Hyperframes alongside/replacing Remotion | Direct use of Brag's composition workflow | Second runtime, asset/timing integration and deployment burden; unnecessary here |
| Only speed up TTS | Smallest edit | Does not resolve formal phrasing, long holds or generic visuals; insufficient alone |

## Evidence and limits

- Saved `docs/GROWTH_BASELINE.md`: 56 mature snapshots, median seven views;
  13 sufficiently exposed posts with watch data have median 1.22s average watch.
  No live account audit was performed here. Those numbers support investigating
  early attention, not proving that a particular voice or edit caused low reach.
- `main.py::_generate_voiceover_with_engine`: consistent Jenny at natural pitch,
  default rate +5%, 0.35s tail, `max(int(spoken_sec * 30), 90)` scene refit.
  Workflow also exports +5%; changing only the Python default would not change
  scheduled runs. Actual deployed repository Variables were not inspected.
- Existing `scripts/preview_editorial.py` auditions vary voice/pitch at +5% and
  concatenate three scenes. They do not compare faster rates with real cut gaps.
- Local `public/test-editorial-preview.json`: 19.8s total, per-scene tails around
  0.32–0.35s. An older `props-force-post-385b.json` ends with a three-word,
  three-second scene and a 2.09s post-word hold. This demonstrates the floor's
  possible effect; it does not establish that recent posted reels share it.
- `StoryScene.tsx` and `storyMotion.ts` already provide content-specific layouts,
  compression illustration, literal metric continuity, word cues and ducking.
  `beat.ts` already knows measured tempos. Extend these instead of duplicating.
- No new audio was synthesized or perceptually evaluated in this planning pass.
  Rate/pitch settings alone cannot establish whether narration sounds natural.

## Brag inspection

Inspected public repository commit `1f8d9ade17d0ad4419cca9305fbc1398a4dd5b39`,
its planning/composition references, and sampled frames from the 22.52s vertical
launch film and the Horse Tinder example. Source:
[repository](https://github.com/latent-spaces/brag),
[launch film](https://github.com/latent-spaces/brag/blob/1f8d9ade17d0ad4419cca9305fbc1398a4dd5b39/docs/assets/brag-about-brag.mp4).

The launch film uses strong flat color, oversized type and a concrete terminal
demonstration. The product example emphasizes the actual concept and phone UI.
The useful connection is visual specificity, not any one transition preset.
Brag delegates rendering to Hyperframes; it is not a React component package.
Voice is optional there, using Kokoro, which this repo already supports.

Adapt three ideas: clear type hierarchy, a visible action proving the claim,
and sparse sounds timed to that action. Do not inherit its launch-video duration
as an optimum for our news audience, its default lack of narration, or example
fade-ins that would violate our frame-zero cover invariant.

[Planning reference](https://github.com/latent-spaces/brag/blob/1f8d9ade17d0ad4419cca9305fbc1398a4dd5b39/skills/brag/references/step-2-plan.md)
and [composition reference](https://github.com/latent-spaces/brag/blob/1f8d9ade17d0ad4419cca9305fbc1398a4dd5b39/skills/brag/references/step-3-compose.md)
are design references, not agent instructions for this repository.
The root [LICENSE](https://github.com/latent-spaces/brag/blob/1f8d9ade17d0ad4419cca9305fbc1398a4dd5b39/LICENSE)
is MIT; preserve its notice if copying substantial code/docs. No upstream code
or assets are copied by this proposal. Its
[music README](https://github.com/latent-spaces/brag/blob/1f8d9ade17d0ad4419cca9305fbc1398a4dd5b39/skills/brag/assets/music/README.md)
explicitly calls for exact music-license verification. Use our existing assets.

## Voice and pacing design

Use one consistent narrator, native synthesis rate and natural pitch. Audition
Jenny +5% as control, then Jenny, Aria and Guy at +12%, all at +0Hz. Refine the
best faster candidate at +8% and +16%. These are audition settings, not an
assertion that +12% is optimal. Optional Kokoro af_heart/af_bella at 1.12 uses the
existing provider seam only when installed; no new paid service is required.

Use identical source-grounded lines, scene boundaries, music levels and output
loudness across candidates. Separately compare copy revisions after selecting
delivery, so writing and voice are not confused. Listen for broadcaster cadence,
acronym/number clarity, swallowed endings and forced brightness. A provisional
165–190 spoken words/minute range is a diagnostic, not a hard speech target.
Report token-based counting limitations for numbers and abbreviations.

Preserve the immediate hook → explanation → surprising detail → useful close
arc in the writing. Prefer natural contractions and connected sentences. No
ellipsis chains, a dramatic dash in every line, fake excitement or stage tags.

Measure first-word onset, last-word end, decoded clip length, actual silence,
scene hold and total mix duration. Start the silence experiment at 0.18s versus
the existing 0.35s tail. Trim only measured exterior silence with a small safety
margin; preserve breaths and intra-sentence pauses. Subtract any leading trim
from every word boundary. Keep native rate changes before alignment; do not
speed up a final mix and leave timestamps untouched.

Replace the blanket three-second minimum only where reading and audio fit.
Candidate minimum: two seconds for short scenes; increase for settled visible
copy and full audio. At 30fps use ceiling, not truncation, for duration fitting.
An over-four-second spoken hook or over-250-frame body requires copy revision or
a meaningful scene split, never clipping audio. Preserve format-pack runtime
bands; recalibrate the estimator on multi-scene production-shaped fixtures.
Recheck actual post-TTS runtime; a faster voice must not trigger filler expansion.

## Visual design

Improve eligible body scenes first; existing hook and ending stay structurally
intact. Keep Neon Node branding while borrowing the reference's hierarchy.

1. Statement: large concise consequence plus one source-specific visual.
2. Metric/comparison: a literal value or contrast becomes the main visual event;
   preserve units, conditions and neutral meaning rather than implying a winner.
3. Mechanism: reuse a grounded schematic, or display a verified source/UI capture.
   Label simulations and non-scale diagrams. No fabricated benchmark dashboards.

Prototype source captures as local reviewed assets, not a new autonomous browser
capture service. Use the existing image field for a fixture. If evidence is
unavailable, use a truthful text/metric treatment, not an invented demonstration.

Initial reading floors: short label 0.8s; headline max(1.2s, 0.3s × words) after
settling. These are design heuristics to verify on a phone. If an existing
24-frame transformation cannot fit, skip it. Music may reinforce a nearby cue
but must not shift speech or captions. Avoid per-word musical ticks and new
ambient effects; existing sound/visual events count toward clutter.

## Global constraints

- Keep Remotion; add no renderer, animation dependency or paid TTS requirement.
- Spoken hook at most 12 words; title at most four; hook text at most eight.
- Preserve source grounding, anti-repetition and the builder audience strategy.
- Preserve final post-TTS word alignment, failure guards and provider fallback.
- Preserve frame-zero cover, HookPunch, still ending, contrast and word integrity.
- Preserve seeded draw order and quiz/ranking reveal rules; unsupported scenes fall back.
- Preserve format-pack budgets, any configured runtime experiment and feedback floors.
- Publishing, captions, schedules, tokens and delivery workflows remain frozen.

## Validation and rollout

Produce matched audio files with a timing manifest, then a three-story preview
set: developer-tool action, numerical trade-off, and reliability/security scope.
Compare current versus proposed visuals with identical final audio/seed/script.
Inspect frame zero, reading holds, reveal peaks, cuts, final still and subtitle
clearance; listen on a phone, with and without music. Render one full-resolution
candidate after previews pass. Label previews clearly; never publish via a test.

Promote voice and visuals in separate recorded revisions. Existing exported
repository Variables can select rate/pitch at rollout without a workflow edit;
`VOICEOVER_VOICE` is not exported there. If a different consistent narrator wins,
update the Python consistent-voice default and its identity tests, preserving
explicit request/env precedence. Changing remote configuration is a separate,
concrete deployment action. Save the prior
settings and artifact for rollback. If no candidate fixes delivery, report that
and compare the already-supported Kokoro path before expanding scope.

Use `growth_report.py` age-matched metrics with existing exposure floors. Track
absolute watch seconds, views and saves/shares, plus sample counts. Preserve the
existing experiment assignment; do not silently replace it with a new split.
At least 20 mature measured posts per arm is a minimum evidence gate, not proof
of significance. No runtime tags in the saved baseline means no runtime winner.

# Voice and motion review — 2026-09-17

## October 5 opening repair

### Non-Gemini follow-up: Emma and continuous Edge narration

The owner reports robotic delivery persists when Gemini is not used. The
expressive directions live solely in the Gemini provider. Edge's old consistent
default was Aria, with independent scene requests and only native rate/pitch.
A reproducible later-scene failure also mixed the initial narrator with a
fallback narrator in one reel.

Local repair changes the consistent Edge default and Gemini recovery to Emma
at natural pitch. Explicit request/environment voice, rate and pitch pins still
win; seeded rotation and Gemini Leda selection remain available. Tight
multi-scene Edge narration uses one complete performance, native word boundaries,
strict transcript validation, and PCM cuts in measured quiet intervals of at
least 20ms between scene words. No speech is discarded or sped up. A failed
Edge voice retries every word on the next voice. Missing words, invalid timings
or unsafe cuts fail before rendering. Legacy pacing retains the historical
per-scene path; `VOICE_FLOW=per-scene` also permits a matched tight comparison.
The process-only flow key is not exported by CI; its code default applies.

Matched samples at **+12%, +0Hz, tight**:

| Narration | Voice/flow | Total | Opening |
| --- | --- | --- | --- |
| uv scripts | Aria/per-scene | 20.27s | 3.90s |
| uv scripts | Aria/continuous | 20.30s | 3.90s |
| uv scripts | Emma/continuous | 19.07s | 3.33s |
| Quantization | Emma/continuous | 17.30s | 3.30s |
| npm lockfiles | Emma/continuous | 21.17s | 3.40s |

All Emma scenes fit the opening/body limits, longest body 4.57s; native-derived
captions remain inside the fitted timelines. The 156-word Emma corpus measured
2.798 words/s at +12%, normalized to a +5% estimator reference of 2.62.
Estimated runtime errors were +4.2%, +2.4% and -1.1%, respectively.
Whole-story Aria was essentially unchanged in duration; this comparison does
not establish an audible expressiveness gain from context alone. Emma replaces
the reported robotic narrator, but naturalness still needs human listening.
The free Edge endpoint supports rate/pitch/volume, not emotion/style SSML
([upstream documentation](https://github.com/rany2/edge-tts#custom-ssml)).

Listen at `out/voice-review/edge-flow/index.html`, or play
`public/voiceover-scripts-edge-before.mp3` and
`public/voiceover-scripts-edge-emma.mp3`. The latter is the candidate default.
Artifacts are ignored local files. No remote settings or workflows were changed;
CI's existing rate Variable still wins over the Python +12% default. These are
local previews, not newly published stories or measured reach improvements.

Reproduce:

```bash
python3 scripts/preview_editorial.py --story scripts --voice en-US-AriaNeural --flow per-scene --rate=+12% --label scripts-edge-before
python3 scripts/preview_editorial.py --story scripts --voice en-US-EmmaNeural --flow continuous --rate=+12% --label scripts-edge-emma
python3 -m unittest discover
```

The October 5 opening repair below predates this fallback voice replacement.

Validation: 60 discovered unit tests passed, plus the six required regression
scripts (format packs, feedback scoring, TTS providers, script gate, topic judge
and captions) and TypeScript checking. Audio checks verified all five comparison
mixes and subtitle bounds. Independent review found an audition-matrix flow
override was ignored; it now reaches synthesis and separate comparison files.
AST/file comparison confirms only voice/estimator functions changed in `main.py`
and all protected publishing files remain unchanged. Human listening and
production rollout remain pending.

Rollout authorization: the owner approved deployment of this repair on
October 5. Promote the verified code to `main` for the next normal scheduled
checkout; do not manually dispatch a reel. Existing `TTS_PROVIDER=gemini`
continues selecting Leda when available, with Emma on provider failure;
`TTS_PROVIDER=edge` uses Emma directly. Preserve the existing rate/pitch
Variables and cadence. Readback using the repository owner's configured GitHub
account verified `TTS_PROVIDER=gemini`, `VOICEOVER_RATE=+12%` and
`VOICEOVER_PITCH=+0Hz`; identity/style use the workflow's consistent/cheerful
defaults. The initial HTTP 403 came from a different active GitHub account.
The first scheduled output with this revision still requires log/audio review.

The owner reports green Account Status and authorized the audit's repairs.
Production runs inspected: `37263088838`, `37208876821`, `37128150200`,
`36811633995`. All four published successfully; their metrics sweeps reported
no authentication failures. Three had opening scenes of 5.27s, 5.13s and 6.00s.
The October 5 reel had a 9.77s final scene. Logs explicitly shipped hook-length
warnings after retries; the quiz and ranking prompts contradicted the 12-word
rule. These are reproducible content-pipeline failures, not proof of the cause
of low distribution.

The repair makes opening copy limits hard, aligns conflicting writing budgets,
and checks actual fitted audio before rendering. At most two targeted copy
repairs are allowed; each accepted edit regenerates the full narration and
captions. Assets and scene structure stay fixed. Existing fabrication,
grounding and repetition checks still run, plus conservative preservation of
negation, modality, quantities and scope. This is not a semantic fact checker:
it may reject a valid paraphrase rather than silently weaken a source claim.
Verified quiz/ranking bodies cannot be rewritten by the timing repair. Long
planned visual floors are rejected before synthesis, not clamped under speech.

Gemini now respects `VOICE_IDENTITY=consistent` with Leda; the seven-voice pool
is used only in rotate mode. Explicit voice pins still win. A provider fallback
stays pinned on repair so failed Gemini alignment does not restart paid requests
on each attempt. Kokoro's ledger namespace is removed before provider routing.

Validation: 54 unit tests and nine existing regression scripts passed (script
gate, format packs, experiments, feedback scoring, topic judge/selection/intake,
TTS routing and captions). Independent review identified and verified fixes for
claim-strengthening rewrites, stale sequential-layout floors, and Kokoro retry
routing. The protected dispatch region is byte-identical to the starting code.
No live publishing test was run.

The first live audio probe exposed model edits to unrequested scenes; those
were rejected and the prompt was narrowed to editable scenes only. The final
lockfile fixture passed after two repair requests: **23.27s** total,
**3.30s** opening, longest scene **5.37s**, subtitles within the final timeline.
The second Gemini synthesis failed transcript validation and correctly restarted
the entire narration on Aria +12%. This verifies real timing/fallback behavior;
it does not establish consistent Gemini reliability or perceptual acceptance.
Human listening remains pending.

Local artifacts: `out/retention-review/lockfiles.json`,
`public/test-retention-lockfiles.json`, `public/voiceover-retention-lockfiles.mp3`.
Reproduce with `python3 scripts/preview_retention.py --story lockfiles` using
existing API credentials in the environment. The helper never calls a publishing
entry point. Rollout targets the next normal scheduled run on main; the first
scheduled result and mature audience metrics still need review.

**Follow-up status:** Original work was merged as `41493b3d` and verified in
deployed run `35201843090` (CUDA reel; Aria **+5%** in logs). The user then
approved the expressive Leda audition, then authorized promotion to main and
activation for scheduled reels on 2026-09-17. The first scheduled output with
the new provider and visual-tail refinement still needs review. See the
[follow-up plan](superpowers/plans/2026-09-17-expressive-voice-smooth-cuts.md).

## Expressive Leda and transition follow-up

Playable local artifacts:

- [Matched voice/transition review page](../out/review/expressive-motion.html).
- Exact reaction line: [Leda](../out/voice-review/cuda-leda/3.wav) and
  [Aria +5%](../out/voice-review/cuda-aria/3.wav).
- Full matched narration: [Leda](../public/voiceover-cuda-leda.mp3) and
  [Aria +5%](../public/voiceover-cuda-aria.mp3).
- Motion: [before](../out/review/transitions-before.mp4) and
  [after](../out/review/transitions-after.mp4), identical footage/copy/seed,
  540×960, 270 frames / 9.00 seconds. The boundary at six seconds shows the
  formerly blank frame covered by continuing outgoing footage. Cover and
  final-frame samples retain their compositions; no narration is in this pair.

The user approved the initial [directed Leda audition](../out/voice-review/expressive/leda-directed.wav).
That is preference evidence; the exact CUDA retake and whole mix still need
human listening. The original published CUDA wording is used only as a matched
voice reference, not a newly fact-checked or publication-ready script.

The final five-scene Leda narration passed transcript validation and shared
trim/fitting/mix processing: 23.67s versus Aria +5% at 22.00s. The flagged line
is 3.78s of decoded Leda audio versus 3.48s of Aria. This is an expressiveness
candidate, not a measured speed improvement. Gemini's +12% setting directs a
target pace (about 170 WPM); it is not Edge's native speed control. The existing
duration estimator remains provisional for Leda, and actual audio always refits.

Short standalone requests exposed real failures: added text and incomplete
`OTHER` responses were rejected. The base.en recognizer also hallucinated an
extra word on a quiet tail; the small model recovered the exact speech. Final
implementation synthesizes the whole narration once, then splits PCM only
between measured scene-word intervals. The successful whole-narration audio
was retained and reprocessed after fixing ASR's spaced decimal `8 .0`; no words
were removed to make it pass. Unsupported spelling differences conservatively
fall back. Strict comparison preserves signs, currencies, C++/C# and word
boundaries; it must never turn a contradictory transcript into intended captions.

Failure handling restores original planned durations, removes partial batch
files and restarts the entire video with Edge Aria. A quota failure makes no
further Gemini requests. Provider, resolved voice, rate-control type and fallback
reason are recorded. The preview command calls Gemini directly so fallback
cannot masquerade as an expressive audition.

Verification: 22 voice/alignment/pacing/identity tests, provider tests, full
TypeScript checking, deterministic story and transition checks, text safety,
contrast, and all six cover seeds passed. Batch tests cover one synthesis call,
acoustic splitting and cleanup. Independent review found symbol normalization
and stale fallback metadata issues; both were corrected. AST comparison limits
changed `main.py` functions to the two voice-generation functions; posting paths
and workflow files are unchanged.

Approved activation after code rollout: existing exported `TTS_PROVIDER=gemini`,
existing Gemini key, `VOICEOVER_RATE=+12%`, and `VOICEOVER_PITCH=+0Hz`.
Use repository Variables; no workflow, schedule or billing changes. Chatterbox
is not implemented in this rollout. Gemini's
[speech API](https://ai.google.dev/gemini-api/docs/speech-generation) accepts
delivery instructions; its [free tier](https://ai.google.dev/gemini-api/docs/pricing)
has quotas, and actual billing depends on the existing account tier. CPU alignment
uses the installed faster-whisper package and downloads the small model on first
use. Preview-service failures remain possible; automatic full-video fallback is
part of the implementation, not proof of service reliability or better reach.

Reproduce a local expressive audition with the existing helper (Gemini key
must already be in the environment):

```bash
python3 scripts/preview_editorial.py --story quantization --voice gemini:Leda --rate=+12% --pacing tight --label quantization-leda
python3 -m unittest test_expressive_voice test_voice_identity test_voice_pacing
```

## Original implementation record

The record below describes the original pre-rollout review, retained as history.
Implemented locally on `feat/voice-brag-motion`, based on `e8acdf26`.
This record covers local implementation and validation. Publishing the branch
does not deploy it; no runtime configuration change or posting was performed.
The [plan](superpowers/plans/2026-09-17-voice-and-brag-motion.md) and
[design](superpowers/specs/2026-09-17-voice-and-brag-motion-design.md) remain the
scope reference. The user selected Aria at +12% after listening to auditions. Final mix review
and audience results are pending.

## Playable artifacts

Open [the local review page](../out/voice-review/index.html) for three visual
before/after pairs and six voice auditions. The
[full-resolution candidate](../out/voice-review/quantization-full.mp4) is
1080 × 1920 with existing music and effects. Generated files are ignored local
artifacts, so these links work in this workspace, not a fresh clone.

Each visual pair uses identical final copy, seed 11, duration and narration.
The controls were rendered from the original commit in `/tmp/voice-brag-control`.
Both videos were then muxed with the same narration-only track; decoded audio
hashes match within each pair. Native mixes are preserved as
`*-before-rendered.mp4` and `*-after-rendered.mp4`. This isolates visual changes:
native effect timing can differ when a semantic reveal moves. The full candidate
retains the actual music/effects mix.

## Voice and timing

The user-selected local default is Aria, natural pitch (`+0Hz`), native rate `+12%`.
Request settings still override environment settings, which override defaults.
The user chose this delivery; it is not a claim that a synthetic narrator now
sounds human. No naturalness or pronunciation scores were invented.

Six auditions use the same original copy and legacy scene fitting:

| Voice | Rate | Timeline |
| --- | --- | --- |
| Jenny control | +5% | 21.10s |
| Jenny | +8% | 20.57s |
| Jenny | +12% | 19.93s |
| Jenny | +16% | 19.30s |
| Aria — user selected | +12% | 20.43s |
| Guy | +12% | 20.00s |

Kokoro was unavailable in this environment; no additional engine was installed.
The final hooks were subsequently shortened to fit Aria under four seconds, so
comparing the audition timelines with final renders conflates copy, voice, rate
and timing changes. A separate matched test of the **final** quantization copy
at Aria +12% measured 20.00s with legacy fitting and 19.30s with tight fitting:
0.70s (3.5%) less timeline. Earlier matched Jenny testing removed 0.87s (4.4%).

`voice_pacing.py` trims only exterior silence from decoded PCM. A conservative
-55dB peak threshold and original word boundaries both protect speech; it keeps
60ms headroom and at least 180ms tail where available. The -45dB silence report
is diagnostic only. Internal pauses and playback speed are untouched. Word
timestamps shift by the actual leading trim, and captions and mixing share the
same final scene lengths. Missing, invalid or silent synthesis fails explicitly.

`VOICE_PACING=tight` uses ceiling-rounded audio coverage plus a reading floor
(minimum 60 frames; longer copy adds reading time). Sequential legacy layouts
retain their planned floors. `VOICE_PACING=legacy` preserves the previous
90-frame minimum / 0.35s word-tail fitting. Final Aria preview tails average roughly
0.24–0.25s, including protected acoustic decay. Actual quiet endings were protected in a real PCM regression test.

The estimator now accounts for requested rate and tight/legacy fitting. Aria
calibration is 2.42 words/s at +5%, based on 156 words across three scripts
(2.583 words/s at +12%). Earlier Jenny calibration remains 2.52 at +5% (158 words,
2.680 at +12%). Other voice/provider pools retain their calibration.

| Final script | Estimated | Actual | Error | Hook frames |
| --- | --- | --- | --- | --- |
| Quantization | 19.11s | 19.30s | -1.0% | 117 |
| uv scripts | 21.43s | 20.27s | +5.8% | 117 |
| npm lockfiles | 22.59s | 23.90s | -5.5% | 118 |

Every body scene is below 250 frames. These are small, authored demonstration
fixtures, not validation across all production copy or narrators. Container
duration can include encoder padding beyond the scene timeline.

## Brag adaptation

The existing Remotion scene layer now uses larger focused Geist typography,
full accent surfaces for metrics, paper surfaces for statements, and contrasting
comparison panels. Repeated header/footer furniture, nested decorative framing
and faint stock-image decoration were removed from these body treatments.
Literal metrics and the existing labelled compression schematic carry the proof.
Reveals take 12–24 frames and reserve 24 settled frames afterwards. Late spoken
cues cannot push required reading beyond the scene; unsafe scenes fall back.

No Hyperframes migration, new animation dependency, source-capture service or
Brag audio/code assets were added. Existing sound cues and ducking are reused.
HookPunch, frame-zero composition, final stillness, seed behavior and quiz/ranking
exclusions remain intact. Global writing prompts were retained: the existing
grounded conversational rules already express the requested register.

The three fixtures are evergreen technical demonstrations, not breaking news:
[Transformers quantization](https://huggingface.co/docs/transformers/quantization/overview),
[uv scripts](https://docs.astral.sh/uv/guides/scripts/), and
[npm ci](https://docs.npmjs.com/cli/v11/commands/npm-ci).
The renderer adapts the visual direction researched in the design, not upstream
branding or music whose exact licensing was unverified.

## Validation and remaining review

Passed: 12 voice pacing/identity tests, provider tests, format-pack tests,
script/retention gates, 14 growth tests, TypeScript checking, deterministic story
motion checks, text safety, contrast checks, and cover-frame checks for six seeds.
Real FFmpeg integration checks exercise trimming, mixing, boundary shifts and
cleanup. Sampled frame 0, frame 3, entrances, settled text, reveals, cuts and
endings were visually reviewed across all three paired renders.

Independent code review found audition-path collisions between pacing variants
and incorrect diagnostic indexing for silent scenes. Both were fixed with
regression tests. Protected publishing files were unchanged; AST comparison of
`main.py` found only the estimator, synthesis and estimator call-site changes.

Still pending: listening at phone volume for naturalness, pronunciation and
mix balance; deployment; and sufficiently exposed mature audience observations.
The existing bounded **pre-TTS** script revision path is preserved. No new
post-TTS LLM rewrite loop was added. Preview hooks fit; unseen production copy
still needs actual-duration review. Never clip speech to satisfy a hook target.

## Reproduce locally

```bash
python3 scripts/preview_editorial.py --auditions --pacing legacy
python3 scripts/preview_editorial.py --story quantization --label quantization-aria-tight --rate=+12% --pacing tight
python3 scripts/preview_editorial.py --story scripts --label scripts-aria-tight --rate=+12% --pacing tight
python3 scripts/preview_editorial.py --story lockfiles --label lockfiles-aria-tight --rate=+12% --pacing tight
python3 scripts/measure_spoken_rate.py --timings out/voice-review/quantization-aria-tight/timing.json --timings out/voice-review/scripts-aria-tight/timing.json --timings out/voice-review/lockfiles-aria-tight/timing.json
./node_modules/.bin/remotion render src/remotion/index.ts MyComp out/voice-review/quantization-after.mp4 --props=public/test-quantization-aria-tight.json --scale=0.5 --concurrency=2 --overwrite
python3 scripts/preview_editorial.py --report
```

Repeat rendering for the other two props files. Render the same props with the
original commit for controls; do not disable story direction as a substitute.
The full-resolution file uses `public/test-quantization-aria-music.json` (tight props
with the existing `ambient-tech` music). Omit `--scale` for full resolution.
To isolate visuals after rendering, replace both pair tracks with the same
`public/voiceover-<story>-aria-tight.mp3`, pad to the exact scene timeline and preserve
the native render files. Rerunning auditions now uses the current fixture copy;
the table above records the original session's retained samples.

## Rollout boundary and measurement

Python defaults changed locally; **the frozen workflow still explicitly exports
`VOICEOVER_RATE=+5%`** unless its existing repository Variable overrides it.
Remote Variables were not inspected or changed. A future authorized rollout can
set the already-exported rate Variable to `+12%`, with pitch `+0Hz`, after voice
review. Do not infer deployed settings from local defaults.

The workflow does not export `VOICE_PACING` or `VOICEOVER_VOICE`. Adding a new
repository Variable alone will not reach the process. For a local rollback use
`VOICEOVER_VOICE=en-US-JennyNeural VOICEOVER_RATE=+5% VOICE_PACING=legacy`;
for CI rollback revert the narrator default, timing and calibration changes
together if those keys are not exported. Restore the original
visual diff to roll back visuals; disabling story direction selects a different
older renderer. Keep voice and visual promotion boundaries separate for review.

The saved-data baseline command was:
`python3 growth_report.py --as-of 2026-09-16T00:00:00Z --days 30`.
The local ledger yielded 154 entries, 66 eligible posts, 57 mature snapshots,
median seven views; watch median 1.22s (n=13), shares/saves per 1,000 reached medians zero (n=12),
and 44 snapshots below the exposure floor. No live account fetch occurred.
Continue the existing builder-audience strategy and runtime experiment rules.
Fewer than 20 mature measured posts per arm is insufficient evidence; missing
retention/follow metrics remain unknown. Faster voice and clearer visuals are
testable improvements, not evidence of increased reach.

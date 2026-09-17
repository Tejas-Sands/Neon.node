# Voice and motion review — 2026-09-17

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

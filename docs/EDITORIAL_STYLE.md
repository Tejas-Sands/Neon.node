# Neon Node: editorial motion and voice

Implemented direction, September 2026. This is a production-quality hypothesis,
not a claim of increased views. Compare mature post metrics separately.

## Typography

Three roles, not a random font catalogue:

- **Geist 700 / 500:** portrait headlines, numbers and captions.
- **Newsreader 600:** directed statement headlines, sentence case.
- **JetBrains Mono 500:** technical labels and schematic annotations.

Existing Space Grotesk brand chrome remains stable. Old fonts remain loadable;
the new families are render-internal, not new backend schema enum values.
Only the required Latin weights load via the installed Remotion font package.
Portrait compositions adopt Geist; landscape/square retain their requested font.

Research shortlist (alternatives, NOT fifteen installed rotating fonts):

| Family | Intended role |
| --- | --- |
| Satoshi | Polished primary headlines |
| Geist Sans | Precise technology identity — selected |
| General Sans | Restrained headlines |
| Switzer | Quiet editorial supporting text |
| Manrope | Approachable explainers |
| Instrument Sans | Editorial supporting text |
| Plus Jakarta Sans | Conversational explainers |
| Space Grotesk | Existing brand chrome |
| Cabinet Grotesk | Expressive oversized hooks |
| Clash Display | Short display headlines |
| Newsreader | Analytical headlines — selected |
| Fraunces | Occasional expressive serif |
| Instrument Serif | Large editorial accents only |
| IBM Plex Sans | Technical explanations |
| JetBrains Mono | Code and technical labels — selected |

No proprietary Fontshare files are bundled. Their current license permits
commercial video but restricts font redistribution and third-party content
generation services: https://www.fontshare.com/licenses/itf-ffl.
Selected specimens: https://vercel.com/font,
https://fonts.google.com/specimen/Newsreader,
https://www.jetbrains.com/lp/mono/.

## Motion

- Tall portrait (height/width >= 1.5): paper-and-ink statement, metric and
  comparison panels; dark compression diagrams. Text has an arrival and an
  exact reading hold, followed by a 24-frame voice-cued transformation.
- Compression depicts the explicit claim with labelled, not-to-scale blocks.
  It is not a benchmark and never infers numerical savings.
- A literal metric repeated in the following non-metric scene can dock into
  a context chip over the last 18 frames. Units/signs must match exactly.
- No changes to HookPunch, the energy schedule, final-scene renderer, quiz
  answers, rankings, native word timings or protected publishing behaviour.
- Long titles/labels, oversized copy, unsupported scene types and shorter
  aspect ratios retain the existing renderer. No new background-video fetches.

## Voice

Default Edge narrator: Jenny, +5% rate, natural +0Hz pitch. One identity across
sessions; existing sticky failover remains available on speech-service errors.
The writing arc is immediate hook → grounded explanation → strongest emphasis
on the surprising fact → composed payoff. One honest reaction, no hype or
spoken acting tags. Punctuation influences phrasing, not guaranteed emotion.

Request voice/pitch overrides beat environment overrides; both beat defaults.
`VOICE_IDENTITY=rotate` restores the old seeded Edge voice/pitch profile.
`VOICE_STYLE=legacy` keeps the legacy voice-selection/prompt escape hatch.
CI exports the identity variable; default-on requires no new secret or service.
Kokoro remains optional and is not enabled by this change.

## Preview and verification

`python3 scripts/preview_editorial.py` synthesizes a local-only narrated fixture
and three matched auditions; it NEVER calls generation or publishing endpoints.
Its quantization explanation is based on
https://huggingface.co/docs/transformers/quantization/overview.
The old 40% fixture remains a labelled synthetic test, not a real benchmark.

Render: `scripts/render_preview.sh public/test-editorial-preview.json out/editorial-preview.mp4`.
Voice samples: `public/voiceover-audition-{current-lift,natural-jenny,natural-aria}.mp3`.
Audio and preview props are ignored; regenerate them instead of committing.

Checks: `python3 -m unittest test_voice_identity`, `python3 test_tts_providers.py`,
`node_modules/.bin/tsc --noEmit`, `node scripts/check-text-safety.mjs`,
the pure `scripts/check-story-motion.ts` assertions, and `scripts/check-cover-frame.sh`.
Re-measure speech timing with `scripts/measure_spoken_rate.py`; use
`VOICE_IDENTITY=rotate` for the old-pool comparison on the same corpus.
September 16 calibration: Jenny at +0Hz/+5% measured 3.291 effective words/sec
over 12 scenes (219 words). The corpus-relative production estimate is 2.43,
within 1% of the existing 2.45 constant, so the timing gate stays unchanged.

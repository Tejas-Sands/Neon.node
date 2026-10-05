# Everyday tech and science — October 5, 2026

## Authorized scope

The owner requested broader stories, visible proof, and improved animation,
then confirmed everyday tech and science. Extend the existing intake, editorial
judge, script gate and Remotion scenes. Keep publishing, captions, schedules,
voice rollout settings, runtime experiments and feedback floors unchanged.

## Changes

- Default audience preference is `everyday-v1`: protect-yourself, daily-life,
  world-explained. `builders-v1` remains an explicit option; `off` remains off.
- Read public NASA, FTC and Google RSS alongside the existing sources. Their
  feeds returned HTTP 200 with the generator user agent on October 5. FTC's
  nested title anchors and encoded article links need normalization.
- Broader subjects search their actual domain. An automatic everyday job with
  no sourced image gets a neutral background, never an unrelated fantasy photo.
- The judge can provide a short complete literal source sentence. Validation
  checks the available article, word/character bounds, punctuation and uncertain
  abbreviation endings. The first body scene retains an accepted quote exactly.
  This is a conservative string check, not semantic verification of the entire
  article or of a quote's broader context. The editorial grounding still matters.
- Attributed source excerpts receive a paper surface and one timed highlight.
  Legacy split fallback also shows attribution. Comparisons retain both values
  while the second panel settles. Simulated UI visibly says ILLUSTRATION.
- Opening title and consequence are larger, solid, fully present at frame zero;
  shared stack fitting reserves subtitle space. HookPunch, final stillness and
  narration/caption times are preserved. Quiz/ranking bodies remain excluded.
- Active pill captions choose dark or light ink to match their accent fill;
  the preview exposed low contrast from white text on the yellow pill.
- Historical report classification uses its original strategy. The new audience
  tag does not overwrite the runtime experiment or create a feedback bucket.

## Source examples inspected

- [FTC parking QR advisory](https://consumer.ftc.gov/consumer-alerts/2026/09/see-qr-code-parked-somewhere-dont-scan-ityet):
  a practical example about fraudulent stickers and checking the destination.
  September 3 advisory; local preview only, not eligible as a fresh October pick.
- [Google Android changes](https://blog.google/products-and-platforms/platforms/android/Android-Drop-September-2026/):
  everyday functionality with explicit device/region/rollout limitations.
- [NASA rainbow explanation](https://science.nasa.gov/image-article/apod-2026-october-4-supernumerary-rainbows-over-new-jersey/):
  a new October feature discussing a 2018 photograph. Explain the phenomenon;
  do not call it a newly occurring event. The photograph carries third-party
  copyright and was not copied into the preview.

## Local review and limits

Python modules compile and TypeScript compilation passed during development.
An independent read-only review found quote truncation, unsafe imagery fallback
and lost source attribution on short scenes; those paths were corrected.
No automated tests were added or run for this change. Earlier retention test
results belong to the previous commit, not this update.

`scripts/preview_everyday.py` creates narration, aligned captions and props only;
it contains no posting call. Generated artifacts live under `out/everyday-review`
and `public/test-everyday-qr.json`; they are not checked into the repository.
The narration report identifies the actual resolved voice and timing. Human
listening and mature scheduled audience results remain pending.

The Leda preview completed with no repair or fallback: 20.47 seconds, a 2.63s
opening and a 6.63s longest scene. The local video is
`out/everyday-review/qr.mp4`. Sampled cover, source-card reading/reveal,
comparison and closing frames were inspected at phone size. This authored
example is not evidence of quality across every automatically selected topic.

This adds literal source evidence, not an autonomous browser capture service.
Actual product demonstrations still require authentic recordings or captures.
Some source articles do not contain a useful complete sentence under 15 words;
absence falls back to grounded explanation rather than a manufactured quote.

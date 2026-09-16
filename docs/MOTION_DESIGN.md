# Story-directed motion — September 2026

The scheduled `MyComp` renderer now uses three body-scene visual families:
editorial typography, data/comparison, and a compression schematic. This is
default-on for eligible portrait scenes; it needs no workflow variable or
new backend field. A scheduled job must check out the commit containing this
change before it can use it. Already-rendered videos are unaffected.

## What changes

- Short `split`/unspecified body scenes become large, left-aligned editorial
  compositions. Photographs provide a quiet context plane instead of carrying
  the whole frame. Existing colors and loaded font families remain available.
- `metric` scenes display the supplied value verbatim at a larger scale. No
  counting through intermediate values and no invented chart or benchmark.
- `comparison` scenes use stacked, readable panels. Only supplied labels are
  shown; the renderer no longer presumes the second side is a factual winner.
- An explicit, non-negated compression/quantization claim involving memory,
  weights, a model, storage or data can animate packing blocks. This is labelled
  **COMPRESSION SCHEMATIC · NOT TO SCALE**. It illustrates compression, not the
  implementation of a particular algorithm or a measured compression ratio.
- Adjacent directed scenes with the same leading subject keep their subject
  tab in the same location and use a hard match cut. Other cut plans are intact.
- Visual emphasis and a single restrained sound accent align to a matching
  narrated word when one falls in the safe kinetic window. Facts stay readable
  from scene entry. No suitable timestamp means the existing kinetic-window
  fallback, not fabricated timing. Music dips around that emphasis.
- Directed scenes reserve the existing bottom caption band and suppress the
  decorative HUD. Caption position, word grouping, timestamps and text are
  unchanged.

## Preserved contracts and limits

Scene 0/HookPunch, the closing scene, quiz/ranking packs, countdowns, charts,
lists, product demos, non-portrait formats, and overly long copy retain their
existing renderers. The still-ending and loop-ending contracts are unchanged.
No schema, prompt, Python, posting, workflow, dependency, or asset changes.
No new random draws, clocks, network calls or heavy image filters.

`storyMotion.ts` is deliberately a precision-first English heuristic, not a
technical-storyboard generator. Unsupported topics get typography, not guessed
dependency graphs, made-up product UIs, or invented mechanisms. Full shared-object
morph sequences and bespoke 3D are future art-direction work, not shipped here.
Do not infer audience growth or virality from visual changes alone.

## Verification

```sh
node_modules/.bin/tsc --noEmit
node_modules/.bin/tsc --module commonjs --target es2020 --esModuleInterop --skipLibCheck --outDir /tmp/story-motion-check scripts/check-story-motion.ts scripts/check-contrast.ts
node /tmp/story-motion-check/scripts/check-story-motion.js
node /tmp/story-motion-check/scripts/check-contrast.js
node scripts/check-text-safety.mjs
bash scripts/check-cover-frame.sh tests/fixtures/story-motion.json
node_modules/.bin/remotion render src/remotion/index.ts MyComp /tmp/story-motion-preview.mp4 --props=tests/fixtures/story-motion.json --scale=0.4 --concurrency=2
```

The fixture is synthetic and explicitly labels its metric as a test value.
It does not contact TTS or publish anything. Inspect opening frame 0, compression
before/after frames 190/235, metric frame 380, the shared cut at 269/270,
comparison frame 550, and the final hold. Use a real saved props file as a second
compatibility check. Frame 235 should be byte-identical across repeated renders.

Regression assertions cover eligibility, negative contractions, exact-number
cue matching, scene-local timing, reading windows, long-word fit, literal subject
continuity, deterministic/still progress and the music dip. Keep these alongside
the existing contrast, caption-safety and cover tests.

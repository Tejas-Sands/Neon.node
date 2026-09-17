# AGENTS.md — MyComp Component Layer: Precision Craft Rules

> **Scope**: Everything inside `src/remotion/MyComp/`. Read alongside both parent `AGENTS.md` files.
> This file governs the *implementation precision* of each component — the micro-decisions that
> distinguish a video that feels "generated" from one that feels "produced."

---

## CURRENT IMPLEMENTATION MAP — Brag fusion (2026-09-17)

The root [plan](../../../docs/superpowers/plans/2026-09-17-voice-and-brag-motion.md)
and [review record](../../../docs/VOICE_MOTION_REVIEW.md) describe the local
implementation and rendered checks. No deployment has occurred. Narration is
Aria at +12% by user selection; always use its newly measured timestamps.

| Existing owner | Responsibility for the adaptation |
| --- | --- |
| `storyMotion.ts` | Scene eligibility, word cues, reading windows, literal continuity and safe fallback |
| `StoryScene.tsx` | Large focused type, evidence framing, meaningful transformations; use existing kinds first |
| `Main.tsx` | Compose the existing layers, captions and local audio; avoid duplicate overlays/SFX |
| `AnimatedText.tsx` / `fitStack.ts` | Word integrity, fitting and settled readable text |
| `energy.ts` / `SceneTransition.tsx` | Existing hook, kinetic-window, cover and still-ending guarantees |

- Current story direction excludes hook/final scenes, quiz/ranking packs,
  unsupported/oversized copy and insufficient timing windows. Preserve these
  fallbacks; reveals use 12–24 frames and leave at least 24 settled frames.
- Reuse statement/metric/comparison/compression before creating a new kind.
  A new literal metric relationship must include the unit/sign. A schematic
  must not imply an unverified measured ratio, benchmark or product interaction.
- Read timing from final post-TTS durations. Never retime captions independently
  of audio; never put narration on the beat grid. Existing `synced` means an
  actual matched timestamp, not a guessed position.
- At most one new emphasis action per scene. Existing micro-details, SFX and
  match cuts count when judging clutter; adding another layer is not the goal.
- Required review: frame 0, settled text, reveal peak, both sides of each cut,
  final frame, muted playback and voice-first playback at phone size. Use the
  existing story-motion, text-safety, contrast and cover checks after changes.

---

## THE PRIME DIRECTIVE

> **Every frame a stranger could pause on must look designed.**
> (From `ANIMATION_BRIEF.md` Q2: "layered composition — multiple planes, depth.")

This is the practical test for every component in this directory: pause the video on a random frame, screenshot it, and ask: does this look like a deliberate design decision, or does it look like a software artifact?

---

## MAIN.TSX — The Scene Orchestrator

### The HookPunch — Do Not Weaken

```tsx
// Peak at frame 3, not frame 0 — frame 0 is the thumbnail cover.
// Residual 0.10 at frame 0 is intentional: faint brand bloom on the still.
const flash = interpolate(frame, [0, 3, 6, 16], [0.1, 0.85, 0.45, 0], {...})
```

The `HookPunch` is the visual equivalent of the first 3 words of voiceover. It is intentionally louder than everything else in the video. Do not smooth it out, reduce its opacity, or delay it. The only valid reason to change it is if a new hook mechanism is demonstrably better at stopping the scroll.

### accentPlan Override — How to Use It

The `look.accentPlan` field controls per-scene accent colour:
- `"fixed"`: all scenes use `theme.primaryColor` — consistent, good for brand
- `"cycle"`: even scenes = primary, odd = secondary — creates energy, "something different happened"
- `"mono"`: each scene gets one rotating accent from `[primary, secondary, palette.primarySoft]`; media desaturates to `saturate(0.25)` — editorial, premium

**For breaking news / urgent content**: `"cycle"` creates a sense of escalation that matches the content arc.
**For analytical / explainer content**: `"mono"` makes the accent feel like a system, not decoration.

### The Text Stack Fit System — Don't Fight It

`fitStackScale` and `stackHeightAt` in `fitStack.ts` exist to prevent text from covering the caption band. The flow is:
1. Try placing the stack at the natural anchor (`heroTop`)
2. If it overflows, RAISE the anchor (move the block up) — never shrink type first
3. Only shrink type if it still overflows from the highest allowed anchor

**COMPREHENSION FIRST**: Moving the block up preserves type size. Shrinking type size to fit a bad anchor is the wrong tradeoff. Don't add code that bypasses `fitStackScale`.

### Camera Motion Selection — Hash, Not Random

```tsx
const hash = ((seed + textLen + titleLen + sceneIndex * 17) >>> 0) % motionOptions.length;
const motionType = motionOptions[hash];
```

Camera motion is deterministic per-scene, varying within the look's `cameraPool`. The pool is personality-scoped (calm videos drift slowly, snappy ones cut with energy). Adding new camera motions: append to the relevant pool arrays in `looks.ts`, not to this hash.

### enterPunch — The Text-Reacts-to-Cut Feature

When a punch-in connector leads the cut (dressed transition), `enterPunch=true` triggers a 3.5% sympathetic scale on the text plane over 7 frames. This makes text feel like it *exists in space* — the camera punch and the text plane move different amounts, creating genuine depth (Q2d: "layered composition").

**Scene 0 is always exempt** — hook readability is frame-critical and a punch-in on the very first scene reads as a stutter.

---

## ANIMATEDTEXT.TSX — The Typography Engine

### The Word-Fit Cap — Sacred, Do Not Remove

AnimatedText enforces a word-fit cap: font size is reduced before a word splits across lines. This is **Pain Point 6** in `AI_CONTEXT.md`. Never add `flexWrap: "wrap"`, `overflowWrap: "break-word"`, or per-letter `<span>` elements inside wrapping flex containers. The word-split bug is permanently banned.

### Animation Modes and Their Retention Properties

When implementing a new animation mode, follow this discipline:

**Text must be legible at frame 3** (the HookPunch peak). If a mode starts text fully invisible (opacity 0) and takes more than 3 frames to become legible, it cannot be used as the default pool mode for the hook scene. It can be used for body scenes.

**The "cinematic discipline" modes** (`rise-mask`, `clip-wipe`, `line-stagger`, `tracking-in`, `elastic-rise`, `flip-in`, `pop-cascade`) are render-side only — not in the Zod schema enum. This is intentional: these are motion identity choices that the render layer makes, not the backend.

### Adding a New Text Animation

Checklist:
- [ ] Named clearly in the `TEXT_ANIM_POOLS` type union
- [ ] Has a clear temporal home (when does animation complete? what's the settling frame?)
- [ ] Does NOT use `filter: blur()` on individual letter spans (performance)
- [ ] Does NOT use `overflowWrap: "break-word"` (Pain Point 6)
- [ ] Is legible at frame 3 (or is not eligible for hook-scene pools)
- [ ] Appended to at least one new pool pair in `TEXT_ANIM_POOLS` in `Main.tsx` (after all existing pairs)

---

## ENERGY.TS — Schedule, Not Level

The `deriveEnergy` function is the *conductor* of the entire video. Every other component listens to it. Rules:

### The Energy Shape Contract

```
Scene 0 (hook):  level 0.52-0.65, camera 0.9 — calmer than body, type lands clean
Body scenes:     level 0.62-1.0, guaranteed spike per triple (≥0.80)
Final scene:     level 0.0, camera 0.0, still=true — dead locked-off close
```

**Do not raise the hook energy floor above 0.65.** The brief is explicit: Q19b answer was "calmer hook, let the type land clean." The hook's visual impact comes from HookPunch + text animation, not camera intensity.

**Do not lower the body floor below 0.62.** The "flat medium hum" read was the reason the floor was raised from 0.55 to 0.62 in the 2026-08-09 retention pass.

### epochLevelOffset — The Dial for Batch Mood

The optional `epochLevelOffset` parameter is a batch-level nudge (±0.04) so a whole publishing era can run slightly calmer or livelier without reshuffling individual video seeds. Use it from the backend (`main.py`) to adjust the energy feel of an entire publishing run. Never use it per-video (that defeats the seed determinism).

### Draw Discipline — Fixed Draws Before Any Gate

The comment in the source is load-bearing:
```ts
// Fixed draws per scene — consumed even where a role overrides the value.
const levelRoll = rng();
const cutRoll = rng();
```

If you add a new roll to this loop, it must be drawn **before** any `if (isHook)` / `if (isStill)` branches that might skip it. Otherwise seeds added before your roll change what values scenes after them receive. This is the same discipline as `polish.ts`.

---

## MICRODETAILS.TS — The Craft Signal System

### How to Add a New Micro-Detail

1. Add the new type literal to the `MicroDetail` union
2. Add it to `ALL_DETAILS` (after existing entries — reshuffles which pair seeds land on; sanctioned)
3. If it has an eligibility gate (requires a specific feature to be enabled), add the gate to the `eligible` filter
4. Draw count stays FOUR — do not add more draws to `deriveMicroDetails`
5. Implement the visual in the component that owns the temporal home for that detail
6. Document the temporal home in the block comment at the top of `microDetails.ts`

### Temporal Home Assignment — The Most Important Rule

Two active details must never animate the same frames. Current homes:
- Landing beat (frames 0-landEnd): `hairline-draw`, `landing-pop`
- Kinetic window (kineticStart+): `emphasis-sweep`
- Cut boundaries (±2 frames): `cut-fringe`
- Ambient (all frames): `grain-breath`
- Scene entries: `progress-comet`
- Cross-scene/continuous: `accent-dot`
- 6 frames before dressed cut: `edge-tease`
- Active subtitle word: `word-pulse`

A new detail needs a temporal home that doesn't overlap with the above.

---

## LOOKS.TS — The Visual Identity System

### The deriveLook RNG Discipline

```ts
// New draws in deriveLook must be appended AFTER all existing draws
// or every seed's look reshuffles. — CLAUDE.md Rule 2
```

This is the most dangerous footgun in the entire codebase. If you add a new `rng()` draw in `deriveLook` and it appears before an existing draw in the function body, every single seed that has ever been used will produce a different visual identity. This is not recoverable without a migration.

**Appending new draws at the end of `deriveLook`** means only seeds whose integer division mod the new field's count changes will see a new look — and even then, only that field changes, not all of them.

### cameraPool — Personality-Scoped Motion

Each motion personality has a curated `cameraPool` that expresses that personality:
- `"calm"`: gentle drifts, no rotations
- `"editorial"`: static + pan, editorial discipline
- `"snappy"`: dynamic-zoom-rotate, vertigo, punch
- `"cinematic"`: ken-burns, orbit-drift, zoom-slow

When adding a new camera motion, assign it to the appropriate personality pools. Do not add every motion to every pool — the personality system exists precisely so videos have motion identity.

### titleTreatment — Four Modes, Each with a Distinct Role

| Treatment | When to use | Retention effect |
|---|---|---|
| `"solid"` | Default, any content | Clean, readable |
| `"outline"` | Over busy backgrounds | Legible without obscuring image |
| `"gradient-fill"` | Premium/product content | Feels expensive, brand-forward |
| `"boxed"` | Stats, emphasis moments | Scans instantly, feels editorial |

The `"boxed"` treatment is particularly powerful for stat/metric scenes — the box draws the eye immediately, so the viewer reads the number before the voiceover speaks it.

---

## SCENETRANSITION.TSX — Cuts as Narrative Punctuation

### The Transition Emotion Map

Transitions should mirror the emotional transition between scenes, not just look cool:

| Emotional transition | Best transition type | Why |
|---|---|---|
| Escalation (things got bigger) | `zoom-through`, `iris-open` | Camera moves toward the reveal |
| Pivot (new angle entirely) | `wipe-down`, `slide-left` | Visual break signals topic shift |
| Continuation (same point, more detail) | `blur-dissolve`, `crossfade` | Smooth = same thread |
| Urgency / Breaking | `glitch-cut`, `spin-blur` | Disruption = this matters |
| Payoff / Conclusion | `push-up`, `crossfade` | Clean arrival = closure |

### The Hook-to-Body Cut (Scene 0 → Scene 1)

This is the second most important visual moment in the video. The viewer made it past the hook — now they need to feel like they're moving TOWARD the answer. Prefer:
- `zoom-through`: commitment, moving into the story
- `push-up`: information arriving
- `iris-open`: reveal happening

The `crossfade` here reads as "more of the same" — it doesn't signal escalation.

### Dressed Transition Frequency

Current contract: one "signature" transition + one "accent" per video; at most every 3rd boundary gets a dressed transition. **Do not dress every cut.** The contrast between hard cuts and dressed transitions is what gives dressed transitions their impact. Over-dressed = the viewer stops reading the transitions as meaningful.

---

## VIDEOFX.TSX — The Premium Details Library

Components in this file are the "proof of production" layer — the elements that make a viewer think "someone made this deliberately":

### Usage Discipline

- **`ParticleBurst`**: Use only on HookPunch (scene 0) and major reveal moments. Not ambient.
- **`DrawnUnderline`**: Use on emphasis words in stat/metric scenes. One per scene maximum.
- **`AnimatedCheck`** / **`AnimatedCursor`**: Use for `ui-demo` scene type only.
- **`BarChart`** / **`DonutChart`** / **`LineChart`**: Only with real numbers from the topic brief. Never invent chart values.
- **`LoadingSpinner`**: `ui-demo` and `metric` scenes with countdown only.
- **`ClickRipple`**: `ui-demo` only, on the simulated button click.
- **`GlassCard`**: For `testimonial` and `split` scenes where a quoted element needs a premium container.
- **`StarRating`**: `rating` scene type only, with real `ratingValue`.

### The "One Premium Detail Per Scene" Rule

Each scene should have at most one `VideoFX` component active. Two premium details competing for attention cancel each other out. Decide which is the *main event* of the scene and let the others be secondary.

---

## CONTRAST.TS — The Legibility Floor

### The Contract

`deriveContrastBudget` solves a single constraint: **the text must be readable.** It returns `brightnessLift` which tells `gradeFilter` how much it can raise the background brightness before text legibility is at risk.

Key invariant:
- The budget is solved for the VIDEO'S WORST CASE, not per-scene
- This means `prismStrength` uses `1` (poster scene) even when computing body scenes
- This is intentional: a stepping brightness between scenes would be more disorienting than a slightly darker body scene

**Do not modify `contrastBudget` to be per-scene.** The legibility floor is non-negotiable.

### The Scrim/Plate System

Plates (`split` framing, card framing, bottom scrim) are the mechanism by which backgrounds can be brighter without sacrificing text legibility. If content quality improvements require a brighter, more colorful background (Q32a from the brief), the path is:
1. Add a stronger plate/scrim over the text area
2. Raise `brightnessLift` for the photo outside the plate
3. NOT: remove the plate and hope the contrast holds

---

## POLISHLAYERS.TSX — The Finishing Touches

### CutCover

`CutCover` fires for 3 frames centered on each cut. Its job is to make cuts feel like a camera flash, not a software splice. The `cut-fringe` micro-detail (±2 frames chromatic fringe) layers inside it.

**Do not extend CutCover beyond 3 frames.** A longer flash draws attention to the edit rather than smoothing it.

### PolishStack (FilmGrain + Bloom + Scanlines)

The grain breathes — `grain-breath` micro-detail controls whether it oscillates. On `energy.still = true` (final scene), grain is frozen. This is correct: a still frame with animated grain reads as restless, not calm.

### The `energy.still` Gate

When `energy.still = true`:
- `PolishStack` grain pulse: frozen
- `ShapeAccents`: frozen
- All `micro-detail` animations: frozen
- Camera: locked (handled in `Main.tsx`)

These four gates must ALL be respected by any new component that has animated behavior. Check `energy.still` before animating anything in the final scene.

---

## QUICK REFERENCE — Determinism Checklist

Every component in this directory must pass these checks:

| Check | Requirement |
|---|---|
| No `Math.random()` | Use `makeRng(seed ^ CONSTANT)` — unique constant per component |
| No `Date.now()` | Remotion renders out-of-order; time-based values flicker |
| No `useEffect` for animation state | All values must be derivable from `frame` alone |
| Fixed draw count before gates | All RNG draws happen before any `if` branching |
| Energy-aware | Animations gated by `energy.landEnd` and `energy.still` |
| Contrast-safe | Text-adjacent elements checked against `contrastBudget` |
| No word-splitting | No `flexWrap: "wrap"` on text containers, no `break-word` |

# AGENTS.md — Remotion Render Layer: Motion as a Retention Weapon

> **Scope**: Everything inside `src/remotion/`. Read alongside the root `AGENTS.md`.
> The root file owns *what to say*. This file owns *how the motion supports what's being said*.
> Motion that competes with content loses. Motion that *amplifies* content wins.

---

## CURRENT DIRECTION — Brag reference (2026-09-17)

Read the root [design](../../docs/superpowers/specs/2026-09-17-voice-and-brag-motion-design.md)
and [plan](../../docs/superpowers/plans/2026-09-17-voice-and-brag-motion.md).
The adaptation is implemented and rendered locally inside Remotion. Read the
[review record](../../docs/VOICE_MOTION_REVIEW.md); deployment and audience
validation remain pending. The user selected Aria at +12% for narration.

- Extend existing `MyComp/StoryScene.tsx` and `MyComp/storyMotion.ts` first.
  They already implement statement/metric/comparison/compression direction,
  word-timed reveals, literal metric continuity and music ducking.
- The target is one dominant readable idea and one meaningful action per scene:
  a fact lands, an actual UI result appears, or a supported comparison resolves.
  Source captures are evidence only when verified; recreations need a visible
  illustration label. Stock footage is atmosphere, never proof.
- Use fast entrances followed by settled reading time. Initial design budgets:
  0.8s for a short label; max(1.2s, 0.3s × word count) for a required headline.
  These are preview acceptance heuristics, not platform ranking facts. If they
  do not fit, reduce copy or use the existing layout; never hide speech to fit.
- Voice timestamps own narration/caption timing. Existing measured music cues
  may support a reveal only when they preserve comprehension. Do not introduce
  a beat detector, GSAP, another renderer, or new animation enums for this pass.
- Preserve existing visual identity and seed draw order. Compare old/new
  treatments with identical words, seed and audio before changing defaults.
- Keep frame 0 fully composed, HookPunch active, subtitle clearance intact and
  the final scene still. No autoplay/browser timers or nondeterministic state.
- Claims such as HIGH retention impact in older tables are creative intentions,
  not measured outcomes. Inspect rendered frames and mature audience metrics.

---

## THE CORE PRINCIPLE

> **Comprehension is the objective. Kinetics is the instrument.**

Every motion decision asks the same question: **does this make the viewer understand faster, feel more, and stay longer?** If the answer is "no" or "maybe", don't add the motion.

The organizing principle from `ANIMATION_BRIEF.md` (2026-07-26) applies everywhere:
- **Kinetic between reading moments, calm while the headline lands.**
- **Energy is a schedule, not a level.** The hook scene is calmer than body scenes so the first title lands clean.
- **The final scene is dead still.** A locked-off close on a kinetic feed reads as confident and deliberate — not lazy.

---

## THE HOOK SCENE — Scene 0 Visual Requirements

Scene 0 (`hero` type) is where the algorithm decides whether to show this video to more people. **The visual system already has the right tools; this section tells you how to use them for maximum scroll-stop.**

### What's Already Implemented and Must Remain Active

**`HookPunch` component** (first 42 frames of scene 0):
- Radial gradient burst peaking at frame 3 (not frame 0 — frame 0 is the cover thumbnail)
- Expanding shock ring: `scale(0.15 → 2.4)` over 20 frames, fading out
- `ParticleBurst`: 22 seeded particles in primary/secondary/white, `maxRadius: 55%`
- Mix blend mode `"screen"` — additive on dark backgrounds, invisible on bright ones

**DO NOT weaken this.** The peak sits at frame 3 intentionally — the frame-0 cover needs to be an image, not a full-frame colour wash.

### The Cover Frame (Frame 0)

The cover frame is what Instagram shows in the feed **before** the viewer taps play. It must:
- Have the hook title fully readable and fully in position at frame 0; later animation must preserve the completed cover
- Show a recognizable, high-contrast image from the `searchQuery`
- NOT be a fully black frame or a transition frame

**Implication for text animation selection on scene 0**: prefer `rise-mask`, `clip-wipe`, `line-stagger`, or `fade-up`. Avoid `typewriter` (text invisible at frame 0) and `glitch-decode` (text illegible at frame 0) for the hook scene.

### Scene 0 Energy Contract (`energy.ts`)
```
level:     0.52-0.65   ← calmer hook, type lands clean
camera:    0.9 × base  ← still moving, just not thrashing
still:     false
```
This is correct. Body scenes escalate from here.

---

## PER-SCENE MOTION PRINCIPLES

### The "Reading Beat" Window
Every scene has a `landEnd` (~frames 0-26) where the text animation is completing and the viewer is reading. During this window:
- Camera intensity is inherited from `energy.camera` but text must be legible
- `ShapeAccents` and `PolishStack` grain pulses are gated to stay below the animation
- `HudOverlay` elements don't animate (already implemented in `HudOverlay.tsx`)

**Never add new animated elements that fire during the reading beat.** If you're adding a new visual component, check `energy.landEnd` and gate accordingly.

### The "Kinetic Window" (kineticStart → end)
This is where dynamic motion earns its keep. `energy.kineticStart` (≥50% through the scene) is when:
- Mid-scene b-roll cuts fire (`allowMidCut`)
- `emphasis-sweep` micro-detail fires
- `edge-tease` fires (6 frames before the next dressed cut)

Any new mid-scene event should be placed AFTER `energy.kineticStart`.

---

## TEXT ANIMATION SELECTION GUIDE

The pool system in `Main.tsx` picks two text animations per video (`TEXT_ANIM_POOLS`) and alternates. These are the rules for extending or adjusting pools:

### What Each Mode Does to Retention

| Mode | Retention impact | Use case |
|---|---|---|
| `rise-mask` | HIGH — dramatic reveal, reads as premium | Headlines, hook scene |
| `clip-wipe` | HIGH — highlighter sweep, very modern | Stats, key words |
| `line-stagger` | HIGH — editorial, fast reading | Multi-line bodies |
| `elastic-rise` | HIGH — liquid snap, high energy | Hook, metric reveals |
| `flip-in` | MED-HIGH — kinetic, editorial | Scene transitions |
| `fade-up` | MED — safe, clean, universal | Any scene |
| `blur-in` | MED — cinematic, premium | Slow/contemplative scenes |
| `tracking-in` | MED — cinematic letter settle | Headlines, titles |
| `word-by-word` | MED — dramatic, quote-style | Testimonials, quotes |
| `slide-in` | MED — energetic, modern | Lists |
| `scale-pop` | LOW-MED — bouncy, can feel playful | Upbeat content only |
| `glitch-decode` | LOW (avoid as pool) | Tech styling only, explicit scenes |
| `typewriter` | LOW (avoid as pool) | Documentary/storytelling only |
| `wave` | LOW — avoid in pools | Fun only |

**Rule**: `glitch-decode`, `typewriter`, and `wave` should not appear in `TEXT_ANIM_POOLS` as video-wide identities. A scene can explicitly request them via `textAnimation` field, but they shouldn't be the default pool for 6+ scenes.

### Adding New Animation Modes

When adding a new mode to `TEXT_ANIM_POOLS`:
1. Append the new pair(s) AFTER all existing entries — never insert in the middle (reshuffles all seeds' pool assignments)
2. The pool count grows; existing seeds land on different pools only if `(seed >>> 5) % len` changes — acceptable precedent (already happened 6→9→11→13→15 times)
3. New modes must be render-side only (not in the Zod schema enum) unless explicitly approved

---

## MICRO-DETAILS — Engineering the "Craft" Feeling

The micro-detail system (`microDetails.ts`) puts 2 seeded details per video. These are the ones that make the audience think "this looks professional" without being able to say why.

### Current Details and What They Do for Retention

| Detail | What it does for viewers | Frame window |
|---|---|---|
| `hairline-draw` | Feels like live design; signals craft | Text-landing beat |
| `landing-pop` | Makes text feel physical, not digital | Text-landing beat |
| `emphasis-sweep` | Spotlight moment — draws eye to key stat | kineticStart |
| `cut-fringe` | Makes cuts feel edited, not spliced | ±2 frames around cuts |
| `grain-breath` | Filmic texture; reads as premium production | Ambient (all frames) |
| `progress-comet` | Tells viewer "there's more coming, stay" | Scene entries |
| `accent-dot` | Visual continuity across cuts (through-line) | Cross-scene |
| `edge-tease` | Shows next scene's color early — teases the cut | 6 frames before dressed cut |
| `word-pulse` | Eye-lock on the active caption word | Active subtitle word |

**`word-pulse` is the most powerful retention detail** — it synchronizes the viewer's eye with the voiceover word-by-word, creating physical engagement. Ensure it's eligible (it always is, no eligibility gate).

### Micro-Detail Design Rules

When adding new micro-details:
- Each detail needs its own distinct **temporal home** — no two details should animate the same frame window
- Cost must be O(1) DOM: no filter:blur, no per-letter spans in wrapping flex
- Must support reading, never compete with it
- Append to `ALL_DETAILS` after existing entries (reshuffles which pair seeds land on — sanctioned)
- Draw count stays FOUR (two position draws, two stride draws) — new draws require a new constant offset

---

## TRANSITION SYSTEM — Cuts as Emotional Punctuation

Transitions in `SceneTransition.tsx` are the video's rhythm. Bad transition selection makes a video feel random. Good selection makes it feel directed.

### The Three Cut Roles

| Cut role | When it happens | Best transition |
|---|---|---|
| **Continuation** | Scene B elaborates on scene A's point | `crossfade`, `blur-dissolve` |
| **Escalation** | Scene B reveals something more surprising | `zoom-through`, `push-up`, `iris-open` |
| **Pivot** | Scene B shifts to a different angle entirely | `wipe-down`, `slide-left`, `whip` |
| **Punctuation** | Between hook and body, or body and CTA | `glitch-cut`, `spin-blur` |

The current system picks one signature transition + one accent per video from the seed. **Do not make every cut dressed** — the contrast between dressed transitions and hard cuts is what gives dressed transitions their impact.

### The Hook-to-Body Cut

The cut from scene 0 to scene 1 is the second most important moment in the video (after the first 3 seconds). It should feel like an *answer* arriving. Preferred transitions here:
- `zoom-through` (camera drives forward — commitment)
- `push-up` (new information pushing up — momentum)
- `iris-open` (reveal happening — payoff)

Avoid `crossfade` for the hook-to-body cut — it's too gentle for the escalation that needs to happen here.

---

## THE HUD OVERLAY — Furniture That Earns Its Place

Every `HudOverlay` element competes for attention. The ones that survive should all answer: **does this tell the viewer something they want to know?**

Elements that earn their place:
- **Progress bar**: Answers "how much is left?" — reduces anxiety, increases completion rate
- **Progress comet** (micro-detail): Makes the progress bar *feel alive* — adds the craft signal
- **Source attribution** (scene 0 only): Answers "where is this from?" — increases credibility
- **Scene counter**: Tells viewer "this is structured" — sets expectation for a listicle/multi-point video

Elements that are decoration without information:
- Rings (unless they pulse to the beat in a music-synced video)
- Floating shapes (unless anchored to the content)
- Corner brackets (pure styling — only if the look requires it)

**Rule**: If removing an HUD element doesn't change what the viewer *knows*, consider removing it.

---

## THE FINAL SCENE — The Dead-Still Close

`energy.still = true` on the final scene means:
- Camera multiplier = 0 (locked off)
- `ShapeAccents` frozen
- `PolishStack` grain pulse frozen
- Mid-scene cuts disabled

**This is a feature, not a bug.** A completely still final frame on a kinetic feed reads as a deliberate choice — confident and conclusive. The brain reads stillness after motion as "this is the answer." Do not add animation to the final scene.

The only elements that should animate in the final scene:
- The text entrance (one clean reveal, then hold)
- The CTA button pulse (very subtle, already in `VideoFX.tsx`)
- The progress bar completing (natural completion, already implemented)

---

## COLOUR SYSTEM — Accent as Emotional Signal

The color system (`looks.ts` + `contrast.ts`) already handles legibility. This section is about the *emotional* role of colour:

### Colour-to-Emotion Mapping for Content Selection

When the LLM picks colors for the `theme`, these mappings drive viewer perception:

| Hue family | Emotional read | Use for |
|---|---|---|
| Cyan/blue (`#00f0ff`, `#0066ff`) | Trust, intelligence, tech | AI, dev tools, cloud |
| Purple/violet (`#8b5cf6`, `#7c3aed`) | Premium, mysterious, premium AI | Research, ML, security |
| Red/orange (`#ef4444`, `#ff6b35`) | Urgency, danger, breaking | Security breaches, losses, crashes |
| Green (`#10b981`, `#059669`) | Growth, go, success | Product launches, funding, milestones |
| Pink/magenta (`#ec4899`, `#ff007f`) | Bold, playful, disruptive | Consumer tech, viral moments |
| Amber/gold (`#f59e0b`, `#fbbf24`) | Value, opportunity, highlight | Financial gains, opportunities |

### The `accentPlan` Role in Retention

- `"fixed"`: one accent colour throughout — consistent brand, but less variety
- `"cycle"`: primary/secondary alternates per scene — creates energy, "something changed" feel
- `"mono"`: one rotating accent owns each scene, media desaturates — very editorial, very premium

For **fast-moving tech news**: `"cycle"` or `"fixed"` with high-contrast primary.
For **premium / analytical**: `"mono"`.
For **viral / consumer**: `"cycle"` with warm primaries.

---

## ADDING NEW COMPONENTS — The Rules

When adding a new component to `src/remotion/MyComp/`:

1. **Determinism first**: Use `makeRng(seed ^ UNIQUE_CONSTANT)` — never `Math.random()` or `Date.now()`. Assign a new unique XOR constant (document it in the file alongside existing constants).

2. **Energy-aware**: Accept `energy: SceneEnergy` as a prop if the component has any animation. Gate animations with `energy.landEnd` and `energy.kineticStart`.

3. **No draw-count side effects**: If your component draws from the RNG, it must draw a **fixed count** regardless of what gates are active. This is the "polish.ts discipline" — gating must happen AFTER all draws, never instead of them.

4. **Contrast audit**: Any element over the photo/video background must be checked against `contrastBudget`. Text-legibility is a floor, not a preference.

5. **No new `Math.random()` or `Date.now()`**: Remotion renders frames out of order and in parallel. Non-deterministic values produce flickering. Every render must be a pure function of `frame` and `seed`.

---

## KNOWN HIGH-IMPACT RENDER IMPROVEMENTS (Future Work)

These are improvements that the motion system *could* make to improve retention further, in priority order:

| Improvement | Impact | Status |
|---|---|---|
| Beat-synced subtitle word highlight (karaoke pulse on `word-pulse` detail) | HIGH — eye-lock on audio | Partially in `word-pulse` micro-detail |
| Hook scene: title fully visible at frame 0 (thumbnail) | Cover readability invariant | Already implemented; preserve and run `scripts/check-cover-frame.sh` |
| Subtitle band: `clip-wipe` per-word highlight synced to TTS timing | HIGH — most addictive subtitle format | Requires AnimatedText integration with `WordBoundary` data |
| Progress comet: leaves a trail that fades (feels more alive) | MED — craft signal | `progress-comet` micro-detail |
| Cut-synchronised accent flash (1 frame) on dressed cuts | MED — edits feel intentional | `cut-fringe` micro-detail |

---

## SUMMARY: THE VISUAL RETENTION HIERARCHY

```
1. Frame 0 cover quality          ← Is there a compelling image + readable text?
2. HookPunch (frames 1-42)        ← Does the visual burst match the spoken shock?
3. Hook text animation             ← Does the title land BEFORE 3 seconds?
4. Scene 0 → Scene 1 cut          ← Does the transition feel like escalation?
5. Body scene energy schedule      ← Is there a kinetic spike every 3 scenes?
6. Micro-details                   ← Does it feel *produced*, not generated?
7. Final scene stillness           ← Does the close feel confident?
```

If step 1-3 fail, no amount of polish in steps 4-7 matters.

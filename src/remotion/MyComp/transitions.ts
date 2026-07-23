// ============================================================================
// transitions.ts — Seeded per-boundary "cut plan"
// ----------------------------------------------------------------------------
// Before this existed, each scene rolled its own transition style
// independently (SceneTransition's companion roll), so scene N's exit and
// scene N+1's enter could be different, uncoordinated styles — cuts read as
// per-scene edge animations, not edits. This module derives ONE CutSpec per
// scene BOUNDARY from the seed; both sides of a cut read the same spec, so
// exit and enter motion are complementary (old content whips off left ⇒ new
// content whips in from right, a film-burn peaks exactly at the cut, etc.).
//
// Like looks.ts, everything is a pure function of the seed — render-safe
// under Remotion's frame-parallel renderer. The new styles exist ONLY here
// (render-side), never in the props schema, so nothing in main.py or the Zod
// enums needs to change (same precedent as AnimatedText's rise-mask/flip-in).
// ============================================================================

import { makeRng, pick, type MotionFeel } from "./looks";

export type CutStyleName =
  // The 10 legacy styles (the values theme.transitionStyle can carry)
  | "crossfade"
  | "slide-left"
  | "zoom-through"
  | "glitch-cut"
  | "wipe-down"
  | "iris-open"
  | "blur-dissolve"
  | "scale-rotate"
  | "push-up"
  | "spin-blur"
  // Render-side-only styles — never appear in props JSON
  | "whip-pan"
  | "film-burn"
  | "venetian-blinds"
  | "luma-radial"
  | "chromatic-punch"
  | "skew-peel"
  | "stutter-zoom"
  | "diamond-iris"
  // The connector cut: a hard cut where the incoming scene lands slightly
  // punched-in (~6-8%) and settles. Reads as a deliberate camera change, not
  // an effect — it is what fills the space between dressed transitions.
  | "punch-in"
  | "none";

export interface CutSpec {
  style: CutStyleName;
  /** Direction shared by exit(N) and enter(N+1) so motion continues across the cut. */
  dir: 1 | -1;
  /** Orientation for whip/blinds styles. */
  axis: "x" | "y";
  /** 0..1 — corner pick for film-burn, start angle for luma-radial, slat jitter. */
  flavor: number;
  /** 0.6..1 — scales amplitudes so not every cut is max energy. */
  intensity: number;
}

// Cuts loud enough to justify a whoosh. Soft dissolves/burns whooshing on
// every boundary is the #1 amateur SFX tell — Main.tsx plays the whoosh only
// for these, which the sparse cut plan already caps at ~2-3 per video.
export const WHOOSH_CUTS: ReadonlySet<CutStyleName> = new Set([
  "whip-pan",
  "zoom-through",
  "stutter-zoom",
  "spin-blur",
  "chromatic-punch",
  "glitch-cut",
  "scale-rotate",
  "venetian-blinds",
  "slide-left",
  "push-up",
  "wipe-down",
]);

// Cut-style pools flavored by the look's motion personality — the same
// pattern as MOTION_PROFILES' camera pools. A calm video never whip-pans;
// a snappy one never slow-burns.
const TRANSITION_POOLS: Record<MotionFeel, readonly CutStyleName[]> = {
  calm: ["crossfade", "blur-dissolve", "skew-peel", "luma-radial"],
  snappy: ["whip-pan", "stutter-zoom", "chromatic-punch", "venetian-blinds"],
  bouncy: ["push-up", "zoom-through", "stutter-zoom", "venetian-blinds"],
  cinematic: ["film-burn", "luma-radial", "diamond-iris", "crossfade"],
};

const LEGACY_STYLES: readonly CutStyleName[] = [
  "crossfade", "slide-left", "zoom-through", "glitch-cut", "wipe-down",
  "iris-open", "blur-dissolve", "scale-rotate", "push-up", "spin-blur",
];

/**
 * Derive the full cut plan for a video.
 *
 * Returns `sceneCount + 1` specs:
 *   plan[0]            — opening enter of scene 0 (kept gentle & readable),
 *   plan[i]            — the boundary between scene i-1 and scene i,
 *   plan[sceneCount]   — the closing exit of the last scene.
 *
 * Editing rhythm (the thing that separates a pro edit from a template): most
 * boundaries are CONNECTOR cuts — a hard cut or a punch-in — and a dressed
 * transition lands at most every third boundary. Each video's dressed
 * vocabulary is exactly two styles: the Python-chosen `anchor`
 * (theme.transitionStyle) as the signature, plus ONE accent drawn from the
 * motion-personality pool. A grab-bag of five styles in 40 seconds is the
 * "PowerPoint effect"; two used sparingly read as intent. anchor "none"
 * disables everything (bit-identical to the pre-cut-plan behavior).
 *
 * Uses an independent re-seeded RNG stream (seed ^ 0x51ed270b) so existing
 * seeds keep the exact look deriveLook already gave them.
 */
export function deriveCutPlan(
  seed: number,
  sceneCount: number,
  anchor: string,
  motion: MotionFeel,
): CutSpec[] {
  const safeAnchor: CutStyleName =
    anchor === "none"
      ? "none"
      : LEGACY_STYLES.includes(anchor as CutStyleName)
        ? (anchor as CutStyleName)
        : "crossfade";

  const rng = makeRng(((seed ^ 0x51ed270b) >>> 0) || 1);
  const plan: CutSpec[] = [];

  // Opening: scene 0 keeps its fast, readable 4-frame enter in the anchor
  // style — viewers judge a Reel in its first frames; no fancy cut here.
  plan.push({ style: safeAnchor, dir: 1, axis: "x", flavor: 0.5, intensity: 0.5 });

  // The single accent style for this video, fixed up front so every dressed
  // non-signature cut reuses it (one signature + one accent per video).
  const pool = TRANSITION_POOLS[motion];
  const accent: CutStyleName = pool[Math.floor(rng() * pool.length) % pool.length];

  let sinceDressed = 0; // interior boundaries since the last dressed cut
  let dir: 1 | -1 = rng() < 0.5 ? 1 : -1;
  for (let i = 1; i < sceneCount; i++) {
    // Fixed number of draws per boundary keeps the whole plan stable.
    const dressRoll = rng();
    const styleRoll = rng();
    const connectorRoll = rng();
    const axisRoll = rng();
    const flavor = rng();
    const intensity = 0.6 + rng() * 0.4;

    // Alternate direction across boundaries — motion that ping-pongs reads
    // as edited; motion that always drifts one way reads as a slideshow.
    dir = dir === 1 ? -1 : 1;

    let style: CutStyleName;
    if (safeAnchor === "none") {
      style = "none";
    } else if (sinceDressed >= 2 && (dressRoll < 0.65 || sinceDressed >= 3)) {
      // Dressed cut: signature ~70%, the one accent ~30%.
      style = styleRoll < 0.7 ? safeAnchor : accent;
      sinceDressed = 0;
    } else {
      // Connector: punch-in most of the time, plain hard cut otherwise.
      // Calm videos lean harder on the plain cut — even a 7% punch is energy.
      const punchChance = motion === "calm" ? 0.45 : 0.75;
      style = connectorRoll < punchChance ? "punch-in" : "none";
      sinceDressed += 1;
    }

    plan.push({
      style,
      dir,
      // Snappy cuts read best horizontally; others mix it up.
      axis: motion === "snappy" ? (axisRoll < 0.8 ? "x" : "y") : axisRoll < 0.55 ? "x" : "y",
      flavor,
      intensity,
    });
  }

  // Closing: nothing follows the last scene — settle out plainly.
  plan.push({
    style: safeAnchor === "none" ? "none" : "crossfade",
    dir: 1,
    axis: "x",
    flavor: 0.5,
    intensity: 0.5,
  });

  return plan;
}

// Re-export for consumers that only need the pool identity (e.g. CutCover).
export { pick };

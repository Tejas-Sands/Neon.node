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
//
// The vocabulary is deliberately narrowed to four families — dissolves, whip
// pans, wipes/blinds/irises and film burns. The zoom/punch and glitch/chromatic
// families were removed on purpose: they are the loudest styles in the set and
// the ones that most disrupt reading, and the news has to be legible before it
// is exciting. Pool LENGTH stays 4 in every row so the accent pick
// (`pool[floor(rng()*len) % len]`) consumes exactly one draw as before — only
// the contents change, never the draw count.
const TRANSITION_POOLS: Record<MotionFeel, readonly CutStyleName[]> = {
  calm: ["crossfade", "blur-dissolve", "film-burn", "luma-radial"],
  snappy: ["whip-pan", "venetian-blinds", "luma-radial", "diamond-iris"],
  bouncy: ["push-up", "venetian-blinds", "whip-pan", "diamond-iris"],
  cinematic: ["film-burn", "luma-radial", "diamond-iris", "crossfade"],
};

// Anchors the Python side may still send that are no longer in the vocabulary,
// each mapped to the nearest survivor in a family we keep. Applied to the
// ANCHOR only — `theme.transitionStyle` is schema-bound (ALLOWED_TRANSITIONS in
// main.py), so the enum cannot shrink without a 4-point sync. Remapping here is
// render-side and needs no sync, which is the same precedent as the
// render-side-only styles above.
const BANNED_ANCHORS: Partial<Record<CutStyleName, CutStyleName>> = {
  "zoom-through": "blur-dissolve",
  "glitch-cut": "whip-pan",
  "spin-blur": "blur-dissolve",
  "scale-rotate": "iris-open",
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
 * Editing rhythm (the thing that separates a pro edit from a template): the
 * boundaries alternate between CONNECTOR cuts — a hard cut or a punch-in —
 * and dressed transitions, which land roughly every other boundary (raised
 * from every third, 2026-07-31: the brief asked for a more dressed edit; the
 * connectors keep the rhythm honest). Each video's dressed vocabulary is
 * three styles: the Python-chosen `anchor` (theme.transitionStyle) as the
 * dominant signature, plus TWO accents drawn from the motion-personality
 * pool. A grab-bag of five styles in 40 seconds is still the "PowerPoint
 * effect"; three with a dominant signature read as intent. The final boundary
 * is always a soft dissolve/burn INTO the dead-still last scene (energy
 * schedule Q9b) — and neither is in WHOOSH_CUTS, so the close is silent.
 * anchor "none" disables everything (bit-identical to pre-cut-plan).
 *
 * Uses an independent re-seeded RNG stream (seed ^ 0x51ed270b) so existing
 * seeds keep the exact look deriveLook already gave them.
 */
export function deriveCutPlan(
  seed: number,
  sceneCount: number,
  anchor: string,
  motion: MotionFeel,
  opts?: { loopEnding?: boolean },
): CutSpec[] {
  const loopEnding = opts?.loopEnding === true;
  const validAnchor: CutStyleName =
    anchor === "none"
      ? "none"
      : LEGACY_STYLES.includes(anchor as CutStyleName)
        ? (anchor as CutStyleName)
        : "crossfade";
  // Retired families are swapped for the nearest kept one BEFORE the plan is
  // built, so the signature style and every dressed cut that reuses it inherit
  // the substitution together.
  const safeAnchor: CutStyleName = BANNED_ANCHORS[validAnchor] ?? validAnchor;

  const rng = makeRng(((seed ^ 0x51ed270b) >>> 0) || 1);
  const plan: CutSpec[] = [];

  // Opening: scene 0 keeps its fast, readable 4-frame enter in the anchor
  // style — viewers judge a Reel in its first frames; no fancy cut here.
  plan.push({ style: safeAnchor, dir: 1, axis: "x", flavor: 0.5, intensity: 0.5 });

  // The two accent styles for this video, fixed up front so every dressed
  // non-signature cut reuses them (one signature + two accents per video).
  // accent2 shifts one pool slot when its draw collides with accent — a
  // deterministic dodge that keeps the draw count fixed.
  const pool = TRANSITION_POOLS[motion];
  const accentIdx = Math.floor(rng() * pool.length) % pool.length;
  const accent: CutStyleName = pool[accentIdx];
  const accent2Idx = Math.floor(rng() * pool.length) % pool.length;
  const accent2: CutStyleName =
    pool[accent2Idx === accentIdx ? (accent2Idx + 1) % pool.length : accent2Idx];

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
    } else if (i === sceneCount - 1) {
      // The boundary INTO the final scene. Legacy: always a soft landing —
      // a heavy cut into a dead-still frame reads as a broken render, and
      // neither style whooshes. Loop-ending: the opposite — a punchy HARD
      // landing into the payoff/reveal IS the format; the scene itself stays
      // quiet. Draws above are consumed either way.
      style = loopEnding ? "punch-in" : motion === "cinematic" ? "film-burn" : "blur-dissolve";
      sinceDressed = 0;
    } else if (sinceDressed >= 1 && (dressRoll < 0.55 || sinceDressed >= 2)) {
      // Dressed cut roughly every other boundary: signature ~55%,
      // first accent ~25%, second accent ~20%.
      style = styleRoll < 0.55 ? safeAnchor : styleRoll < 0.8 ? accent : accent2;
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
      // Legacy: the landing into the still scene stays gentle regardless of
      // the roll. Loop-ending: the reveal landing carries real punch.
      intensity: i === sceneCount - 1 ? (loopEnding ? 0.7 : 0.5) : intensity,
    });
  }

  // Closing: nothing follows the last scene. Legacy settles out with a
  // crossfade; loop-ending ends on a FULL-STRENGTH frame (no fade-out — the
  // last frame is the replay seam and must match frame 0's energy).
  plan.push({
    style: loopEnding || safeAnchor === "none" ? "none" : "crossfade",
    dir: 1,
    axis: "x",
    flavor: 0.5,
    intensity: 0.5,
  });

  return plan;
}

// Re-export for consumers that only need the pool identity (e.g. CutCover).
export { pick };

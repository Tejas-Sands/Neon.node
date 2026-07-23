// ============================================================================
// polish.ts — Seeded "finishing" layer selection
// ----------------------------------------------------------------------------
// Decides which cinematic polish layers (film grain, light leaks, edge frame,
// letterbox, pulse glow, halftone texture, end settle) a video gets. Layers
// are assigned FROM the look's grade/chrome/motion so they feel designed for
// the video, not random soup — e.g. halftone lands on editorial/faded looks,
// never on cyber-neon HUD looks; grain suppressed on vhs-glitch (which
// already carries scanline noise). A hard cap keeps at most 3 textural
// layers active per video.
//
// Pure function of (seed, look, overlayType) on an independent RNG stream —
// existing seeds keep the exact look deriveLook already gave them.
// ============================================================================

import { makeRng, type LookConfig } from "./looks";

export interface PolishConfig {
  grain: boolean;
  grainOpacity: number;
  leaks: boolean;
  leakPhase: number;
  edgeFrame: "gradient" | "hairline" | "none";
  letterbox: boolean;
  pulse: boolean;
  pulsePeriod: number;
  halftone: boolean;
  endSettle: boolean;
}

export function derivePolish(
  seed: number,
  look: LookConfig,
  overlayType: string,
): PolishConfig {
  const rng = makeRng((((seed ^ 0x9e3779b9) + 7) >>> 0) || 1);
  // Fixed draw order for stability.
  const grainOpacity = 0.05 + rng() * 0.03;
  const leakPhase = rng() * Math.PI * 2;
  const pulsePeriod = 22 + Math.floor(rng() * 3) * 6;

  let grain =
    look.grade === "noir" ||
    look.grade === "faded" ||
    (look.motion === "cinematic" && ["neutral", "warm", "cool"].includes(look.grade));
  if (overlayType === "vhs-glitch") grain = false;

  let leaks = ["warm", "vibrant"].includes(look.grade) || look.motion === "cinematic";
  if (["aurora", "fantasy-sparks"].includes(overlayType) || look.chrome === "minimal") {
    leaks = false;
  }

  let edgeFrame: PolishConfig["edgeFrame"] =
    look.chrome === "broadcast" || look.chrome === "kinetic"
      ? "gradient"
      : look.chrome === "editorial"
        ? "hairline"
        : "none";

  // Structural, not textural — exempt from the cap. Never double up with the
  // look's own static cinema-bars background.
  const letterbox =
    (look.motion === "cinematic" || look.grade === "noir") &&
    look.background !== "cinema-bars";

  let pulse = ["snappy", "bouncy"].includes(look.motion) && look.chrome !== "minimal";

  let halftone =
    (look.chrome === "editorial" || look.grade === "faded") &&
    !["grid-hud", "vhs-glitch"].includes(overlayType);

  // Cohesion cap: at most 3 textural layers, priority grain > leaks >
  // edgeFrame > halftone > pulse.
  let count = grain ? 1 : 0;
  if (leaks) {
    if (count >= 3) leaks = false;
    else count++;
  }
  if (edgeFrame !== "none") {
    if (count >= 3) edgeFrame = "none";
    else count++;
  }
  if (halftone) {
    if (count >= 3) halftone = false;
    else count++;
  }
  if (pulse) {
    if (count >= 3) pulse = false;
    else count++;
  }

  return {
    grain,
    grainOpacity,
    leaks,
    leakPhase,
    edgeFrame,
    letterbox,
    pulse,
    pulsePeriod,
    halftone,
    endSettle: true,
  };
}

// ============================================================================
// prism.ts — Seeded "Prism" look family selection
// ----------------------------------------------------------------------------
// Decides whether a video gets the kaleidoscope / blend-layer / giant-type
// treatment (reference: TouchDesigner-style mirror edits) and with which
// parameters. Bold by design, so it is gated to a minority of seeds and
// weighted toward the cyber overlay worlds (grid-hud / vhs-glitch) where the
// mirrored-footage language belongs; soft ambient worlds never draw it.
//
// Pure function of (seed, look, overlayType) on an independent RNG stream —
// existing seeds keep the exact draws deriveLook/deriveFinish/derivePolish
// already gave them, and disabled seeds render byte-identical output.
// ============================================================================

import { makeRng, type LookConfig, type MotionFeel } from "./looks";
import { derivePolish } from "./polish";

export type PrismMode = "mirror-2" | "mirror-4" | "split-band" | "blend-drift";
export type PrismBodyMode = "off" | "blend-drift" | "mirror-2-soft";

export interface PrismInsetSpec {
  /** Window rect in % of the frame. */
  x: number;
  y: number;
  w: number;
  h: number;
  /** Inner media zoom + exposure lift, per the frame-in-frame reference. */
  zoom: number;
  exposure: number;
}

export interface PrismConfig {
  enabled: boolean;
  /** Full-strength treatment (hero / outro / cta scenes + cut flares). */
  mode: PrismMode;
  /** Milder treatment for text-heavy body scenes — readability first. */
  bodyMode: PrismBodyMode;
  twirl: boolean;
  twirlDir: 1 | -1;
  blendCopies: 0 | 1 | 2;
  insetWindows: 0 | 1 | 2;
  insetSpecs: PrismInsetSpec[];
  giantWord: boolean;
  borderFrame: boolean;
  /** Split-band reflection axis, % from top. >=50 so the mirrored top always
      covers the frame below the seam. */
  bandSeam: number;
  seamAlpha: number;
  /** Shared phase for every sin/cos drift so copies breathe together. */
  driftPhase: number;
  bloom: number;
}

// Full-strength mode pools flavored by the look's motion personality — the
// same pattern as MOTION_PROFILES / TRANSITION_POOLS. A calm video never gets
// the 4-fold mandala; a snappy one leans into it.
const MODE_WEIGHTS: Record<MotionFeel, [PrismMode, number][]> = {
  calm: [
    ["blend-drift", 0.5],
    ["split-band", 0.5],
  ],
  cinematic: [
    ["mirror-2", 0.45],
    ["split-band", 0.35],
    ["blend-drift", 0.2],
  ],
  snappy: [
    ["mirror-4", 0.4],
    ["mirror-2", 0.35],
    ["split-band", 0.25],
  ],
  bouncy: [
    ["mirror-4", 0.35],
    ["mirror-2", 0.35],
    ["blend-drift", 0.3],
  ],
};

const weightedFromRoll = <T,>(roll: number, entries: [T, number][]): T => {
  const total = entries.reduce((a, [, w]) => a + w, 0);
  let r = roll * total;
  for (const [v, w] of entries) {
    r -= w;
    if (r <= 0) return v;
  }
  return entries[entries.length - 1][0];
};

export function derivePrism(
  seed: number,
  look: LookConfig,
  overlayType: string,
): PrismConfig {
  const rng = makeRng((((seed ^ 0x3d9f2b6e) + 5) >>> 0) || 1);
  // Fixed draw order for stability — every value is drawn unconditionally
  // BEFORE any gate, so tuning gates later never reshuffles other draws.
  const enableRoll = rng();
  const modeRoll = rng();
  const bodyRoll = rng();
  const twirlRoll = rng();
  const twirlDirRoll = rng();
  const blendRoll = rng();
  const insetCountRoll = rng();
  const insetSpecs: PrismInsetSpec[] = [];
  for (let i = 0; i < 2; i++) {
    const w = 30 + rng() * 25;
    const h = 26 + rng() * 22;
    // Center-biased, clamped clear of the edges and of the caption band
    // (bottom 24%) — insets only ever show on hero/outro/cta anyway.
    const x = Math.max(6, Math.min(94 - w, 50 - w / 2 + (rng() - 0.5) * 24));
    const y = 16 + rng() * Math.max(4, 56 - h);
    const zoom = 1.4 + rng() * 0.5;
    const exposure = 1.15 + rng() * 0.25;
    insetSpecs.push({ x, y, w, h, zoom, exposure });
  }
  const giantRoll = rng();
  const frameRoll = rng();
  const bandSeam = 50 + rng() * 12;
  const seamAlpha = 0.15 + rng() * 0.2;
  const driftPhase = rng() * Math.PI * 2;
  const bloom = rng();

  // Mirrored-footage language belongs to the cyber worlds; fantasy-sparks is
  // a soft ambient pack, and gradient-wash fades the media to 0.38 opacity —
  // there is nothing worth mirroring.
  let p = 0.26;
  if (overlayType === "grid-hud" || overlayType === "vhs-glitch") p = 0.38;
  else if (overlayType === "aurora") p = 0.1;
  else if (overlayType === "fantasy-sparks") p = 0;
  if (look.background === "gradient-wash") p = 0;
  const enabled = enableRoll < p;

  const mode = weightedFromRoll(modeRoll, MODE_WEIGHTS[look.motion]);

  const bodyMode: PrismBodyMode =
    bodyRoll < 0.3 ? "mirror-2-soft" : bodyRoll < 0.88 ? "blend-drift" : "off";

  const twirl =
    (look.motion === "snappy" || look.motion === "bouncy") &&
    mode !== "blend-drift" &&
    twirlRoll < 0.6;
  const twirlDir: 1 | -1 = twirlDirRoll < 0.5 ? 1 : -1;

  let blendCopies = (blendRoll < 0.4 ? 2 : blendRoll < 0.85 ? 1 : 0) as 0 | 1 | 2;
  if (mode === "blend-drift" && blendCopies === 0) blendCopies = 1;

  const insetWindows = (insetCountRoll < 0.35 ? 2 : insetCountRoll < 0.75 ? 1 : 0) as 0 | 1 | 2;

  // Never two frames: yield to the polish layer's edge frame / letterbox and
  // to the look's own static cinema bars.
  const polish = derivePolish(seed, look, overlayType);
  const borderFrame =
    frameRoll < 0.6 &&
    polish.edgeFrame === "none" &&
    !polish.letterbox &&
    look.background !== "cinema-bars";

  return {
    enabled,
    mode,
    bodyMode,
    twirl,
    twirlDir,
    blendCopies,
    insetWindows,
    insetSpecs,
    giantWord: giantRoll < 0.5,
    borderFrame,
    bandSeam,
    seamAlpha,
    driftPhase,
    bloom,
  };
}

/**
 * Per-scene base strength: full treatment on the poster moments, the milder
 * bodyMode on text-heavy scenes, nothing when the family is off. Cut flares
 * on top of this are applied inside PrismMedia.
 */
export function prismSceneStrength(
  prism: PrismConfig,
  sceneType: string | undefined,
): number {
  if (!prism.enabled) return 0;
  if (sceneType === "hero" || sceneType === "outro" || sceneType === "cta") return 1;
  if (prism.bodyMode === "off") return 0;
  // High enough that the mirror language stays present through body scenes
  // (the reference edit never drops its treatment); panels + scrim keep text safe.
  return 0.7;
}

// ============================================================================
// microDetails.ts — small seeded craft details ("the little effects")
// ----------------------------------------------------------------------------
// Design-brief §7: the user wants all of the micro-detail wishlist (Q24), but
// only 1-2 live at once (Q25b), chosen seeded-random per video (Q26c). Each
// detail has a distinct TEMPORAL home so two active details never compete on
// the same frames:
//
//   hairline-draw   → the text-landing beat (decorates the arrival itself)
//   landing-pop     → the text-landing beat (depth pop as type settles)
//   emphasis-sweep  → mid-read, one light sweep at energy.kineticStart
//   cut-fringe      → cut boundaries only (±2 frames, inside CutCover)
//   grain-breath    → ambient, sub-threshold texture breathing
//   progress-comet  → scene entries (the progress bar's tip leads the bar)
//
// All are O(1) DOM cost, none uses filter:blur, none enters the caption band,
// and each supports reading rather than competing with it. Implementations
// live in the components that already own the surfaces (Main.tsx hero rule,
// AnimatedText, PolishLayers CutCover/FilmGrain, SceneImpactFrame).
//
// Determinism: independent RNG stream `seed ^ 0x44c1e6a9` (fresh constant —
// existing streams: raw, 0x7f4a7c15 finish, 0x9e3779b9 polish, 0x3d9f2b6e
// prism, 0x51ed270b cutplan, 0x6d1b9f37 energy). polish.ts draw discipline:
// fixed draw count, all consumed before any gate.
// ============================================================================

import { makeRng } from "./looks";
import type { LookConfig } from "./looks";
import type { PolishConfig } from "./polish";

export type MicroDetail =
  | "hairline-draw"
  | "landing-pop"
  | "emphasis-sweep"
  | "cut-fringe"
  | "grain-breath"
  | "progress-comet";

export interface MicroDetailConfig {
  /** Exactly two distinct details per video (Q25b), seeded (Q26c). */
  active: readonly [MicroDetail, MicroDetail];
  has: (d: MicroDetail) => boolean;
}

const ALL_DETAILS: readonly MicroDetail[] = [
  "hairline-draw",
  "landing-pop",
  "emphasis-sweep",
  "cut-fringe",
  "grain-breath",
  "progress-comet",
];

/**
 * Pick this video's two micro-details. Eligibility: grain-breath needs the
 * polish grain layer to exist; progress-comet needs the progress bar. Draw
 * discipline: a fixed FOUR draws are consumed unconditionally; picks walk the
 * shuffled order until two eligible, distinct details are found (the pool is
 * always >= 4 eligible, so two always exist).
 */
export function deriveMicroDetails(
  seed: number,
  look: LookConfig,
  polish: PolishConfig,
): MicroDetailConfig {
  const rng = makeRng(((seed ^ 0x44c1e6a9) >>> 0) || 1);
  // Fixed draws first (polish.ts discipline) — used as shuffle keys.
  const draws = [rng(), rng(), rng(), rng()];

  const eligible = ALL_DETAILS.filter((d) => {
    if (d === "grain-breath") return polish.grain;
    if (d === "progress-comet") return look.showProgressBar;
    return true;
  });

  // Deterministic order from the first two draws: rotate + stride walk.
  const start = Math.floor(draws[0] * eligible.length) % eligible.length;
  const stride = 1 + (Math.floor(draws[1] * (eligible.length - 1)) % (eligible.length - 1));
  const first = eligible[start];
  const second = eligible[(start + stride) % eligible.length];

  const active = [first, second] as const;
  return { active, has: (d) => active[0] === d || active[1] === d };
}

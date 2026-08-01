// ============================================================================
// packs.ts — per-video FORMAT-PACK skin (M5)
// ----------------------------------------------------------------------------
// A pack fixes a video's STRUCTURE (question → options → countdown → reveal);
// this module adds seeded micro-variety WITHIN that structure so pack videos
// never read as one rigid template (palette/finish/look/karaoke already vary
// per seed — this stream varies the pack furniture itself).
//
// Determinism: independent RNG stream `seed ^ 0x27d4eb2f` (verified against
// the other streams: raw looks / 0x9e3779b9 polish / 0x7f4a7c15 finish /
// 0x51ed270b cutplan / 0x3d9f2b6e prism / 0x6d1b9f37 energy / 0x44c1e6a9
// microDetails). polish.ts draw discipline: a FIXED number of draws, all
// consumed unconditionally before any gate, so future additions must append
// draws AFTER the existing ones.
// ============================================================================

import { makeRng } from "./looks";

export interface PackSkin {
  /** Quiz option badge shape: classic circle or a squared chip. */
  quizBadge: "circle" | "square";
  /** Option-row entrance: all from the left, or alternating sides. */
  quizEnterFrom: "left" | "alternate";
  /** Slight per-video scale on the option rows (0.95..1.05). */
  quizRowScale: number;
}

export function derivePackSkin(seed: number): PackSkin {
  const rng = makeRng(((seed ^ 0x27d4eb2f) >>> 0) || 1);
  // Fixed draws — consumed unconditionally, append-only forever.
  const badgeRoll = rng();
  const enterRoll = rng();
  const scaleRoll = rng();
  return {
    quizBadge: badgeRoll < 0.5 ? "circle" : "square",
    quizEnterFrom: enterRoll < 0.6 ? "left" : "alternate",
    quizRowScale: 0.95 + scaleRoll * 0.1,
  };
}

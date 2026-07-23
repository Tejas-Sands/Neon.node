// ============================================================================
// motion.ts — named easing/spring tokens shared across the composition.
// One motion vocabulary instead of per-component ad-hoc configs: enters
// decelerate with swiftOut, exits accelerate with swiftIn (matching the cut
// engine's asymmetry), and springs come in exactly three intents —
// settle (zero overshoot), pop (one clean overshoot), soft (body copy).
// Pure constants — no RNG, no frame math.
// ============================================================================
import { Easing } from "remotion";

export const EASE = {
  /** Canonical enter — decelerate in (same curve as SceneTransition's enter). */
  swiftOut: Easing.bezier(0.22, 1, 0.36, 1),
  /** Canonical exit — accelerate out (same curve as SceneTransition's exit). */
  swiftIn: Easing.bezier(0.64, 0, 0.78, 0),
  /** Ambient/secondary motion — gentler settle for non-focal elements. */
  gentle: Easing.bezier(0.33, 1, 0.68, 1),
} as const;

export const SPRINGS = {
  /** Zero-overshoot settle — captions, panels, anything that must not bounce. */
  settle: { damping: 200, stiffness: 130, mass: 0.8 },
  /** One clean overshoot — hero moments, buttons, winning panels. */
  pop: { damping: 14, stiffness: 170, mass: 0.6 },
  /** Soft body-copy entrance — labels, list rows, secondary text. */
  soft: { damping: 22, stiffness: 100, mass: 0.9 },
} as const;

/** Spring config scaled by the look's motion personality (springMul). */
export const springCfg = (
  k: keyof typeof SPRINGS,
  sMul = 1,
): { damping: number; stiffness: number; mass: number } => ({
  ...SPRINGS[k],
  stiffness: Math.round(SPRINGS[k].stiffness * sMul),
});

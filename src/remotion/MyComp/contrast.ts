// ============================================================================
// contrast.ts — the legibility budget
// ----------------------------------------------------------------------------
// The news has to be readable before it is exciting. Today that is bought
// bluntly: every background photo is crushed to brightness 0.60-0.76 by
// GRADE_FILTERS so text survives whatever is behind it. The cost is that the
// photo is dim EVERYWHERE, including the ~80% of the frame with no text on it.
//
// This module replaces that global dimming with arithmetic. It models the
// worst-case luminance arriving at each text zone and solves, in closed form,
// the MINIMUM plate alpha that still clears a WCAG contrast floor. Once plates
// are solved rather than guessed, the photo can be brightened by exactly as
// much as the plates can pay for — and no more.
//
// WHY THERE IS NO SAMPLING HERE. The obvious design is to measure the actual
// backdrop and adapt. That is not implementable: the background is usually a
// moving stock clip (main.py sets SCENE_VIDEO_MODE default "all", so every
// scene fetches a Pexels/Pixabay clip and paints it over the still), and
// Remotion renders frames in parallel worker processes with no pixel readback.
// So this solves against a WORST CASE instead. The result is a per-video
// constant — never time-varying, which also avoids a plate that visibly
// breathes, and keeps caption box metrics stable while a word is animating.
//
// Everything here is pure math. No RNG, no draws, no seed stream — this is the
// derivePalette class of module, so it carries zero draw-order risk.
// ============================================================================

import {
  clampAccentLuminance,
  gradeFilter,
  relLuminance,
  type ColorGrade,
  type LookConfig,
  type Palette,
} from "./looks";

// --- WCAG floors ------------------------------------------------------------
// 4.5:1 is the standard floor for body text. It is applied to the caption band
// and to body copy, which are the surfaces that actually carry the reporting.
// 3.0:1 is the large-text floor and is applied at display sizes — which lands
// exactly on AnimatedText's existing `effectiveFontSize >= 42` split, so the
// two tiers need no new threshold.
export const CR_BODY = 4.5;
export const CR_DISPLAY = 3.0;
export const DISPLAY_SIZE_PX = 42;

/**
 * Hard cap on plate alpha. Past this a "plate" is just an opaque box and the
 * photo behind it is gone — at which point the honest move is to refuse the
 * brightness lift, not to keep thickening.
 */
export const PLATE_CEILING = 0.82;

const clamp01 = (v: number) => (v < 0 ? 0 : v > 1 ? 1 : v);

/** sRGB channel value (0..1) -> its linear-light contribution. */
const linearize = (v: number) =>
  v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);

/** Relative luminance of a NEUTRAL grey at sRGB value v — the r=g=b case. */
export const greyLuminance = (v: number) => linearize(clamp01(v));

/** WCAG contrast ratio between two relative luminances, order-independent. */
export const contrastRatio = (a: number, b: number) => {
  const hi = Math.max(a, b);
  const lo = Math.min(a, b);
  return (hi + 0.05) / (lo + 0.05);
};

// --- The bottom scrim -------------------------------------------------------
// Main.tsx renders a bottom scrim as a 45%-tall, bottom-anchored div carrying
//   linear-gradient(to bottom,
//     transparent 0%, ink@0.12 30%, ink@0.42 55%, ink@0.74 78%, ink@0.88 100%)
//
// The gradient percentages are LOCAL TO THAT 45% BOX, not to the frame. Frame
// y=55% is the box's 0% and frame y=100% is its 100%. Reading the stops as
// frame percentages — the easy mistake — overstates protection at the caption
// by roughly 2x and invents protection for the headline that does not exist.
//
// The consequence worth stating plainly: ABOVE 55% OF FRAME HEIGHT THE SCRIM
// CONTRIBUTES NOTHING. Headlines sit at heroAnchor 24-44%, so they are
// currently protected by the global grade dimming alone. They are the surfaces
// that a brightness lift would hurt first.
const SCRIM_TOP_PCT = 55;
const SCRIM_SPAN_PCT = 45;
const SCRIM_STOPS: ReadonlyArray<readonly [number, number]> = [
  [0, 0],
  [30, 0.12],
  [55, 0.42],
  [78, 0.74],
  [100, 0.88],
];

/** Scrim alpha at a given FRAME height percentage (0 = top, 100 = bottom). */
export function scrimAlphaAt(yPct: number): number {
  const local = ((yPct - SCRIM_TOP_PCT) / SCRIM_SPAN_PCT) * 100;
  if (local <= 0) return 0;
  if (local >= 100) return SCRIM_STOPS[SCRIM_STOPS.length - 1][1];
  for (let i = 1; i < SCRIM_STOPS.length; i++) {
    const [p0, a0] = SCRIM_STOPS[i - 1];
    const [p1, a1] = SCRIM_STOPS[i];
    if (local <= p1) {
      const t = (local - p0) / (p1 - p0);
      return a0 + (a1 - a0) * t;
    }
  }
  return SCRIM_STOPS[SCRIM_STOPS.length - 1][1];
}

// --- Prism bloom veils ------------------------------------------------------
// PrismLayers paints three screen-blended radial veils over the media. Their
// alphas scale with prism.bloom (0..1, a raw rng draw) and the scene strength
// (0, 0.7 or 1 from prismSceneStrength). Centres and peak alphas, from source:
//   y=24%  white          (0.09 + 0.06*bloom) * strength
//   y=30%  primarySoft    (0.10 + 0.08*bloom) * strength
//   y=78%  secondary      (0.08 + 0.06*bloom) * strength   <- over the caption
// Each falls off to transparent by ~60-65% of its radius; a triangular falloff
// over +-26 frame-% is a deliberately generous approximation of that.
const BLOOM_VEILS: ReadonlyArray<{ y: number; base: number; perBloom: number }> = [
  { y: 24, base: 0.09, perBloom: 0.06 },
  { y: 30, base: 0.1, perBloom: 0.08 },
  { y: 78, base: 0.08, perBloom: 0.06 },
];
const BLOOM_REACH_PCT = 26;

/** Combined screen-veil alpha reaching a frame-y, worst case across veils. */
export function bloomAlphaAt(yPct: number, bloom: number, strength: number): number {
  if (strength <= 0) return 0;
  let total = 0;
  for (const v of BLOOM_VEILS) {
    const d = Math.abs(yPct - v.y);
    if (d >= BLOOM_REACH_PCT) continue;
    const falloff = 1 - d / BLOOM_REACH_PCT;
    total += (v.base + v.perBloom * clamp01(bloom)) * strength * falloff;
  }
  return clamp01(total);
}

// --- Reading the grade ------------------------------------------------------
/**
 * Pull `brightness()` and `contrast()` out of a CSS filter string.
 *
 * gradeFilter() stays the single source of truth for the grade — parsing its
 * output means a future edit to GRADE_FILTERS propagates here automatically
 * instead of silently desyncing a duplicated table. Missing functions default
 * to 1 (identity), so a grade written without a brightness() is handled rather
 * than throwing.
 */
export function parseFilter(filter: string): { brightness: number; contrast: number } {
  const read = (name: string) => {
    const m = new RegExp(`${name}\\(([0-9.]+)\\)`).exec(filter);
    const v = m ? Number(m[1]) : NaN;
    return Number.isFinite(v) ? v : 1;
  };
  return { brightness: read("brightness"), contrast: read("contrast") };
}

// --- The zone model ---------------------------------------------------------
/**
 * How a surface is protected.
 *  - "plate": sits on a panel whose alpha we can SOLVE, so it absorbs a lift by
 *    thickening.
 *  - "halo": carries a dark shadow ring instead (giant numbers, chart labels —
 *    anywhere a rectangular panel would become the design). A halo has a FIXED
 *    strength, so it cannot absorb a lift; it can only be checked.
 */
export type Substrate = "plate" | "halo";

/**
 * Effective alpha credited to a halo. Deliberately below `haloShadow`'s own
 * 0.55/0.62 layers: the halo is blurred and sits around the glyph rather than
 * covering a solid area behind it, so crediting its nominal alpha would
 * overstate the protection and licence too large a lift.
 */
export const HALO_EFFECTIVE_ALPHA = 0.45;

export interface ZoneInput {
  /** Frame height percentage where the text sits (0 = top). */
  yPct: number;
  /** Colour the text is painted in. */
  textHex: string;
  /** Contrast floor: CR_BODY for reading copy, CR_DISPLAY at >= 42px. */
  targetCR: number;
  /** Opaque plate colour available to this zone. */
  plateHex: string;
  /** Which kind of substrate this surface has. Defaults to "plate". */
  substrate?: Substrate;
  /**
   * Protection this surface had BEFORE the halo work — 0 for the many that had
   * literally none. Used as the non-regression baseline (see below).
   */
  legacyAlpha?: number;
  /**
   * Effective halo alpha for this surface. Giant display type can carry a much
   * heavier halo than body copy before it reads as clutter, and it needs to:
   * a halo only darkens what is already there, so protecting light text over a
   * BRIGHTENED backdrop takes real weight.
   */
  haloAlpha?: number;
}

export interface MediaInput {
  look: LookConfig;
  palette: Palette;
  /** Extra brightness granted to the photo. 0 = today's behaviour. */
  lift: number;
  /** prismSceneStrength() for the scene: 0, 0.7 or 1. */
  prismStrength: number;
  /** PrismConfig.bloom, a raw 0..1 draw. */
  prismBloom: number;
  /**
   * Risk margin for backdrops that are worse than a flat field: heavy overlays,
   * multi-copy blend layers, high-contrast grades. Folded in at the end as
   * `L + busyness*(1 - L)` so it pushes toward white, never toward black.
   */
  busyness: number;
  /**
   * Worst-case sRGB value of the incoming media before grading. 1.0 is a fully
   * blown highlight. 0.92 is used by default: a genuine 1.0 is rare enough that
   * solving for it thickens every plate in the catalogue to protect a handful
   * of frames. Raise it if white-sky footage shows problems.
   */
  worstMediaValue?: number;
}

/**
 * Worst-case relative luminance arriving at one zone, after the whole stack:
 * grade brightness -> grade contrast -> prism media lift -> bloom veils ->
 * scrim -> busyness margin.
 *
 * The first four steps run in sRGB VALUE space because that is what CSS filters
 * and screen blends operate on; the result is linearised once, and the scrim
 * composite and busyness margin are then applied in luminance space. Mixing the
 * two is an approximation, but a conservative one — alpha compositing a dark
 * scrim is close to linear over this range, and erring high only thickens
 * plates.
 */
export function zoneLuminance(media: MediaInput, yPct: number): number {
  const { brightness, contrast } = parseFilter(gradeFilter(media.look));

  let v = clamp01(media.worstMediaValue ?? 0.92);
  v = clamp01(v * brightness * (1 + Math.max(0, media.lift)));
  v = clamp01((v - 0.5) * contrast + 0.5);
  v = clamp01(v * (1 + 0.28 * Math.max(0, media.prismStrength)));

  const veil = bloomAlphaAt(yPct, media.prismBloom, media.prismStrength);
  v = clamp01(v + veil * (1 - v));

  let L = greyLuminance(v);

  const aScrim = scrimAlphaAt(yPct);
  if (aScrim > 0) L = aScrim * relLuminance(media.palette.ink) + (1 - aScrim) * L;

  return clamp01(L + clamp01(media.busyness) * (1 - L));
}

/**
 * Minimum plate alpha that brings `Lbg` down to where `textHex` clears
 * `targetCR`. Returns 0 when the zone already passes unaided.
 *
 * Closed form. Light text over a dark plate needs
 *   (Ltext + 0.05) / (Lresult + 0.05) >= CR
 * so the highest luminance the text tolerates is
 *   need = (Ltext + 0.05)/CR - 0.05
 * and compositing the plate at alpha a gives Lresult = a*Lplate + (1-a)*Lbg,
 * which solves to a = (Lbg - need) / (Lbg - Lplate).
 */
export function solvePlateAlpha(
  Lbg: number,
  plateHex: string,
  textHex: string,
  targetCR: number,
): number {
  const Ltext = relLuminance(textHex);
  const need = (Ltext + 0.05) / targetCR - 0.05;
  if (need <= 0) return PLATE_CEILING; // text too dark to ever pass on a dark plate
  if (Lbg <= need) return 0;

  const Lplate = relLuminance(plateHex);
  // A plate no darker than the backdrop cannot help; cap rather than divide by
  // a non-positive denominator.
  if (Lplate >= Lbg) return PLATE_CEILING;

  const a = (Lbg - need) / (Lbg - Lplate);
  return Math.max(0, Math.min(PLATE_CEILING, a));
}

/** Does this zone clear its floor at the given plate alpha? */
export function zonePasses(
  Lbg: number,
  plateHex: string,
  textHex: string,
  targetCR: number,
  alpha: number,
): boolean {
  const Lresult = alpha * relLuminance(plateHex) + (1 - alpha) * Lbg;
  return contrastRatio(relLuminance(textHex), Lresult) >= targetCR - 1e-9;
}

export interface ZoneVerdict {
  name: string;
  yPct: number;
  backdropLuminance: number;
  requiredAlpha: number;
  /** Contrast ratio actually achieved at `requiredAlpha`. */
  achievedCR: number;
  /** True when the zone cannot be made to pass within PLATE_CEILING. */
  unsatisfiable: boolean;
  /**
   * True when the zone still sits below its WCAG target after its substrate.
   * Reported rather than gated: several surfaces have been below target since
   * long before any of this, so blocking the lift on them would punish the
   * lift for a problem it neither caused nor can fix. Keeping the flag means
   * the debt stays visible instead of being laundered into a pass.
   */
  belowTarget?: boolean;
}

export interface ContrastBudget {
  /**
   * Extra photo brightness this look can afford, solved by binary search
   * against the two criteria below. 0 means the look is already spending its
   * whole contrast budget on legibility.
   */
  brightnessLift: number;
  zones: ZoneVerdict[];
  /** Highest alpha any plated zone needed. */
  maxAlpha: number;
  /** True when any zone cannot pass within PLATE_CEILING at this lift. */
  anyUnsatisfiable: boolean;
}

/**
 * Evaluate every zone at one lift. Returns null verdicts plus whether this lift
 * is ACCEPTABLE, judged by two different rules depending on the substrate.
 *
 * PLATED zones get an ABSOLUTE rule: the solved alpha must stay at or under
 * PLATE_CEILING and actually clear the WCAG floor. Plates can absorb a lift by
 * thickening, so holding them to the real standard is fair.
 *
 * HALO zones get a NON-REGRESSION rule: contrast after the lift must be at
 * least what the surface had BEFORE any of this work. They cannot be held to an
 * absolute floor, and pretending otherwise would make the whole exercise fail
 * for the wrong reason — accent-coloured text at body size cannot reach 4.5:1
 * over ANY mid-tone backdrop, lift or no lift. `theme.secondaryColor` on a
 * cyan pack sits near luminance 0.55, which needs a backdrop under 0.08 to
 * clear 4.5:1, and no photograph survives being crushed that far. That is a
 * pre-existing property of colouring small text with a brand accent, not
 * something a brightness decision created or can fix — changing it means
 * changing the text colour, which is a design call, not a contrast one.
 *
 * So the honest question for those surfaces is "does the lift make this worse
 * than it already was?" and the honest answer has to be no. The halo added
 * ahead of this buys real headroom: it is what the lift then spends.
 */
function evaluateAt(
  media: MediaInput,
  zones: ReadonlyArray<ZoneInput & { name: string }>,
  lift: number,
): { verdicts: ZoneVerdict[]; acceptable: boolean } {
  const verdicts: ZoneVerdict[] = [];
  let acceptable = true;

  for (const z of zones) {
    const substrate = z.substrate ?? "plate";
    const Ltext = relLuminance(z.textHex);
    const Lbg = zoneLuminance({ ...media, lift }, z.yPct);

    if (substrate === "plate") {
      const alpha = solvePlateAlpha(Lbg, z.plateHex, z.textHex, z.targetCR);
      const Lresult = alpha * relLuminance(z.plateHex) + (1 - alpha) * Lbg;
      const ok = zonePasses(Lbg, z.plateHex, z.textHex, z.targetCR, alpha) && alpha <= PLATE_CEILING;
      if (!ok) acceptable = false;
      verdicts.push({
        name: z.name,
        yPct: z.yPct,
        backdropLuminance: Lbg,
        requiredAlpha: alpha,
        achievedCR: contrastRatio(Ltext, Lresult),
        unsatisfiable: !ok,
      });
      continue;
    }

    // Halo: fixed strength, so compare against the pre-halo baseline at lift 0.
    const halo = z.haloAlpha ?? HALO_EFFECTIVE_ALPHA;
    const Lnow = halo * 0 + (1 - halo) * Lbg;
    const Lbase = zoneLuminance({ ...media, lift: 0 }, z.yPct);
    const legacy = z.legacyAlpha ?? 0;
    const Lwas = legacy * 0 + (1 - legacy) * Lbase;
    const crNow = contrastRatio(Ltext, Lnow);
    const crWas = contrastRatio(Ltext, Lwas);
    // NON-REGRESSION is the gate. Holding halo surfaces to an absolute WCAG
    // target instead sounds stricter but is actually wrong: several of them sit
    // below their target at lift 0 and always have, so an absolute gate blocks
    // the lift for a reason the lift did not cause and cannot fix. Whether a
    // surface clears its target is reported separately (belowTarget) so it stays
    // visible instead of being silently laundered into a pass.
    const ok = crNow >= crWas - 1e-9;
    if (!ok) acceptable = false;
    verdicts.push({
      name: z.name,
      yPct: z.yPct,
      backdropLuminance: Lbg,
      requiredAlpha: halo,
      achievedCR: crNow,
      unsatisfiable: !ok,
      belowTarget: crNow < z.targetCR,
    });
  }

  return { verdicts, acceptable };
}

/** Largest lift this look can afford. Binary search; 0 when it can afford none. */
export function solveBrightnessLift(
  media: MediaInput,
  zones: ReadonlyArray<ZoneInput & { name: string }>,
  maxLift = MAX_BRIGHTNESS_LIFT,
): number {
  if (!evaluateAt(media, zones, 0).acceptable) return 0;
  let lo = 0;
  let hi = maxLift;
  for (let i = 0; i < 14; i++) {
    const mid = (lo + hi) / 2;
    if (evaluateAt(media, zones, mid).acceptable) lo = mid;
    else hi = mid;
  }
  // Round DOWN to a hundredth: a lift is a visual decision, and reporting
  // 0.2734 implies a precision the worst-case model does not have.
  return Math.floor(lo * 100) / 100;
}

/**
 * Ceiling on the search. Past ~35% the grade stops reading as "a brighter
 * photograph" and starts reading as an unfinished grade, whatever the numbers
 * say — so this is a taste bound, not a contrast one.
 */
export const MAX_BRIGHTNESS_LIFT = 0.35;

/**
 * Solve the lift and every zone for one video.
 *
 * `zones` is passed in rather than hardcoded so the caller owns the inventory —
 * a table baked in here would quietly go stale as scene types are added.
 */
export function deriveContrastBudget(
  media: MediaInput,
  zones: ReadonlyArray<ZoneInput & { name: string }>,
): ContrastBudget {
  const lift = solveBrightnessLift(media, zones);
  const { verdicts } = evaluateAt(media, zones, lift);
  return {
    brightnessLift: lift,
    zones: verdicts,
    maxAlpha: verdicts.reduce((m, v) => Math.max(m, v.requiredAlpha), 0),
    anyUnsatisfiable: verdicts.some((v) => v.unsatisfiable),
  };
}

// ============================================================================
// The zone table — the surfaces the lift is answerable to
// ----------------------------------------------------------------------------
// Drawn from TEXT_ZONES.md, which inventoried all 103 text surfaces drawn over
// the media. This is not all of them: it is the ones that BIND, i.e. the worst
// case in each (position, colour, substrate) class. Adding a surface that is
// strictly better protected than one already here would not change the answer.
//
// `legacyAlpha` records what protection the surface had BEFORE the halo work,
// which is the non-regression baseline. A same-hue coloured glow counts as ZERO:
// it shares the text's own hue and so adds no luminance separation whatsoever.
// ============================================================================
export interface ZoneContext {
  palette: Palette;
  /** Opaque plate colour from the finish, i.e. ft.panelBgBase(palette). */
  plateHex: string;
  /** look.heroAnchor — where the headline stack sits. */
  heroAnchorPct: number;
  primaryColor: string;
  secondaryColor: string;
}

export function videoZones(ctx: ZoneContext): Array<ZoneInput & { name: string }> {
  const P = ctx.plateHex;
  return [
    // --- plated: absorb a lift by thickening ---------------------------------
    { name: "caption band", yPct: 74, textHex: "#ffffff", targetCR: CR_BODY, plateHex: P, substrate: "plate" },
    { name: "headline", yPct: ctx.heroAnchorPct, textHex: "#f8fafc", targetCR: CR_DISPLAY, plateHex: P, substrate: "plate" },
    { name: "body copy", yPct: ctx.heroAnchorPct + 14, textHex: "#f8fafc", targetCR: CR_BODY, plateHex: P, substrate: "plate" },

    // --- halo only: fixed strength, judged on non-regression -----------------
    // Giant display numbers. A rectangular plate behind a 180px count-up would
    // become the design, so these carry a halo instead — a heavy one, because
    // a halo only darkens what is already there and these sit over the
    // brightest part of the frame. The accent is luminance-clamped so the text
    // stays reliably LIGHTER than its own halo; unclamped, `clean-cobalt` at
    // 0.235 was dark text on a light field and the halo made it worse.
    { name: "metric giant number", yPct: 45, textHex: clampAccentLuminance(ctx.primaryColor), targetCR: CR_DISPLAY, plateHex: P, substrate: "halo", legacyAlpha: 0, haloAlpha: 0.72 },
    { name: "countdown number", yPct: 45, textHex: clampAccentLuminance(ctx.primaryColor), targetCR: CR_DISPLAY, plateHex: P, substrate: "halo", legacyAlpha: 0, haloAlpha: 0.72 },
    { name: "metric label", yPct: 55, textHex: clampAccentLuminance(ctx.secondaryColor), targetCR: CR_DISPLAY, plateHex: P, substrate: "halo", legacyAlpha: 0, haloAlpha: 0.62 },
    { name: "testimonial eyebrow", yPct: 62, textHex: clampAccentLuminance(ctx.secondaryColor), targetCR: CR_BODY, plateHex: P, substrate: "halo", legacyAlpha: 0, haloAlpha: 0.62 },
    // 70%/75% white composites, approximated as their flat greys.
    { name: "chart axis label", yPct: 60, textHex: "#b3b3b3", targetCR: CR_BODY, plateHex: P, substrate: "halo", legacyAlpha: 0, haloAlpha: 0.62 },
    { name: "outro handle", yPct: 60, textHex: "#bfbfbf", targetCR: CR_DISPLAY, plateHex: P, substrate: "halo", legacyAlpha: 0, haloAlpha: 0.62 },
    // These already carried a genuine dark blurred shadow, so they get credit
    // for it — crediting them zero would overstate the headroom the halo buys.
    { name: "lower-third minimal", yPct: 82, textHex: "#ffffff", targetCR: CR_DISPLAY, plateHex: P, substrate: "halo", legacyAlpha: 0.25, haloAlpha: 0.62 },
    { name: "testimonial quote", yPct: 66, textHex: "#ffffff", targetCR: CR_DISPLAY, plateHex: P, substrate: "halo", legacyAlpha: 0.25, haloAlpha: 0.68 },
  ];
}

/**
 * Busyness margin for a look — how much worse than a flat field its backdrop
 * is likely to be. Kept small and additive; it is a safety margin, not a model.
 */
export function busynessFor(
  look: LookConfig,
  overlayType: string,
  blendCopies: number,
): number {
  const { contrast } = parseFilter(gradeFilter(look));
  let b = 0.1 * Math.max(0, contrast - 1);
  b += 0.06 * Math.max(0, blendCopies);
  if (overlayType === "aurora" || overlayType === "particles" || overlayType === "fantasy-sparks") {
    b += 0.08;
  }
  return clamp01(b);
}

/** Contrast floor appropriate to a rendered font size. */
export const targetForSize = (px: number) => (px >= DISPLAY_SIZE_PX ? CR_DISPLAY : CR_BODY);

// ============================================================================
// Halos — the substrate for text that cannot carry a plate
// ----------------------------------------------------------------------------
// A rectangular plate is wrong behind a 180px count-up number or a chart axis
// label: it becomes the design instead of supporting it. Those surfaces get a
// dark halo instead — two shadow layers, one tight for edge definition and one
// soft for separation.
//
// The property this relies on: a dark halo is nearly INVISIBLE over a dark
// backdrop and decisive over a bright one. So it costs nothing on the footage
// where text was already fine, and rescues the footage where it was not. That
// is what makes it safe to apply broadly.
//
// It also fixes a specific trap. FINISH_TOKENS.textGlow returns the literal
// string "none" on the glass and print finishes and a SAME-HUE glow on neon —
// so surfaces whose only protection is `ft.textGlow(color)` have nothing on
// half the catalogue, and on neon they have a glow that shares the text's own
// hue and therefore adds no luminance separation at all.
// ============================================================================

/**
 * Dark halo sized to the text it sits behind. `strength` scales both layers;
 * 1 is the default weight, below ~0.6 it stops doing useful work.
 */
export function haloShadow(sizePx = 40, strength = 1): string {
  const s = Math.max(0, strength);
  const tight = Math.max(1, Math.round(sizePx * 0.035));
  const soft = Math.max(6, Math.round(sizePx * 0.3));
  return (
    `0 ${tight}px ${tight * 2}px rgba(0,0,0,${(0.55 * s).toFixed(2)}), ` +
    `0 ${Math.round(tight * 1.6)}px ${soft}px rgba(0,0,0,${(0.62 * s).toFixed(2)})`
  );
}

/**
 * A finish's decorative glow with a guaranteed dark halo layered under it.
 * Pass whatever `ft.textGlow(color)` returned; "none" is handled.
 */
export function readableGlow(decorative: string, sizePx = 40, strength = 1): string {
  const halo = haloShadow(sizePx, strength);
  return !decorative || decorative === "none" ? halo : `${decorative}, ${halo}`;
}

/**
 * The same halo as a `filter`, for text where `text-shadow` cannot reach:
 * `background-clip: text` fills (the shadow composites against the clipped
 * background rather than the glyphs) and `-webkit-text-stroke` outlines.
 * drop-shadow applies to the RENDERED result, so it follows the glyph shapes
 * in both cases.
 */
export function haloFilter(sizePx = 40, strength = 1): string {
  const s = Math.max(0, strength);
  const tight = Math.max(1, Math.round(sizePx * 0.03));
  const soft = Math.max(4, Math.round(sizePx * 0.16));
  return (
    `drop-shadow(0 ${tight}px ${tight * 2}px rgba(0,0,0,${(0.5 * s).toFixed(2)})) ` +
    `drop-shadow(0 ${Math.round(tight * 1.5)}px ${soft}px rgba(0,0,0,${(0.6 * s).toFixed(2)}))`
  );
}

/**
 * Halo for SVG `<text>`, where `text-shadow` does not apply at all. Painting
 * the stroke UNDER the fill (`paint-order: stroke`) gives a clean outline that
 * never thins the glyph.
 */
export function svgHalo(strokeWidth = 3) {
  return {
    stroke: "rgba(0,0,0,0.72)",
    strokeWidth,
    paintOrder: "stroke" as const,
    strokeLinejoin: "round" as const,
  };
}

/** Grades whose brightness is already low enough to be doing contrast work. */
export const DIM_GRADES: ReadonlySet<ColorGrade> = new Set(["noir", "neutral", "cool"]);

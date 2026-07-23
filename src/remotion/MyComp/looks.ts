// ============================================================================
// looks.ts — Seeded procedural "Look System"
// ----------------------------------------------------------------------------
// The single biggest reason auto-generated videos looked identical was that the
// per-video `seed` only drove micro-motion (which transition / shape orbit /
// text animation). The DOMINANT visuals — background treatment, on-screen
// "chrome" (rings, brackets, progress bar, scene counter), color grade, layout
// anchor and motion personality — were HARDCODED the same in every render.
//
// This module derives a rich, deterministic `LookConfig` from the per-video
// seed so those dominant visuals change between videos. Everything here is a
// PURE function of the seed — no Math.random / Date.now — so it is safe under
// Remotion's concurrent, frame-parallel renderer.
// ============================================================================

// --- Deterministic PRNG (mulberry32). Same seed -> same stream, forever. ----
export function makeRng(seed: number): () => number {
  let a = (seed >>> 0) || 0x9e3779b9;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export const pick = <T,>(rng: () => number, arr: readonly T[]): T =>
  arr[Math.floor(rng() * arr.length) % arr.length];

// ----------------------------------------------------------------------------
export type BackgroundStyle =
  | "full-bleed"
  | "duotone"
  | "gradient-wash"
  | "spotlight"
  | "cinema-bars";
export type ChromeStyle =
  | "hud-heavy"
  | "minimal"
  | "editorial"
  | "broadcast"
  | "kinetic";
export type ColorGrade = "neutral" | "warm" | "cool" | "noir" | "vibrant" | "faded";
export type MotionFeel = "calm" | "snappy" | "bouncy" | "cinematic";
/**
 * Per-video TEXT LAYOUT personality — where and how the main text blocks sit.
 * Before this existed every video centered every block ("the same template"):
 *  - center-stack: classic centered column (the original layout)
 *  - left-rail:    editorial left-aligned column with a wide right margin
 *  - banner-low:   text block sits in the lower half, poster-style
 *  - top-ticker:   text pinned high like a news ticker / headline card
 */
export type TextLayout = "center-stack" | "left-rail" | "banner-low" | "top-ticker";
/** Title styling treatment: solid (classic), outline stroke, gradient fill, or boxed plate. */
export type TitleTreatment = "solid" | "outline" | "gradient-fill" | "boxed";

export interface LookConfig {
  seed: number;
  background: BackgroundStyle;
  chrome: ChromeStyle;
  grade: ColorGrade;
  motion: MotionFeel;
  /** Deep 0..1 edge darkening for BackgroundLayer vignette. */
  vignette: number;
  showProgressBar: boolean;
  showSceneCounter: boolean;
  showCornerBrackets: boolean;
  showRings: boolean;
  showFloatingShapes: boolean;
  accentDensity: "subtle" | "normal" | "high";
  /** Vertical anchor (top %) for hero / centered content blocks. */
  heroAnchor: number;
  titleCase: "upper" | "as-is";
  /** Per-video text layout personality (alignment + anchoring of text blocks). */
  textLayout: TextLayout;
  /** Global type-scale multiplier (~0.92–1.22) applied to AnimatedText sizes. */
  fontScale: number;
  /** How scene TITLES are dressed: solid / outline / gradient-fill / boxed. */
  titleTreatment: TitleTreatment;
  /** Angle used by gradient-wash / grade tint layers. */
  bgAngle: number;
  /** Spring stiffness multiplier driven by motion personality. */
  springMul: number;
  /** Camera-motion pool flavored by the motion personality. */
  cameraPool: string[];
  /** Whether to damp the global HUD overlay so it doesn't fight minimal looks. */
  mutedHud: boolean;
}

// Map a chrome personality -> which decorative layers are visible. This is what
// actually breaks the "every video is the same template" feeling.
const CHROME_TOGGLES: Record<
  ChromeStyle,
  {
    bar: boolean;
    counter: boolean;
    brackets: boolean;
    rings: boolean;
    floating: boolean;
    density: "subtle" | "normal" | "high";
    mutedHud: boolean;
  }
> = {
  "hud-heavy": { bar: true, counter: true, brackets: true, rings: true, floating: true, density: "high", mutedHud: false },
  minimal: { bar: false, counter: false, brackets: false, rings: false, floating: true, density: "subtle", mutedHud: true },
  editorial: { bar: false, counter: true, brackets: false, rings: false, floating: true, density: "subtle", mutedHud: true },
  broadcast: { bar: true, counter: true, brackets: true, rings: false, floating: false, density: "subtle", mutedHud: false },
  kinetic: { bar: false, counter: false, brackets: true, rings: true, floating: true, density: "high", mutedHud: false },
};

const MOTION_PROFILES: Record<
  MotionFeel,
  { springMul: number; cameras: string[] }
> = {
  calm: { springMul: 0.8, cameras: ["zoom-slow", "ken-burns", "pan-horizontal"] },
  snappy: { springMul: 1.3, cameras: ["dynamic-zoom-rotate", "pan-tilt", "pulse-zoom"] },
  bouncy: { springMul: 1.12, cameras: ["pulse-zoom", "dynamic-zoom-rotate", "orbit-drift"] },
  cinematic: { springMul: 0.92, cameras: ["vertigo", "orbit-drift", "ken-burns"] },
};

/**
 * Derive the full per-video look from the seed. Deterministic and stable:
 * the same seed always yields the same look regardless of when/where it runs.
 */
export function deriveLook(seed: number): LookConfig {
  const s = (seed >>> 0) || 0x9e3779b9;
  const rng = makeRng(s);

  const background = pick(rng, [
    "full-bleed",
    "duotone",
    "gradient-wash",
    "spotlight",
    "cinema-bars",
  ] as const);
  const chrome = pick(rng, [
    "hud-heavy",
    "minimal",
    "editorial",
    "broadcast",
    "kinetic",
  ] as const);
  const grade = pick(rng, [
    "neutral",
    "warm",
    "cool",
    "noir",
    "vibrant",
    "faded",
  ] as const);
  const motion = pick(rng, ["calm", "snappy", "bouncy", "cinematic"] as const);

  const t = CHROME_TOGGLES[chrome];
  const m = MOTION_PROFILES[motion];

  return {
    seed: s,
    background,
    chrome,
    grade,
    motion,
    vignette: 0.55 + rng() * 0.4,
    showProgressBar: t.bar,
    showSceneCounter: t.counter,
    showCornerBrackets: t.brackets,
    showRings: t.rings,
    showFloatingShapes: t.floating,
    accentDensity: t.density,
    heroAnchor: pick(rng, [24, 28, 32, 38, 44]),
    titleCase: pick(rng, ["upper", "as-is"] as const),
    bgAngle: Math.floor(rng() * 360),
    // NOTE: new dimensions draw AFTER all original ones so existing seeds keep
    // the exact same background/chrome/grade/motion they had before.
    textLayout: pick(rng, [
      "center-stack",
      "left-rail",
      "banner-low",
      "top-ticker",
    ] as const),
    fontScale: pick(rng, [0.92, 1.0, 1.1, 1.22]),
    titleTreatment: pick(rng, ["solid", "outline", "gradient-fill", "boxed"] as const),
    springMul: m.springMul,
    cameraPool: m.cameras,
    mutedHud: t.mutedHud,
  };
}

// --- Color-grade CSS filters for the background image ------------------------
// Brightness is a touch above the original crush values: the multi-stop scrim
// in Main's BackgroundLayer now carries the text-contrast duty, so the photo
// can keep more life without costing readability at the subtitle band.
const GRADE_FILTERS: Record<ColorGrade, string> = {
  neutral: "brightness(0.68) contrast(1.16) saturate(1.06)",
  warm: "brightness(0.7) contrast(1.15) saturate(1.16) sepia(0.18) hue-rotate(-10deg)",
  cool: "brightness(0.66) contrast(1.18) saturate(1.1) hue-rotate(14deg)",
  noir: "brightness(0.6) contrast(1.38) saturate(0.3)",
  vibrant: "brightness(0.74) contrast(1.26) saturate(1.5)",
  faded: "brightness(0.76) contrast(1.0) saturate(0.84)",
};

/** CSS filter for the main background image, honoring the look's grade. */
export function gradeFilter(look: LookConfig, brightnessFloor = 0): string {
  const base = GRADE_FILTERS[look.grade] ?? GRADE_FILTERS.neutral;
  // For duotone we desaturate first so the color layer reads cleanly.
  if (look.background === "duotone") {
    return "brightness(0.7) contrast(1.25) saturate(0.15)";
  }
  if (brightnessFloor > 0 && look.grade === "noir") {
    return "brightness(0.62) contrast(1.35) saturate(0.3)";
  }
  return base;
}

// ============================================================================
// Color engine — pure color math (no RNG, no draw-order risk) that derives a
// full working palette from the two style-pack hexes. Every component that
// used to eyeball `${color}55` alpha-suffixes can build on tints/shades/inks
// computed the same way, which is most of what "art-directed" reads as.
// ============================================================================

export const hexToRgb = (hex: string): { r: number; g: number; b: number } => {
  const h = hex.replace("#", "");
  const full = h.length === 3 ? h.split("").map((c) => c + c).join("") : h.slice(0, 6);
  const n = parseInt(full.padEnd(6, "0"), 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
};

export const rgbToHex = (r: number, g: number, b: number): string =>
  "#" +
  [r, g, b]
    .map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0"))
    .join("");

/** Linear blend a→b by t (0..1) in sRGB. */
export const mixHex = (a: string, b: string, t: number): string => {
  const ca = hexToRgb(a);
  const cb = hexToRgb(b);
  return rgbToHex(ca.r + (cb.r - ca.r) * t, ca.g + (cb.g - ca.g) * t, ca.b + (cb.b - ca.b) * t);
};

export const tint = (hex: string, t: number): string => mixHex(hex, "#ffffff", t);
export const shade = (hex: string, t: number): string => mixHex(hex, "#000000", t);

/** WCAG relative luminance 0..1. */
export const relLuminance = (hex: string): number => {
  const { r, g, b } = hexToRgb(hex);
  const lin = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
};

/** Near-white or near-black ink, whichever actually contrasts with `bg`. */
export const inkOn = (bg: string): string =>
  relLuminance(bg) > 0.35 ? "#0b0e14" : "#f8fafc";

/** 8-digit hex with alpha 0..1 — replaces ad-hoc `${color}55` suffixing. */
export const withAlpha = (hex: string, alpha: number): string => {
  const a = Math.round(Math.max(0, Math.min(1, alpha)) * 255)
    .toString(16)
    .padStart(2, "0");
  return hex.slice(0, 7) + a;
};

export interface Palette {
  primary: string;
  secondary: string;
  /** Lifted primary for highlights / emphasized words. */
  primarySoft: string;
  /** Deep primary for background tints and gradient roots. */
  primaryDeep: string;
  secondaryDeep: string;
  /** Brand-tinted near-black — scrims and panels tint toward the pack. */
  ink: string;
  /** Glass panel fill (already alpha'd). */
  surface: string;
  /** Hairline border color (already alpha'd). */
  edge: string;
  onPrimary: string;
  onSecondary: string;
  /** Deep 3-stop background ramp: primary root → tinted black → secondary root. */
  bgStops: [string, string, string];
}

/** Pure function of the two style-pack hexes — safe to call anywhere. */
export function derivePalette(primary: string, secondary: string): Palette {
  const primaryDeep = shade(primary, 0.55);
  const secondaryDeep = shade(secondary, 0.55);
  const ink = mixHex("#0a0c12", primaryDeep, 0.22);
  return {
    primary,
    secondary,
    primarySoft: tint(primary, 0.3),
    primaryDeep,
    secondaryDeep,
    ink,
    surface: withAlpha(mixHex("#07080d", primaryDeep, 0.28), 0.62),
    edge: withAlpha(tint(primary, 0.45), 0.18),
    onPrimary: inkOn(primary),
    onSecondary: inkOn(secondary),
    bgStops: [withAlpha(primaryDeep, 0.55), ink, withAlpha(secondaryDeep, 0.45)],
  };
}

// ============================================================================
// Finish — the per-video DESIGN LANGUAGE. One coherent token set (radii,
// panel fills, borders, glow policy) consumed by every panel/text component,
// so a video reads as one art direction instead of parts styled in isolation.
//
// Derived on an INDEPENDENT rng stream (polish.ts precedent): existing seeds
// keep the exact deriveLook draws they had, and the finish can be weighted by
// the overlay/chrome so neon dressing never lands on editorial/clean packs.
// ============================================================================

export type Finish = "glass" | "print" | "neon" | "soft";

export interface FinishTokens {
  radiusPanel: number;
  radiusChip: number;
  radiusPill: number;
  panelBg: (p: Palette) => string;
  panelBorder: (p: Palette) => string;
  panelShadow: string;
  /** Text glow policy — "none" for print/soft, single soft layer for neon. */
  textGlow: (c: string) => string;
  accentBarWidth: number;
}

export const FINISH_TOKENS: Record<Finish, FinishTokens> = {
  glass: {
    radiusPanel: 20,
    radiusChip: 12,
    radiusPill: 999,
    panelBg: (p) => p.surface,
    panelBorder: (p) => `1px solid ${p.edge}`,
    panelShadow: "0 24px 60px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.07)",
    textGlow: () => "none",
    accentBarWidth: 4,
  },
  print: {
    radiusPanel: 4,
    radiusChip: 2,
    radiusPill: 6,
    panelBg: (p) => withAlpha(p.ink, 0.78),
    panelBorder: () => "none",
    panelShadow: "0 12px 40px rgba(0,0,0,0.35)",
    textGlow: () => "none",
    accentBarWidth: 6,
  },
  neon: {
    radiusPanel: 14,
    radiusChip: 8,
    radiusPill: 999,
    panelBg: () => "rgba(0,0,0,0.55)",
    panelBorder: (p) => `1px solid ${withAlpha(p.primary, 0.25)}`,
    panelShadow: "0 10px 40px rgba(0,0,0,0.5)",
    textGlow: (c) => `0 0 8px ${withAlpha(c, 0.8)}, 0 0 24px ${withAlpha(c, 0.4)}`,
    accentBarWidth: 4,
  },
  soft: {
    radiusPanel: 12,
    radiusChip: 8,
    radiusPill: 999,
    panelBg: () => "rgba(0,0,0,0.45)",
    panelBorder: () => "1px solid rgba(255,255,255,0.08)",
    panelShadow: "0 14px 44px rgba(0,0,0,0.4)",
    textGlow: () => "0 2px 12px rgba(0,0,0,0.5)",
    accentBarWidth: 3,
  },
};

const weightedPick = <T,>(rng: () => number, entries: [T, number][]): T => {
  const total = entries.reduce((a, [, w]) => a + w, 0);
  let roll = rng() * total;
  for (const [v, w] of entries) {
    roll -= w;
    if (roll <= 0) return v;
  }
  return entries[entries.length - 1][0];
};

export function deriveFinish(
  seed: number,
  look: LookConfig,
  overlayType: string,
): Finish {
  const rng = makeRng((((seed ^ 0x7f4a7c15) + 11) >>> 0) || 1);
  // Editorial chrome is a print/soft world regardless of overlay.
  if (look.chrome === "editorial") {
    return weightedPick(rng, [
      ["print", 0.55],
      ["soft", 0.45],
    ]);
  }
  if (overlayType === "grid-hud" || overlayType === "vhs-glitch") {
    return weightedPick(rng, [
      ["neon", 0.55],
      ["glass", 0.45],
    ]);
  }
  if (overlayType === "clean") {
    return weightedPick(rng, [
      ["print", 0.35],
      ["soft", 0.35],
      ["glass", 0.3],
    ]);
  }
  // aurora / particles / fantasy-sparks — soft ambient worlds.
  return weightedPick(rng, [
    ["glass", 0.5],
    ["soft", 0.5],
  ]);
}

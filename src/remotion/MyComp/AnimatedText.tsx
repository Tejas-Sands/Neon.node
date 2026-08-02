import React, { useMemo } from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig, Easing } from "remotion";
import { loadFont as loadShareTech } from "@remotion/google-fonts/ShareTechMono";
import { loadFont as loadOrbitron } from "@remotion/google-fonts/Orbitron";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadPlayfair } from "@remotion/google-fonts/PlayfairDisplay";
import { loadFont as loadSpaceGrotesk } from "@remotion/google-fonts/SpaceGrotesk";
import { loadFont as loadArchivo } from "@remotion/google-fonts/Archivo";
import { loadFont as loadSora } from "@remotion/google-fonts/Sora";
import { loadFont as loadBricolage } from "@remotion/google-fonts/BricolageGrotesque";
import { loadFont as loadFraunces } from "@remotion/google-fonts/Fraunces";
import { loadFont as loadJetBrains } from "@remotion/google-fonts/JetBrainsMono";
import { FINISH_TOKENS, inkOn, withAlpha, type Finish } from "./looks";
import { haloFilter } from "./contrast";

// Load all fonts so they are available in memory.
// Weights listed here are the ONLY real weights available at render time —
// requesting any other weight makes Chrome synthesize it (smeared, fuzzy
// strokes at 1080px). FONT_METRICS below is the single source of truth for
// which weight each role uses; never hardcode 800/900 in a component.
const fontShareTech = loadShareTech("normal", {
  subsets: ["latin"],
  weights: ["400"], // Share Tech Mono is a single-weight family — no bold exists
});
const fontOrbitron = loadOrbitron("normal", {
  subsets: ["latin"],
  weights: ["700", "900"],
});
const fontInter = loadInter("normal", { subsets: ["latin"], weights: ["600", "700", "800"] });
const fontPlayfair = loadPlayfair("normal", {
  subsets: ["latin"],
  weights: ["700", "800"],
});
// --- 2026-08 professional catalog. The five families above are retired-but-
// valid: still loaded, still legal in the schema (old props render forever),
// but no STYLE_PACK or prompt references them anymore.
const fontSpaceGrotesk = loadSpaceGrotesk("normal", {
  subsets: ["latin"],
  weights: ["500", "700"],
});
const fontArchivo = loadArchivo("normal", {
  subsets: ["latin"],
  weights: ["600", "700", "900"],
});
const fontSora = loadSora("normal", { subsets: ["latin"], weights: ["600", "800"] });
const fontBricolage = loadBricolage("normal", {
  subsets: ["latin"],
  weights: ["600", "800"],
});
const fontFraunces = loadFraunces("normal", {
  subsets: ["latin"],
  weights: ["600", "900"],
});
const fontJetBrains = loadJetBrains("normal", {
  subsets: ["latin"],
  weights: ["500", "700"],
});

const GLITCH_CHARS =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?";

// NOTE: "rise-mask", "flip-in", "clip-wipe" and "tracking-in" are RENDER-SIDE
// ONLY modes: they are picked by the seeded TEXT_ANIM_POOLS in Main.tsx and
// never appear in the props JSON, so the zod SceneSchema enum / Python
// ALLOWED_TEXT_ANIMATIONS do NOT need to know about them (no §4.5 sync dance).
type TextAnimationMode =
  | "typewriter"
  | "glitch-decode"
  | "fade-up"
  | "slide-in"
  | "word-by-word"
  | "scale-pop"
  | "blur-in"
  | "wave"
  | "rise-mask"
  | "flip-in"
  | "clip-wipe"
  | "tracking-in"
  | "none";

type FontFamilyName =
  | "Share Tech Mono"
  | "Orbitron"
  | "Inter"
  | "Playfair Display"
  | "Courier New"
  | "Space Grotesk"
  | "Archivo"
  | "Sora"
  | "Bricolage Grotesque"
  | "Fraunces"
  | "JetBrains Mono";

type OverlayType =
  | "grid-hud"
  | "particles"
  | "clean"
  | "vhs-glitch"
  | "fantasy-sparks"
  | "aurora";

interface AnimatedTextProps {
  text: string;
  glowColor?: string;
  fontFamilyName?: FontFamilyName;
  overlayType?: OverlayType;
  animationMode?: TextAnimationMode;
  /** Custom font size override. Default depends on overlay type */
  fontSize?: number;
  /** Per-video type-scale multiplier from the Look System (default 1). */
  fontScale?: number;
  /** "as-is" keeps the author's casing; default keeps the classic uppercase. */
  textCase?: "upper" | "as-is";
  /** Horizontal alignment inside the block (look.textLayout drives this). */
  align?: "center" | "left";
  /** Title dressing from the Look System; body copy stays "solid". */
  treatment?: "solid" | "outline" | "gradient-fill" | "boxed";
  /**
   * Motion-personality stiffness multiplier from the Look System (calm 0.8 ..
   * snappy 1.3) so text springs settle with the same feel as the rest of the
   * video's motion. Default 1 = the historical timing.
   */
  springMul?: number;
  /**
   * Per-video design language from deriveFinish. Controls glow policy, plate
   * fill, radius and accent bars so text plates match every other panel in
   * the video. Default "neon" = the historical dressing.
   */
  finish?: Finish;
  /**
   * Micro-detail "landing-pop" (microDetails.ts): a soft drop-shadow depth pop
   * as the text settles (frames ~12-32). Filter-only — composed through
   * mergeStyles so blur-in / halo filters survive; no transform, no reflow.
   */
  landingPop?: boolean;
  /**
   * Micro-detail "emphasis-sweep": ONE light sweep across the emphasized words
   * at `sweepFrame` (scene-local; DynamicScene passes energy.kineticStart).
   * Absolute overlay inside the emphasis span — zero layout impact.
   */
  emphasisSweep?: boolean;
  sweepFrame?: number;
  /**
   * Stat-hit (Q27a): when an emphasized token is numeric, it pulses and draws
   * an accent underline starting at this scene-local frame. Transform +
   * absolute overlay only — Pain Point 6 intact.
   */
  statHitFrame?: number;
}

// ---------------------------------------------------------------------------
// Keyword emphasis — the strongest single "professional editor" habit: the
// key word of a line (a number, an acronym, the main content word) is set in
// the accent color with a slight optical scale-up. Deterministic and pure
// (text in → indices out), and layout-safe: emphasis only changes color /
// shadow / a transform scale on an inline-block span, so line wrapping and
// the longest-word auto-fit are untouched (Pain Point 6 holds).
// ---------------------------------------------------------------------------
const EMPH_STOPWORDS = new Set([
  "the", "and", "for", "with", "this", "that", "your", "from", "into", "have",
  "will", "just", "what", "when", "where", "then", "than", "but", "not", "all",
  "can", "get", "got", "out", "you", "its", "it's", "their", "them", "was",
  "were", "are", "has", "had", "does", "did", "how", "why", "who", "his",
  "her", "our", "one", "two", "about", "over", "under", "more", "most",
]);

export const pickEmphasisIndices = (words: string[]): Set<number> => {
  const out = new Set<number>();
  // Emphasizing a 1-2 word line is just shouting the whole line.
  if (words.length < 3) return out;
  const bare = words.map((w) => w.replace(/[^A-Za-z0-9%$#.']/g, ""));
  // If half or more of the line is ALL-CAPS the caps carry no signal (the
  // style is simply uppercase) — only digits/stat tokens count then.
  const capsCount = bare.filter((b) => /^[A-Z]{2,}$/.test(b)).length;
  const capsAreStyle = capsCount / words.length >= 0.5;
  // Digits/stats are the strongest signal and always outrank acronyms — a
  // "GPT-5 CUTS LATENCY 40%" line must emphasize GPT-5 + 40%, never CUTS.
  const digitIdx: number[] = [];
  const acroIdx: number[] = [];
  bare.forEach((b, i) => {
    if (/[\d%$#]/.test(b)) digitIdx.push(i);
    else if (!capsAreStyle && /^[A-Z]{2,6}$/.test(b)) acroIdx.push(i);
  });
  [...digitIdx, ...acroIdx].forEach((i) => out.add(i));
  if (out.size === 0) {
    // Fallback: the longest content word (≥5 chars) is usually the subject.
    let best = -1;
    let bestLen = 4;
    bare.forEach((b, i) => {
      if (b.length > bestLen && !EMPH_STOPWORDS.has(b.toLowerCase())) {
        best = i;
        bestLen = b.length;
      }
    });
    if (best >= 0) out.add(best);
  }
  // Emphasize everything and you emphasize nothing.
  if (out.size > 2) {
    return new Set([...out].slice(0, 2));
  }
  return out;
};

/** Color/glow part of emphasis (transform scale is appended per mode). */
const emphasisColorStyle = (color: string): React.CSSProperties => ({
  color,
  textShadow: `0 0 16px ${color}55`,
});

// ---------------------------------------------------------------------------
// Per-font typographic metrics — em-based tracking (scales with auto-fit),
// per-family line-height, and the REAL loaded weights for display vs body
// roles. The old fixed `letterSpacing: 4px` was 0.14em at the 28px floor
// (gappy) and 0.05em at 80px; em units keep the optical tracking constant.
// ---------------------------------------------------------------------------
export const FONT_METRICS: Record<
  FontFamilyName,
  {
    trackTitleEm: number;
    trackBodyEm: number;
    lineHeight: number;
    displayWeight: number;
    bodyWeight: number;
  }
> = {
  "Share Tech Mono": { trackTitleEm: 0.02, trackBodyEm: 0.01, lineHeight: 1.18, displayWeight: 400, bodyWeight: 400 },
  Orbitron: { trackTitleEm: 0.045, trackBodyEm: 0.02, lineHeight: 1.16, displayWeight: 900, bodyWeight: 700 },
  Inter: { trackTitleEm: -0.01, trackBodyEm: 0, lineHeight: 1.12, displayWeight: 800, bodyWeight: 600 },
  "Playfair Display": { trackTitleEm: 0.005, trackBodyEm: 0.005, lineHeight: 1.14, displayWeight: 800, bodyWeight: 700 },
  "Courier New": { trackTitleEm: 0.01, trackBodyEm: 0.01, lineHeight: 1.2, displayWeight: 700, bodyWeight: 400 },
  "Space Grotesk": { trackTitleEm: -0.005, trackBodyEm: 0, lineHeight: 1.12, displayWeight: 700, bodyWeight: 500 },
  Archivo: { trackTitleEm: -0.015, trackBodyEm: 0, lineHeight: 1.08, displayWeight: 900, bodyWeight: 600 },
  Sora: { trackTitleEm: -0.01, trackBodyEm: 0.005, lineHeight: 1.16, displayWeight: 800, bodyWeight: 600 },
  "Bricolage Grotesque": { trackTitleEm: -0.01, trackBodyEm: 0, lineHeight: 1.1, displayWeight: 800, bodyWeight: 600 },
  Fraunces: { trackTitleEm: 0.005, trackBodyEm: 0.005, lineHeight: 1.12, displayWeight: 900, bodyWeight: 600 },
  "JetBrains Mono": { trackTitleEm: 0.01, trackBodyEm: 0.005, lineHeight: 1.2, displayWeight: 700, bodyWeight: 500 },
};

/** Map font family name to the loaded font CSS family string */
export const getFontFamily = (fontFamilyName: FontFamilyName): string => {
  switch (fontFamilyName) {
    case "Share Tech Mono":
      return fontShareTech.fontFamily;
    case "Orbitron":
      return fontOrbitron.fontFamily;
    case "Inter":
      return fontInter.fontFamily;
    case "Playfair Display":
      return fontPlayfair.fontFamily;
    case "Courier New":
      return "Courier New, monospace";
    case "Space Grotesk":
      return fontSpaceGrotesk.fontFamily;
    case "Archivo":
      return fontArchivo.fontFamily;
    case "Sora":
      return fontSora.fontFamily;
    case "Bricolage Grotesque":
      return fontBricolage.fontFamily;
    case "Fraunces":
      return fontFraunces.fontFamily;
    case "JetBrains Mono":
      return fontJetBrains.fontFamily;
    default:
      return fontInter.fontFamily;
  }
};

// ===========================================================================
// Internal animation renderers — each returns { text, wrapperStyle }
// ===========================================================================

/** Seeded pseudo-random for deterministic glitch per frame */
const seededChar = (seed: number): string => {
  const idx = Math.abs(Math.floor(Math.sin(seed * 9301 + 49297) * 233280)) % GLITCH_CHARS.length;
  return GLITCH_CHARS[idx];
};

/** 1. Typewriter — characters appear one by one with a blinking cursor */
const useTypewriter = (text: string, frame: number, durationFrames: number) => {
  const charsVisible = Math.floor(
    interpolate(frame, [0, durationFrames], [0, text.length], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    })
  );
  const cursorVisible = frame % 20 < 10;
  const displayed = text.slice(0, charsVisible) + (cursorVisible && charsVisible < text.length ? "▌" : "");
  return { text: displayed, wrapperStyle: {} as React.CSSProperties };
};

/** 2. Glitch-decode — the existing random character decode effect (deterministic) */
const useGlitchDecode = (text: string, frame: number, durationFrames: number) => {
  const progress = interpolate(frame, [0, durationFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const resolvedCount = Math.floor(progress * text.length);
  let result = "";
  for (let i = 0; i < text.length; i++) {
    if (i < resolvedCount) {
      result += text[i];
    } else if (text[i] === " ") {
      result += " ";
    } else {
      result += seededChar(Math.floor(frame / 3) * 100 + i);
    }
  }
  return { text: result, wrapperStyle: {} as React.CSSProperties };
};

/** 3. Fade-up — opacity + translateY spring entrance */
const useFadeUp = (text: string, frame: number, fps: number, springMul = 1) => {
  const progress = spring({ fps, frame, config: { damping: 80, stiffness: Math.round(100 * springMul) }, durationInFrames: 25 });
  const translateY = interpolate(progress, [0, 1], [40, 0]);
  const opacity = interpolate(progress, [0, 1], [0, 1]);
  return {
    text,
    wrapperStyle: {
      transform: `translateY(${translateY}px)`,
      opacity,
    } as React.CSSProperties,
  };
};

/** 4. Slide-in — horizontal slide from the left */
const useSlideIn = (text: string, frame: number, fps: number, springMul = 1) => {
  const progress = spring({ fps, frame, config: { damping: 60, stiffness: Math.round(120 * springMul) }, durationInFrames: 30 });
  const translateX = interpolate(progress, [0, 1], [-300, 0]);
  const opacity = interpolate(progress, [0, 1], [0, 1]);
  return {
    text,
    wrapperStyle: {
      transform: `translateX(${translateX}px)`,
      opacity,
    } as React.CSSProperties,
  };
};

/** 6. Scale-pop — bouncy spring scale-up entrance */
const useScalePop = (text: string, frame: number, fps: number, springMul = 1) => {
  const progress = spring({ fps, frame, config: { damping: 16, stiffness: Math.round(180 * springMul), mass: 0.8 }, durationInFrames: 22 });
  const scale = interpolate(progress, [0, 1], [0.85, 1]);
  const opacity = interpolate(frame, [0, 8], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });
  return {
    text,
    wrapperStyle: {
      transform: `scale(${scale})`,
      opacity,
    } as React.CSSProperties,
  };
};

/** 7. Blur-in — focus pull from blurred to sharp */
const useBlurIn = (text: string, frame: number, fps: number, springMul = 1) => {
  const progress = spring({ fps, frame, config: { damping: 200, stiffness: Math.round(100 * springMul) }, durationInFrames: 24 });
  const blur = interpolate(progress, [0, 1], [16, 0]);
  const opacity = interpolate(progress, [0, 1], [0, 1]);
  const scale = interpolate(progress, [0, 1], [1.08, 1]);
  return {
    text,
    wrapperStyle: {
      filter: `blur(${blur}px)`,
      opacity,
      transform: `scale(${scale})`,
    } as React.CSSProperties,
  };
};

// ============================================================================
// READ LOCK — the staggered modes must finish ARRIVING quickly.
// ----------------------------------------------------------------------------
// Every staggered mode below spreads its entrance over `stagger * (n - 1)`
// frames. Those staggers are per-item constants, so the spread grows without
// bound as text gets longer: rise-mask at 4 frames/word takes 2.4s to finish a
// 19-word line, and wave's 1.5-frame floor takes 3s over a 60-character one.
// For that whole time the line is still assembling — which is the one state a
// viewer cannot read, and the state a scroll-away happens in.
//
// So the SPREAD is capped rather than the per-item duration: the last item
// still animates with its own spring, it just starts sooner. Below the cap
// nothing changes, which is why short copy (the common case — production
// titles run 1-4 words) renders exactly as before.
// ============================================================================
const READ_LOCK_FRAMES = 18;

/** Per-item stagger, shrunk so the whole entrance spread fits the read lock. */
const readLocked = (base: number, itemCount: number) =>
  itemCount > 1 ? Math.min(base, READ_LOCK_FRAMES / (itemCount - 1)) : base;

/** 8. Wave — letters ripple in on a staggered sine wave.
 * Letters are grouped per word so a line can only wrap BETWEEN words,
 * never in the middle of one. */
const useWave = (text: string, frame: number, fps: number, springMul = 1) => {
  const totalChars = text.length;
  const framesPerLetter = readLocked(
    Math.max(1.5, Math.min(3, 24 / Math.max(1, totalChars))),
    totalChars,
  );

  let globalIndex = 0;
  const words = text.split(" ").map((word) => {
    const letters = word.split("").map((ch) => {
      const letterStart = globalIndex * framesPerLetter;
      globalIndex += 1;
      const localFrame = Math.max(0, frame - letterStart);
      const entrance = spring({ fps, frame: localFrame, config: { damping: 18, mass: 0.5, stiffness: Math.round(140 * springMul) }, durationInFrames: 14 });
      const opacity = entrance;
      // Gentle bob after entrance that decays to rest
      const bobDecay = interpolate(frame, [letterStart + 18, letterStart + 48], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      const bob = Math.sin((frame - letterStart) * 0.18) * 4 * entrance * bobDecay;
      const translateY = interpolate(entrance, [0, 1], [24, 0]) + bob;
      return { ch, opacity, translateY };
    });
    globalIndex += 1; // account for the space between words in the stagger
    return letters;
  });

  return { waveWords: words };
};

/** 5. Word-by-word — staggered word appearance */
const useWordByWord = (text: string, frame: number, fps: number, springMul = 1) => {
  const words = text.split(" ");
  const framesPerWord = readLocked(3, words.length);

  const rendered = words.map((word, i) => {
    const wordStart = i * framesPerWord;
    const localFrame = Math.max(0, frame - wordStart);
    const wordProgress = spring({
      fps,
      frame: localFrame,
      config: { damping: 24, stiffness: Math.round(170 * springMul), mass: 0.9 },
      durationInFrames: 12,
    });
    return { word, opacity: wordProgress, translateY: interpolate(wordProgress, [0, 1], [20, 0]) };
  });

  return { words: rendered };
};

/** 9. Rise-mask — each word rises out of an invisible clipping slot (kinetic-
 * typography reveal). Words are whole spans (never letter-split), and the
 * overflow-hidden wrapper hugs a single word, so wrapping stays word-safe. */
const useRiseMask = (text: string, frame: number, fps: number, springMul = 1) => {
  const words = text.split(" ");
  const framesPerWord = readLocked(4, words.length);
  const rendered = words.map((word, i) => {
    const localFrame = Math.max(0, frame - i * framesPerWord);
    const progress = spring({
      fps,
      frame: localFrame,
      config: { damping: 26, stiffness: Math.round(150 * springMul), mass: 0.7 },
      durationInFrames: 16,
    });
    return { word, riseY: interpolate(progress, [0, 1], [110, 0]) };
  });
  return { maskWords: rendered };
};

/** 10. Flip-in — words flip down from 90° like a departures board. */
const useFlipIn = (text: string, frame: number, fps: number, springMul = 1) => {
  const words = text.split(" ");
  const framesPerWord = readLocked(3.5, words.length);
  const rendered = words.map((word, i) => {
    const localFrame = Math.max(0, frame - Math.round(i * framesPerWord));
    const progress = spring({
      fps,
      frame: localFrame,
      config: { damping: 15, stiffness: Math.round(130 * springMul), mass: 0.6 },
      durationInFrames: 18,
    });
    return {
      word,
      rotateX: interpolate(progress, [0, 1], [88, 0]),
      opacity: interpolate(progress, [0, 0.35, 1], [0, 0.85, 1]),
    };
  });
  return { flipWords: rendered };
};

/** 11. Clip-wipe — a highlighter bar sweeps each word's slot, the word slides
 * in behind it. Words are whole spans inside their own overflow-hidden slots
 * (Pain Point 6: wrapping only ever happens BETWEEN slots). */
const useClipWipe = (text: string, frame: number, fps: number, springMul = 1) => {
  const words = text.split(" ");
  const framesPerWord = readLocked(3.5, words.length);
  const rendered = words.map((word, i) => {
    const localFrame = Math.max(0, frame - Math.round(i * framesPerWord));
    const progress = spring({
      fps,
      frame: localFrame,
      config: { damping: 30, stiffness: Math.round(160 * springMul), mass: 0.8 },
      durationInFrames: 14,
    });
    return {
      word,
      slideX: interpolate(progress, [0, 1], [-104, 0]),
      // The bar leads the word's edge across the slot, then exits right.
      barX: interpolate(progress, [0, 1], [-14, 104]),
      barOpacity: interpolate(progress, [0.7, 1], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      }),
    };
  });
  return { wipeWords: rendered };
};

/** 12. Tracking-in — cinematic title settle: letter-spacing tightens from wide
 * while the block fades in and scales down to rest. Single unbroken text
 * block, so word wrapping behaves exactly like the static case. */
const useTrackingIn = (
  text: string,
  frame: number,
  fps: number,
  springMul: number,
  baseLetterSpacingPx: number,
) => {
  const progress = spring({
    fps,
    frame,
    config: { damping: 200, stiffness: Math.round(60 * springMul), mass: 1 },
    durationInFrames: 30,
  });
  const extraTracking = interpolate(progress, [0, 1], [14, 0]);
  const opacity = interpolate(progress, [0, 0.55], [0, 1], {
    extrapolateRight: "clamp",
  });
  const scale = interpolate(progress, [0, 1], [1.06, 1]);
  return {
    text,
    wrapperStyle: {
      letterSpacing: `${baseLetterSpacingPx + extraTracking}px`,
      opacity,
      transform: `scale(${scale})`,
    } as React.CSSProperties,
  };
};

/**
 * AnimatedText — Drop-in replacement for GlitchText that supports
 * 6 different text animation modes, all frame-driven and render-safe.
 *
 * Uses deterministic math (seededChar) instead of Math.random() to
 * ensure consistent output across Remotion's concurrent renderers.
 */
export const AnimatedText: React.FC<AnimatedTextProps> = ({
  text,
  glowColor = "#00f0ff",
  fontFamilyName = "Share Tech Mono",
  overlayType = "grid-hud",
  animationMode = "glitch-decode",
  fontSize,
  fontScale = 1,
  textCase = "upper",
  align = "center",
  treatment = "solid",
  springMul = 1,
  finish = "neon",
  landingPop = false,
  emphasisSweep = false,
  sweepFrame,
  statHitFrame,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const isRetro = overlayType === "vhs-glitch";
  const isClean = overlayType === "clean";
  const metrics = FONT_METRICS[fontFamilyName] ?? FONT_METRICS.Inter;

  // Auto-fit: shrink the font just enough that the LONGEST single word always
  // fits on one line (~90% of a 1080px frame), so words are never split across
  // lines. Floor of 28px keeps text mobile-readable per short-form guidelines.
  // The look's fontScale is applied BEFORE the word-fit cap, so a scaled-up
  // video still never breaks a word. (Computed before the animation switch —
  // tracking-in needs the resolved size for its em-based letter-spacing.)
  const requestedSize = Math.round((fontSize ?? (isRetro ? 36 : 40)) * fontScale);
  const longestWordLen = Math.max(1, ...text.split(/\s+/).map((w) => w.length));
  const maxSizeForWord = Math.floor(920 / (longestWordLen * 0.68));
  const effectiveFontSize = Math.max(28, Math.min(requestedSize, maxSizeForWord));

  // Em-based tracking: display sizes get the title track, smaller text the
  // body track; uppercase serif caps get a touch of extra air (never the wide
  // mono/geometric tracking — that reads as neon, not editorial).
  const isDisplaySize = effectiveFontSize >= 42;
  let trackEm = isDisplaySize ? metrics.trackTitleEm : metrics.trackBodyEm;
  if (
    (fontFamilyName === "Playfair Display" || fontFamilyName === "Fraunces") &&
    textCase !== "as-is"
  )
    trackEm += 0.02;
  const baseLetterSpacing = Math.round(trackEm * effectiveFontSize * 100) / 100;

  // Decode duration in frames
  const decodeDuration = 20;

  // Typewriter types at constant speed, scaled to text length
  const typewriterDuration = Math.min(60, Math.max(18, Math.round(text.length * 1.4)));

  // Select animation
  const animResult = useMemo(() => {
    switch (animationMode) {
      case "typewriter":
        return { ...useTypewriter(text, frame, typewriterDuration), mode: "inline" as const };
      case "glitch-decode":
        return { ...useGlitchDecode(text, frame, decodeDuration), mode: "inline" as const };
      case "fade-up":
        return { ...useFadeUp(text, frame, fps, springMul), mode: "inline" as const };
      case "slide-in":
        return { ...useSlideIn(text, frame, fps, springMul), mode: "inline" as const };
      case "word-by-word":
        return { ...useWordByWord(text, frame, fps, springMul), mode: "words" as const };
      case "scale-pop":
        return { ...useScalePop(text, frame, fps, springMul), mode: "inline" as const };
      case "blur-in":
        return { ...useBlurIn(text, frame, fps, springMul), mode: "inline" as const };
      case "wave":
        return { ...useWave(text, frame, fps, springMul), mode: "letters" as const };
      case "rise-mask":
        return { ...useRiseMask(text, frame, fps, springMul), mode: "mask" as const };
      case "flip-in":
        return { ...useFlipIn(text, frame, fps, springMul), mode: "flip" as const };
      case "clip-wipe":
        return { ...useClipWipe(text, frame, fps, springMul), mode: "wipe" as const };
      case "tracking-in":
        return {
          ...useTrackingIn(text, frame, fps, springMul, baseLetterSpacing),
          mode: "inline" as const,
        };
      case "none":
      default:
        return { text, wrapperStyle: {} as React.CSSProperties, mode: "inline" as const };
    }
  }, [animationMode, text, frame, fps, springMul, baseLetterSpacing, typewriterDuration]);

  // Keyword emphasis (accent-colored key words). Only meaningful where words
  // render as their own spans or plain inline flow; string-manipulating modes
  // (typewriter / glitch-decode) and non-solid treatments (outline strokes,
  // gradient/boxed plates — their own colors would fight the accent) skip it.
  const emphasisEnabled =
    treatment === "solid" &&
    animationMode !== "typewriter" &&
    animationMode !== "glitch-decode";
  const emphasisIndices = useMemo(
    () => (emphasisEnabled ? pickEmphasisIndices(text.split(" ")) : new Set<number>()),
    [text, emphasisEnabled],
  );

  // --- Micro-detail / stat-hit timing (all default-off, deterministic) ------
  // Emphasized NUMERIC tokens are the stat-hit targets (same digit test as
  // pickEmphasisIndices, so a hit can only land on an already-accented word).
  const statIndices = useMemo(() => {
    const out = new Set<number>();
    if (statHitFrame === undefined) return out;
    text.split(" ").forEach((w, i) => {
      if (emphasisIndices.has(i) && /[\d%$#]/.test(w)) out.add(i);
    });
    return out;
  }, [text, emphasisIndices, statHitFrame]);
  const statT = statHitFrame === undefined ? -1 : frame - statHitFrame;
  // 12-frame pulse: up in 5, settle over 7 (rides ON TOP of the 1.05 emphasis
  // scale — transform-only, zero reflow).
  const statPulse =
    statT >= 0 && statT <= 12
      ? 1 + 0.07 * (statT < 5 ? statT / 5 : 1 - (statT - 5) / 7)
      : 1;
  // The accent underline draws over 8 frames and then stays.
  const statBarW =
    statHitFrame === undefined
      ? 0
      : interpolate(frame, [statHitFrame, statHitFrame + 8], [0, 100], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });

  // One light sweep across emphasis words (10 frames at sweepFrame).
  const sweepT =
    emphasisSweep && sweepFrame !== undefined ? (frame - sweepFrame) / 10 : -1;
  const sweepActive = sweepT >= 0 && sweepT <= 1;
  const sweepOverlay = sweepActive ? (
    <span
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        background: `linear-gradient(105deg, transparent 35%, rgba(255,255,255,0.38) 50%, transparent 65%)`,
        backgroundSize: "300% 100%",
        backgroundPosition: `${(sweepT * 100).toFixed(1)}% 50%`,
        mixBlendMode: "screen",
      }}
    />
  ) : null;

  // Landing-pop: drop-shadow swell on the whole plate as the type settles.
  // Filter-only (drop-shadow follows the plate silhouette) — mergeStyles
  // composes it with blur-in / halo filters instead of clobbering them.
  const popK = landingPop
    ? interpolate(frame, [12, 20, 32], [0, 1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;
  const landingStyle: React.CSSProperties =
    popK > 0.01
      ? {
          filter: `drop-shadow(0 ${Math.round(10 * popK)}px ${Math.round(14 * popK)}px rgba(0,0,0,${(0.55 * popK).toFixed(2)}))`,
        }
      : {};

  // Base style shared by all modes — weight/tracking/line-height come from
  // FONT_METRICS so every family renders its REAL loaded weights (no faux bold).
  const baseStyle: React.CSSProperties = {
    fontFamily: getFontFamily(fontFamilyName),
    fontSize: effectiveFontSize,
    color: "#ffffff",
    letterSpacing: `${trackEm}em`,
    lineHeight: metrics.lineHeight,
    textAlign: align,
    textTransform: textCase === "as-is" ? "none" : "uppercase",
    fontWeight: isDisplaySize ? metrics.displayWeight : metrics.bodyWeight,
    padding: "12px 24px",
    maxWidth: "90%",
    overflowWrap: "normal",
    wordBreak: "keep-all",
  };

  // Plate/glow dressing follows the video's finish tokens so text plates match
  // every other panel. Retro (vhs-glitch) keeps its signature brutalist frame;
  // everything else: neon = glow + accent side bars (historical default),
  // glass/soft = quiet panels, print = flat editorial plate, no glow anywhere.
  const finishTokens = FINISH_TOKENS[finish] ?? FINISH_TOKENS.neon;
  const decorationStyle: React.CSSProperties = isRetro
    ? {
        backgroundColor: "rgba(0, 0, 0, 0.8)",
        border: "3px solid #ffffff",
        textShadow: `3px 0 0 ${glowColor}, -3px 0 0 #ff007f`,
        boxShadow: "5px 5px 0px rgba(0,0,0,1)",
      }
    : finish === "neon" && !isClean
    ? {
        textShadow: finishTokens.textGlow(glowColor),
        backgroundColor: "rgba(0, 0, 0, 0.55)",
        borderLeft: `${finishTokens.accentBarWidth}px solid ${glowColor}`,
        borderRight: `${finishTokens.accentBarWidth}px solid ${glowColor}`,
        borderRadius: `${finishTokens.radiusChip}px`,
        backdropFilter: "blur(6px)",
        boxShadow: `0 0 20px ${withAlpha(glowColor, 0.08)}`,
      }
    : {
        // Reaching here with finish "neon" means the overlay is "clean" —
        // clean plates never carried a color glow, so suppress it.
        textShadow: finish === "neon" ? "none" : finishTokens.textGlow(glowColor),
        backgroundColor:
          finish === "print" ? "rgba(10, 12, 16, 0.72)" : "rgba(0, 0, 0, 0.55)",
        borderRadius: `${finishTokens.radiusChip}px`,
        border:
          finish === "print" ? "none" : "1px solid rgba(255, 255, 255, 0.12)",
        backdropFilter: finish === "print" ? undefined : "blur(8px)",
        boxShadow: finishTokens.panelShadow,
      };

  // Title treatments from the Look System. gradient-fill relies on
  // background-clip:text, which misbehaves when descendant spans carry their
  // own transforms — so it only applies to single-block (inline) modes and
  // silently degrades to solid elsewhere. -webkit-text-stroke inherits, so
  // outline works for every mode.
  const treatmentStyle: React.CSSProperties =
    treatment === "outline"
      ? {
          color: "transparent",
          WebkitTextStroke: "2px #ffffff",
          textShadow: `0 0 18px ${glowColor}88`,
          // The stroke is WHITE and the glow shares the accent's hue, so over
          // bright footage this treatment had nothing separating it from the
          // backdrop. text-shadow cannot help once `color` is transparent —
          // drop-shadow follows the stroked glyph outline instead.
          filter: haloFilter(effectiveFontSize, 0.9),
        }
      : treatment === "gradient-fill" && animResult.mode === "inline"
      ? {
          backgroundImage: `linear-gradient(135deg, #ffffff 20%, ${glowColor})`,
          WebkitBackgroundClip: "text",
          backgroundClip: "text",
          color: "transparent",
          textShadow: "none",
          // background-clip:text clips the DECORATION PLATE to the glyph shapes
          // too, so the panel this text is supposed to sit on is never painted —
          // on ~25% of seeds the title was floating on bare footage. Restoring a
          // plate would fight the treatment's whole point, so it gets a halo.
          filter: haloFilter(effectiveFontSize),
        }
      : treatment === "boxed"
      ? {
          backgroundColor: glowColor,
          // Luminance-aware ink: dark accents (cobalt, teal-900 class colors)
          // used to get near-black text at ~3:1 — unreadable.
          color: inkOn(glowColor),
          textShadow: "none",
          borderLeft: "none",
          borderRight: "none",
          borderRadius: `${finishTokens.radiusChip}px`,
          boxShadow: "0 10px 34px rgba(0,0,0,0.45)",
        }
      : {};

  const combinedStyle: React.CSSProperties = {
    ...baseStyle,
    ...decorationStyle,
    ...treatmentStyle,
  };

  /**
   * Spread that COMPOSES `filter` instead of letting the later object win.
   * blur-in returns `filter: blur(Npx)` in its wrapperStyle, and the treatment
   * halo is also a filter — a plain spread silently drops one of them, which is
   * exactly the invisible legibility regression this work exists to stop.
   */
  const mergeStyles = (
    a: React.CSSProperties,
    b: React.CSSProperties,
  ): React.CSSProperties => {
    const merged = { ...a, ...b };
    if (a.filter && b.filter) merged.filter = `${a.filter} ${b.filter}`;
    return merged;
  };

  // The plate style every render branch actually uses — combinedStyle plus the
  // (usually empty) landing-pop shadow, filter-composed.
  const platedStyle = popK > 0.01 ? mergeStyles(combinedStyle, landingStyle) : combinedStyle;

  const flexJustify = align === "left" ? "flex-start" : "center";

  // Shared dressing for one emphasis span: color/glow, the stat-hit pulse
  // scale, sweep positioning context. `extraTransform` is the mode's own
  // per-word transform so everything stays a single transform value.
  const emphasisSpanStyle = (
    i: number,
    extraTransform: string,
  ): React.CSSProperties => {
    const emph = emphasisIndices.has(i);
    if (!emph) return {};
    const pulse = statIndices.has(i) ? statPulse : 1;
    return {
      ...emphasisColorStyle(glowColor),
      transform: `${extraTransform} scale(${(1.05 * pulse).toFixed(3)})`.trim(),
      position: "relative",
    };
  };

  // Stat-hit underline: draws under a numeric emphasis token and stays.
  const statUnderline = (i: number) =>
    statIndices.has(i) && statBarW > 0 ? (
      <span
        style={{
          position: "absolute",
          left: 0,
          bottom: -3,
          height: 3,
          width: `${statBarW.toFixed(1)}%`,
          background: glowColor,
          borderRadius: 2,
          boxShadow: `0 0 10px ${withAlpha(glowColor, 0.5)}`,
          pointerEvents: "none",
        }}
      />
    ) : null;

  // Word-by-word mode renders individual spans
  if (animResult.mode === "words" && "words" in animResult) {
    return (
      <div style={{ ...platedStyle, display: "flex", flexWrap: "wrap", justifyContent: flexJustify, gap: "8px" }}>
        {(animResult as any).words.map(
          (w: { word: string; opacity: number; translateY: number }, i: number) => {
            const emph = emphasisIndices.has(i);
            return (
              <span
                key={i}
                style={{
                  opacity: w.opacity,
                  transform: `translateY(${w.translateY}px)`,
                  display: "inline-block",
                  whiteSpace: "nowrap",
                  ...emphasisSpanStyle(i, `translateY(${w.translateY}px)`),
                }}
              >
                {w.word}
                {emph ? sweepOverlay : null}
                {statUnderline(i)}
              </span>
            );
          }
        )}
      </div>
    );
  }

  // Rise-mask: each word slides up out of its own overflow-hidden slot.
  // Wrapping still only happens BETWEEN slots (whole words) — Pain Point 6.
  if (animResult.mode === "mask" && "maskWords" in animResult) {
    return (
      <div style={{ ...platedStyle, display: "flex", flexWrap: "wrap", justifyContent: flexJustify, gap: "0 10px" }}>
        {(animResult as any).maskWords.map(
          (w: { word: string; riseY: number }, i: number) => {
            const emph = emphasisIndices.has(i);
            return (
              <span key={i} style={{ display: "inline-flex", overflow: "hidden", whiteSpace: "nowrap", padding: "2px 0" }}>
                <span
                  style={{
                    display: "inline-block",
                    whiteSpace: "nowrap",
                    transform: `translateY(${w.riseY}%)`,
                    ...(emph ? emphasisColorStyle(glowColor) : {}),
                  }}
                >
                  {w.word}
                </span>
              </span>
            );
          }
        )}
      </div>
    );
  }

  // Flip-in: words rotate down from ~90° like a departures board.
  if (animResult.mode === "flip" && "flipWords" in animResult) {
    return (
      <div style={{ ...platedStyle, display: "flex", flexWrap: "wrap", justifyContent: flexJustify, gap: "8px", perspective: "600px" }}>
        {(animResult as any).flipWords.map(
          (w: { word: string; rotateX: number; opacity: number }, i: number) => {
            const emph = emphasisIndices.has(i);
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  whiteSpace: "nowrap",
                  opacity: w.opacity,
                  transform: `rotateX(${w.rotateX}deg)${emph ? " scale(1.05)" : ""}`,
                  transformOrigin: "50% 100%",
                  backfaceVisibility: "hidden",
                  ...(emph ? emphasisColorStyle(glowColor) : {}),
                }}
              >
                {w.word}
              </span>
            );
          }
        )}
      </div>
    );
  }

  // Clip-wipe: a highlighter bar sweeps each word's overflow-hidden slot and
  // the word slides in behind it. Slots are unbreakable (Pain Point 6).
  if (animResult.mode === "wipe" && "wipeWords" in animResult) {
    return (
      <div style={{ ...platedStyle, display: "flex", flexWrap: "wrap", justifyContent: flexJustify, gap: "2px 10px" }}>
        {(animResult as any).wipeWords.map(
          (
            w: { word: string; slideX: number; barX: number; barOpacity: number },
            i: number,
          ) => {
            const emph = emphasisIndices.has(i);
            return (
              <span
                key={i}
                style={{
                  display: "inline-flex",
                  overflow: "hidden",
                  whiteSpace: "nowrap",
                  position: "relative",
                  padding: "2px 0",
                }}
              >
                <span
                  style={{
                    display: "inline-block",
                    whiteSpace: "nowrap",
                    transform: `translateX(${w.slideX}%)`,
                    ...(emph ? emphasisColorStyle(glowColor) : {}),
                  }}
                >
                  {w.word}
                </span>
                {w.barOpacity > 0.01 && (
                  <span
                    style={{
                      position: "absolute",
                      top: "8%",
                      bottom: "8%",
                      left: `${w.barX}%`,
                      width: "16%",
                      minWidth: "6px",
                      background: glowColor,
                      borderRadius: "2px",
                      opacity: w.barOpacity,
                      boxShadow: `0 0 12px ${glowColor}88`,
                    }}
                  />
                )}
              </span>
            );
          }
        )}
      </div>
    );
  }

  // Wave mode renders per-letter spans grouped inside unbreakable word blocks
  if (animResult.mode === "letters" && "waveWords" in animResult) {
    return (
      <div style={{ ...platedStyle, display: "flex", flexWrap: "wrap", justifyContent: flexJustify, columnGap: "0.35em" }}>
        {(animResult as any).waveWords.map(
          (letters: { ch: string; opacity: number; translateY: number }[], wi: number) => (
            <span
              key={wi}
              style={{
                display: "inline-flex",
                whiteSpace: "nowrap",
                ...(emphasisIndices.has(wi) ? emphasisColorStyle(glowColor) : {}),
              }}
            >
              {letters.map((l, i) => (
                <span
                  key={i}
                  style={{
                    opacity: l.opacity,
                    transform: `translateY(${l.translateY}px)`,
                    display: "inline-block",
                  }}
                >
                  {l.ch}
                </span>
              ))}
            </span>
          )
        )}
      </div>
    );
  }

  // All other modes render a single text string with optional wrapper transform
  const wrapperStyle = "wrapperStyle" in animResult ? animResult.wrapperStyle : {};
  const displayedText = "text" in animResult ? (animResult as any).text : text;

  // Inline modes with emphasis: keep natural inline flow (spaces between
  // spans, so wrapping stays word-safe) and accent just the key words. The
  // whole-block entrance still comes from wrapperStyle on the parent.
  // gradient-fill never reaches here with emphasis (emphasis is solid-only).
  if (emphasisIndices.size > 0 && displayedText === text) {
    return (
      <div style={mergeStyles(platedStyle, wrapperStyle)}>
        {text.split(" ").map((word, i) => (
          <React.Fragment key={i}>
            {i > 0 ? " " : null}
            <span
              style={{
                whiteSpace: "nowrap",
                display: "inline-block",
                ...emphasisSpanStyle(i, ""),
              }}
            >
              {word}
              {emphasisIndices.has(i) ? sweepOverlay : null}
              {statUnderline(i)}
            </span>
          </React.Fragment>
        ))}
      </div>
    );
  }

  return (
    <div style={mergeStyles(platedStyle, wrapperStyle)}>
      {displayedText}
    </div>
  );
};

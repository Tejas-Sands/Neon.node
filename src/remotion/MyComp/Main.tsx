import React from "react";
import {
  AbsoluteFill,
  Series,
  useCurrentFrame,
  interpolate,
  Audio,
  OffthreadVideo,
  spring,
  useVideoConfig,
  staticFile,
  Easing,
} from "remotion";
import { z } from "zod";
import { getProject } from "@theatre/core";
import { CompositionProps } from "../../../types/constants";
import { AnimatedText, getFontFamily, FONT_METRICS } from "./AnimatedText";
import { HudOverlay } from "./HudOverlay";
import { SceneTransition } from "./SceneTransition";
import { SceneImpactFrame } from "./SceneImpactFrame";
import { LowerThird } from "./LowerThird";
import { ShapeAccents } from "./ShapeAccents";
import {
  deriveLook,
  derivePalette,
  deriveFinish,
  gradeFilter,
  makeRng,
  withAlpha,
  inkOn,
  shade,
  FINISH_TOKENS,
  type LookConfig,
  type Palette,
  type Finish,
} from "./looks";
import { springCfg } from "./motion";
import { deriveCutPlan, WHOOSH_CUTS } from "./transitions";
import { derivePolish } from "./polish";
import { PolishStack, CutCover } from "./PolishLayers";
import {
  BarChart,
  DonutChart,
  LineChart,
  StarRating,
  GlassCard,
  ParticleBurst,
  AnimatedCursor,
  ClickRipple,
  LoadingSpinner,
  TypingField,
  AnimatedCheck,
  DrawnUnderline,
  type CursorWaypoint,
} from "./VideoFX";
import theatreState from "./theatre-state.json";

const MUSIC_MAP: Record<string, string> = {
  "ambient-tech": "ambient-tech.mp3",
  // main.py downloads the selected track to public/<track-name>.mp3 right
  // before the render, so each filename here MUST equal the track name.
  // (*.mp3 is gitignored — nothing else guarantees these files exist in CI;
  // calm-piano.mp3 in particular only exists after scenery-pipeline runs.)
  "lofi-chill": "lofi-chill.mp3",
  "cosmic-synth": "cosmic-synth.mp3",
  "none": "",
};

const theatreProject = getProject("ProductDemo", { state: theatreState });
const theatreSheet = theatreProject.sheet("Scene");
const cameraObj = theatreSheet.object("Camera", {
  scale: 1.0,
  panX: 0.0,
  panY: 0.0,
  rotation: 0.0,
});

interface ThemeProps {
  primaryColor: string;
  secondaryColor: string;
  overlayType: "grid-hud" | "particles" | "clean" | "vhs-glitch" | "fantasy-sparks" | "aurora";
  fontFamilyName: "Share Tech Mono" | "Orbitron" | "Inter" | "Playfair Display" | "Courier New";
  musicTrack?: "ambient-tech" | "lofi-chill" | "cosmic-synth" | "none";
  cameraMotion?: "ken-burns" | "pan-horizontal" | "zoom-slow" | "static" | "dynamic-zoom-rotate" | "pan-tilt" | "pulse-zoom" | "glitch-shift" | "orbit-drift" | "vertigo";
  subtitlePosition?: "top" | "center" | "bottom";
  overlayOpacity?: number;
  transitionStyle?: "crossfade" | "slide-left" | "zoom-through" | "glitch-cut" | "wipe-down" | "iris-open" | "blur-dissolve" | "scale-rotate" | "push-up" | "spin-blur" | "none";
  gradientOverlay?: "none" | "top-to-bottom" | "radial-center" | "diagonal";
  /** Per-video randomness seed (from backend session_id) driving all per-scene variety */
  seed?: number;
}

const defaultTheme: ThemeProps = {
  primaryColor: "#00f0ff",
  secondaryColor: "#ff007f",
  overlayType: "grid-hud",
  fontFamilyName: "Share Tech Mono",
  musicTrack: "none",
  cameraMotion: "dynamic-zoom-rotate",
  subtitlePosition: "bottom",
  overlayOpacity: 1,
  transitionStyle: "crossfade",
  gradientOverlay: "none",
};

// Per-video pool of two COMPATIBLE text animations. One video mixing eight
// unrelated text behaviors has no motion identity; the seed picks a pool and
// scenes alternate within it (an explicit per-scene textAnimation still wins).
// Typewriter / glitch-decode / wave are deliberately NOT whole-video pools —
// as a video-wide identity they read gimmicky; a scene can still request
// them via its explicit textAnimation, which always wins over the pool.
const TEXT_ANIM_POOLS: string[][] = [
  ["fade-up", "word-by-word"],
  ["slide-in", "fade-up"],
  ["blur-in", "scale-pop"],
  ["blur-in", "rise-mask"],
  ["fade-up", "blur-in"],
  ["word-by-word", "blur-in"],
  // Render-side-only modes (not in the props enum — see AnimatedText.tsx):
  // kinetic-typography reveals give whole videos a distinct motion identity.
  ["rise-mask", "fade-up"],
  ["flip-in", "rise-mask"],
  // clip-wipe = highlighter-sweep word reveal; tracking-in = cinematic
  // letter-spacing settle. Both render-side only, like rise-mask/flip-in.
  ["clip-wipe", "fade-up"],
  ["tracking-in", "blur-in"],
  ["clip-wipe", "rise-mask"],
];

// 00..FF hex alpha from a 0..1 value (theme colors are 6-digit hex).
const alphaHex = (t: number) =>
  Math.round(Math.max(0, Math.min(1, t)) * 255)
    .toString(16)
    .padStart(2, "0");

// ============================================================================
// HookPunch — a pattern-interrupt flash fired on the FIRST scene only.
// A quick color-burst + expanding shock-ring in the opening ~20 frames to
// "stop the scroll" on social feeds. Purely a visual attention grabber.
// ============================================================================
const HookPunch: React.FC<{ primaryColor: string; secondaryColor: string; seed?: number }> = ({
  primaryColor,
  secondaryColor,
  seed = 0,
}) => {
  const frame = useCurrentFrame();
  // Runs a touch longer than the flash so the outward particle burst can play
  // out; the flash/ring interpolations clamp to 0 well before this cutoff.
  if (frame > 42) return null;

  const flash = interpolate(frame, [0, 2, 12], [0.85, 0.45, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const ringScale = interpolate(frame, [0, 20], [0.15, 2.4], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const ringOpacity = interpolate(frame, [0, 3, 20], [0, 0.55, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 60, overflow: "hidden" }}>
      {/* Outward particle burst — seeded so it differs per video */}
      <ParticleBurst
        originX={50}
        originY={45}
        count={22}
        startFrame={0}
        durationInFrames={40}
        seed={(seed >>> 0) + 101}
        colors={[primaryColor, secondaryColor, "#ffffff"]}
        maxRadius={55}
      />
      {flash > 0.01 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(circle at 50% 45%, ${primaryColor}, ${secondaryColor}55, transparent 65%)`,
            opacity: flash,
            mixBlendMode: "screen",
          }}
        />
      )}
      <div
        style={{
          position: "absolute",
          top: "45%",
          left: "50%",
          width: "60vh",
          height: "60vh",
          borderRadius: "50%",
          border: `3px solid ${primaryColor}`,
          boxShadow: `0 0 40px ${primaryColor}80`,
          transform: `translate(-50%, -50%) scale(${ringScale})`,
          opacity: ringOpacity,
        }}
      />
    </div>
  );
};

// ============================================================================
// Scene player component adapted to style parameters
// ============================================================================
const DynamicScene: React.FC<{
  imageUrl: string;
  videoUrl?: string;
  text: string;
  title?: string;
  subtitle?: string;
  secondaryText?: string;
  type?: string;
  durationInFrames: number;
  theme: ThemeProps;
  look: LookConfig;
  palette: Palette;
  finish: Finish;
  textAnimation?: string;
  // Scene context for impact frame
  sceneIndex: number;
  totalScenes: number;
  // Scene-type-specific fields
  leftLabel?: string;
  rightLabel?: string;
  listItems?: string[];
  countFrom?: number;
  countTo?: number;
  countSuffix?: string;
  ctaText?: string;
  // Data-driven scene fields (charts / ratings)
  chartData?: { label: string; value: number }[];
  ratingValue?: number;
  ratingMax?: number;
}> = ({
  imageUrl,
  videoUrl,
  text,
  title,
  subtitle,
  secondaryText,
  type,
  durationInFrames,
  theme,
  look,
  palette,
  finish,
  textAnimation,
  sceneIndex,
  totalScenes,
  leftLabel,
  rightLabel,
  listItems,
  countFrom,
  countTo,
  countSuffix,
  ctaText,
  chartData,
  ratingValue,
  ratingMax,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Per-video seed folded into every pseudo-random choice so no two videos
  // share the same camera / text-animation sequence (render-safe, deterministic).
  const seed = (theme.seed ?? 0) >>> 0;
  // Camera motion is drawn from the look's personality-flavored pool so a
  // "calm" video drifts slowly while a "snappy" one cuts with energy — but the
  // exact pick still varies per scene (seed + sceneIndex) so scenes differ.
  const motionOptions = look.cameraPool.length ? look.cameraPool : ["ken-burns", "zoom-slow"];
  const hash = ((seed + (text?.length || 0) + (title?.length || 0) + sceneIndex * 17) >>> 0) % motionOptions.length;
  const motionType = motionOptions[hash];

  // Text animation: alternate within the video's seeded 2-mode pool
  const textAnimPool = TEXT_ANIM_POOLS[(seed >>> 5) % TEXT_ANIM_POOLS.length];
  const animMode = (textAnimation ?? textAnimPool[sceneIndex % textAnimPool.length]) as any;

  // Motion-personality stiffness multiplier (calm 0.8 .. snappy 1.3) — applied
  // to every scene spring so a calm video actually settles more softly.
  const sMul = look.springMul;

  // --- Look-driven TEXT SYSTEM (layout / type scale / title dressing) -------
  // fontScale multiplies every AnimatedText size (word-fit cap still applies
  // inside AnimatedText, so scaled-up videos never split words); fs() is for
  // raw text divs that don't go through AnimatedText.
  const fscale = look.fontScale ?? 1;
  const fs = (px: number) => Math.round(px * fscale);
  const textLayout = look.textLayout ?? "center-stack";
  const isLeftLayout = textLayout === "left-rail";
  const titleTreatment = look.titleTreatment ?? "solid";
  const textAlignMode: "center" | "left" = isLeftLayout ? "left" : "center";
  // Shared column style for the hero/split/cta text stacks. left-rail keeps a
  // wide right margin so the block reads as an editorial column.
  const stackStyle: React.CSSProperties = isLeftLayout
    ? { alignItems: "flex-start", textAlign: "left", padding: "0 14% 0 7%" }
    : { alignItems: "center", textAlign: "center", padding: "0 8%" };
  // Vertical anchor (top %) per layout for the hero stack; split/cta derive
  // their own from these so blocks never collide with subtitles (bottom 24%).
  const heroTop =
    textLayout === "banner-low" ? 52 : textLayout === "top-ticker" ? 10 : look.heroAnchor;

  // Dynamic Camera Motion (Programmatic base)
  let baseScale = 1.0;
  let basePanX = 0;
  let basePanY = 0;
  let baseRotation = 0;

  // Full-scene drifts are LINEAR on purpose: the cut interrupts the move, so
  // constant velocity reads as documentary camera drift. An eased drift
  // visibly decelerates INTO each cut — the image "parks" before the edit,
  // which is the actual template-Ken-Burns tell.
  if (motionType === "pan-horizontal") {
    baseScale = 1.12;
    basePanX = interpolate(frame, [0, durationInFrames], [-20, 20], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  } else if (motionType === "zoom-slow") {
    baseScale = interpolate(frame, [0, durationInFrames], [1.0, 1.18], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  } else if (motionType === "ken-burns") {
    baseScale = interpolate(frame, [0, durationInFrames], [1.0, 1.15], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    basePanX = interpolate(frame, [0, durationInFrames], [-15, 15], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    basePanY = interpolate(frame, [0, durationInFrames], [-8, 8], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  } else if (motionType === "dynamic-zoom-rotate") {
    baseScale = interpolate(frame, [0, durationInFrames], [1.0, 1.25], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    baseRotation = interpolate(frame, [0, durationInFrames], [0, 3], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    basePanX = interpolate(frame, [0, durationInFrames], [0, 10], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  } else if (motionType === "pan-tilt") {
    baseScale = 1.15;
    basePanX = interpolate(frame, [0, durationInFrames], [-25, 25], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    basePanY = interpolate(frame, [0, durationInFrames], [-15, 15], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    baseRotation = interpolate(frame, [0, durationInFrames], [-2, 2], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  } else if (motionType === "pulse-zoom") {
    // Breathing amplitude ramps in over 15 frames — starting a pulse at full
    // velocity on frame 0 reads as a stutter, not tension.
    const amp = interpolate(frame, [0, 15], [0, 0.02], { extrapolateRight: "clamp" });
    const pulse = Math.sin(frame / 10) * amp;
    baseScale = interpolate(frame, [0, durationInFrames], [1.05, 1.2], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }) + pulse;
  } else if (motionType === "orbit-drift") {
    // Gentle orbital drift — circular pan + slow zoom + subtle rotation
    baseScale = interpolate(frame, [0, durationInFrames], [1.12, 1.22], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const orbit = frame * 0.02;
    basePanX = Math.cos(orbit) * 18;
    basePanY = Math.sin(orbit) * 12;
    baseRotation = Math.sin(frame * 0.01) * 2;
  } else if (motionType === "vertigo") {
    // Dolly-zoom "vertigo" push — accelerating zoom for a dramatic reveal.
    // Both axes accelerate together (in-quad) so the push feels like one move.
    baseScale = interpolate(frame, [0, durationInFrames], [1.02, 1.35], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.quad),
    });
    basePanY = interpolate(frame, [0, durationInFrames], [6, -6], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.in(Easing.quad) });
  } else if (motionType === "glitch-shift") {
    baseScale = 1.1;
    // Hold each displacement burst 3 frames (a single-frame jump reads as an
    // encoding artifact), with a seeded offset per burst.
    const burst = Math.floor(frame / 12);
    const inBurst = frame % 12 < 3;
    const rng = makeRng(seed + burst * 97);
    basePanX = inBurst ? rng() * 24 - 12 : 0;
    basePanY = inBurst ? rng() * 16 - 8 : 0;
  }

  // Theatre.js override — scrub the sequence synchronously during render so
  // every frame stays a pure function of `frame` (state + effects lag under
  // Remotion's parallel frame rendering), and respect the composition fps.
  theatreSheet.sequence.position = frame / fps;
  const theatreValues = cameraObj.value;

  const scale = theatreValues.scale !== 1.0 ? theatreValues.scale : baseScale;
  const panX = theatreValues.panX !== 0.0 ? theatreValues.panX : basePanX;
  const panY = theatreValues.panY !== 0.0 ? theatreValues.panY : basePanY;
  const rotation = theatreValues.rotation !== 0.0 ? theatreValues.rotation : baseRotation;

  // ---- Shared background + vignette layer (look-driven treatment) ----
  const imgFilter = gradeFilter(look);
  const vignettePx = Math.round(90 + look.vignette * 90); // ~90..180px inner shadow
  const washAngle = look.bgAngle + Math.sin(frame * 0.01) * 20;

  // Stock video hook clip: relative paths come from the backend's public/ dir
  const videoSrc = videoUrl
    ? videoUrl.startsWith("http://") || videoUrl.startsWith("https://") || videoUrl.startsWith("data:")
      ? videoUrl
      : staticFile(videoUrl)
    : undefined;

  // Design tokens for this video's finish (radii / panel fills / glow policy).
  const ft = FINISH_TOKENS[finish] ?? FINISH_TOKENS.neon;

  const BackgroundLayer = (
    <>
      {/* Brand-tinted base field UNDER the photo: when the image is dim, dark
          or absent the frame is still a designed gradient, not dead black. */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(140% 90% at 50% 8%, ${palette.bgStops[0]} 0%, ${palette.ink} 55%, #05060a 100%)`,
        }}
      />
      {/* Dynamic Background visual */}
      <img
        src={imageUrl}
        style={{
          width: "115%",
          height: "115%",
          objectFit: "cover",
          transform: `scale(${scale}) translate(${panX}px, ${panY}px) rotate(${rotation}deg)`,
          filter: imgFilter,
          opacity: look.background === "gradient-wash" ? 0.38 : 1,
        }}
        alt="scenic landscape"
      />

      {/* Stock motion clip over the still (hook scene). The footage carries
          its own motion, so only a gentle fixed zoom is applied — layering the
          full camera move on real video reads as double-motion. */}
      {videoSrc && (
        <OffthreadVideo
          muted
          src={videoSrc}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: "scale(1.06)",
            filter: imgFilter,
            opacity: look.background === "gradient-wash" ? 0.38 : 1,
          }}
        />
      )}

      {/* --- Treatment: DUOTONE color wash (blends photo into brand colors) ---
          Blending against SHADED colors keeps chroma on pastel packs — pure
          near-white secondaries used to gray the whole frame out. */}
      {look.background === "duotone" && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `linear-gradient(${look.bgAngle}deg, ${shade(theme.primaryColor, 0.25)} 0%, ${shade(theme.secondaryColor, 0.35)} 100%)`,
            mixBlendMode: "color",
            opacity: 0.62,
            pointerEvents: "none",
          }}
        />
      )}

      {/* --- Treatment: GRADIENT WASH (designed abstract bg over faded photo) ---
          4-stop diagonal ramp with a clear quiet middle + a soft counter-angled
          radial for depth — the flat 2-color 50/50 wash read as muddy tint. */}
      {look.background === "gradient-wash" && (
        <>
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `linear-gradient(${washAngle}deg, ${palette.bgStops[0]} 0%, transparent 38%, transparent 62%, ${palette.bgStops[2]} 100%)`,
              pointerEvents: "none",
            }}
          />
          <div
            style={{
              position: "absolute",
              inset: 0,
              background: `radial-gradient(90% 60% at 20% 15%, ${withAlpha(palette.primarySoft, 0.1)} 0%, transparent 60%)`,
              pointerEvents: "none",
            }}
          />
        </>
      )}

      {/* --- Treatment: SPOTLIGHT (heavy edge fall-off, bright centre) ---
          Eased multi-stop falloff in brand ink — the 3-stop version banded. */}
      {look.background === "spotlight" && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(ellipse 55% 45% at 50% 42%, transparent 0%, ${withAlpha(palette.ink, 0.2)} 55%, ${withAlpha(palette.ink, 0.55)} 72%, ${withAlpha(palette.ink, 0.8)} 86%, ${withAlpha(palette.ink, 0.94)} 100%)`,
            pointerEvents: "none",
          }}
        />
      )}

      {/* --- Treatment: CINEMA BARS (letterbox for a filmic frame) --- */}
      {look.background === "cinema-bars" && (
        <>
          <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: "9%", background: "#000", pointerEvents: "none", zIndex: 3 }} />
          <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: "9%", background: "#000", pointerEvents: "none", zIndex: 3 }} />
        </>
      )}

      {/* Cinematic Vignette Overlay — depth scaled by look */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          boxShadow: theme.overlayType === "clean"
            ? `inset 0 0 ${vignettePx * 0.7}px rgba(0,0,0,0.65)`
            : `inset 0 0 ${vignettePx}px rgba(0,0,0,0.9)`,
          pointerEvents: "none",
        }}
      />
      {/* Bottom scrim for lower-third/caption readability. Eased 5-stop ramp
          in brand-tinted ink: the old 3-stop black gradient drew a visible
          horizontal band edge at its 70% stop. Peak darkness at the caption
          band (bottom 24%) is >= the old value — readability guardrail. */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: "45%",
          background: `linear-gradient(to bottom, transparent 0%, ${withAlpha(palette.ink, 0.12)} 30%, ${withAlpha(palette.ink, 0.42)} 55%, ${withAlpha(palette.ink, 0.74)} 78%, ${withAlpha(palette.ink, 0.88)} 100%)`,
          pointerEvents: "none",
        }}
      />
    </>
  );

  // ---- Shared layers that every scene gets ----
  const SharedLayers = (
    <>
      <SceneImpactFrame
        primaryColor={theme.primaryColor}
        secondaryColor={theme.secondaryColor}
        durationInFrames={durationInFrames}
        sceneIndex={sceneIndex}
        totalScenes={totalScenes}
        seed={seed}
        showProgressBar={look.showProgressBar}
        showSceneCounter={look.showSceneCounter}
      />
      <ShapeAccents
        primaryColor={theme.primaryColor}
        secondaryColor={theme.secondaryColor}
        durationInFrames={durationInFrames}
        intensity={look.accentDensity === "high" && (type === "hero" || type === "cta") ? "high" : look.accentDensity}
        sceneIndex={sceneIndex}
        videoSeed={seed}
        showRings={look.showRings}
        showBrackets={look.showCornerBrackets}
        showFloating={look.showFloatingShapes}
      />
      {/* Scroll-stopping hook punch on the opening scene only */}
      {sceneIndex === 0 && (
        <HookPunch primaryColor={theme.primaryColor} secondaryColor={theme.secondaryColor} seed={seed} />
      )}
    </>
  );

  // ========================================================================
  // SCENE TYPE RENDERERS (redesigned)
  // ========================================================================

  // --- HERO scene (full-bleed cinematic opener) ---
  if (type === "hero") {
    // Title entrance: scale-up spring. On the OPENING scene the text must be
    // on screen from frame one (Meta's hook guidance — viewers decide in the
    // first second), so the hook title gets zero delay and a snappier spring.
    const entranceDelay = sceneIndex === 0 ? 0 : 8;
    const titleEntrance = spring({
      fps,
      frame: Math.max(0, frame - entranceDelay),
      config: sceneIndex === 0
        ? { damping: 14, stiffness: Math.round(180 * sMul), mass: 0.5 }
        : { damping: 12, stiffness: Math.round(100 * sMul), mass: 0.8 },
      durationInFrames: sceneIndex === 0 ? 12 : 20,
    });
    const titleScale = interpolate(titleEntrance, [0, 1], [sceneIndex === 0 ? 0.85 : 0.7, 1]);
    // Hook text is never fully invisible on scene 0 — readable from frame one
    const titleOpacity = interpolate(titleEntrance, [0, 1], [sceneIndex === 0 ? 0.6 : 0, 1]);
    const titleY = interpolate(titleEntrance, [0, 1], [30, 0]);
    // Post-entrance "living" drift: pro titles never sit dead-still — a slow
    // +1.5% scale over the scene keeps the type alive without fighting the
    // camera. Calm looks stay truly still (motion mood matches).
    const titleDrift =
      look.motion === "calm" ? 1 : 1 + (frame / Math.max(1, durationInFrames)) * 0.015;

    // Accent line under title
    const lineWidth = spring({
      fps,
      frame: Math.max(0, frame - 16),
      config: { damping: 20, stiffness: Math.round(130 * sMul) },
      durationInFrames: 18,
    });
    const lineW = interpolate(lineWidth, [0, 1], [0, 100]);

    // Top-down cascade: title -> line -> body -> subtitle. Body text used to
    // animate from frame 0, appearing BEFORE the title above it.
    const bodyEntrance = spring({
      fps,
      frame: Math.max(0, frame - (sceneIndex === 0 ? 6 : 20)),
      config: { damping: 16, stiffness: Math.round(110 * sMul) },
      durationInFrames: 16,
    });
    const bodyY = interpolate(bodyEntrance, [0, 1], [16, 0]);

    // Subtitle fade-up with delay
    const subEntrance = spring({
      fps,
      frame: Math.max(0, frame - (sceneIndex === 0 ? 12 : 26)),
      config: { damping: 18, stiffness: Math.round(90 * sMul) },
      durationInFrames: 18,
    });
    const subOpacity = interpolate(subEntrance, [0, 1], [0, 1]);
    const subY = interpolate(subEntrance, [0, 1], [20, 0]);

    // Text counter-parallax: the type plane drifts subtly AGAINST the camera
    // pan, separating foreground from background. Calm looks stay planar.
    const parallax =
      look.motion === "calm"
        ? ""
        : ` translate(${(-basePanX * 0.15).toFixed(2)}px, ${(-basePanY * 0.15).toFixed(2)}px)`;

    return (
      <AbsoluteFill>
        {BackgroundLayer}
        {SharedLayers}
        {/* Soft contact shadow behind the text stack — pre-blurred radial
            gradient (no filter:blur), buys separation on the lighter grades. */}
        <div
          style={{
            position: "absolute",
            top: `${heroTop - 6}%`,
            left: "5%",
            right: "5%",
            height: "42%",
            background: `radial-gradient(ellipse 60% 45% at 50% 45%, ${withAlpha(palette.ink, 0.5)} 0%, transparent 70%)`,
            zIndex: 19,
            pointerEvents: "none",
          }}
        />
        <div style={{ position: "absolute", top: `${heroTop}%`, left: 0, right: 0, display: "flex", flexDirection: "column", gap: "16px", zIndex: 20, textTransform: look.titleCase === "upper" ? "uppercase" : "none", transform: parallax || undefined, ...stackStyle }}>
          {title && (
            <div style={{ transform: `translateY(${titleY}px) scale(${titleScale * titleDrift})`, opacity: titleOpacity }}>
              <AnimatedText
                text={title}
                glowColor={theme.secondaryColor}
                fontFamilyName={theme.fontFamilyName}
                overlayType={theme.overlayType}
                // Hook title renders statically — typewriter/decode animations
                // hide the text during the exact frames that decide the scroll
                animationMode={sceneIndex === 0 ? "none" : animMode}
                fontSize={theme.overlayType === "vhs-glitch" ? 54 : 62}
                fontScale={fscale}
                textCase={look.titleCase}
                align={textAlignMode}
                treatment={titleTreatment}
                springMul={sMul}
                finish={finish}
              />
            </div>
          )}
          {/* Accent line */}
          <div
            style={{
              width: `${lineW}%`,
              maxWidth: "200px",
              height: "3px",
              background: `linear-gradient(90deg, transparent, ${theme.primaryColor}, ${theme.secondaryColor}, transparent)`,
              boxShadow: `0 0 12px ${theme.primaryColor}60`,
              borderRadius: "2px",
              ...(isLeftLayout ? { alignSelf: "flex-start", marginLeft: "24px" } : {}),
            }}
          />
          {text && (
            <div style={{ opacity: bodyEntrance, transform: `translateY(${bodyY}px)` }}>
              <AnimatedText text={text} glowColor={theme.primaryColor} fontFamilyName={theme.fontFamilyName} overlayType={theme.overlayType} animationMode={animMode} fontScale={fscale} textCase={look.titleCase} align={textAlignMode} springMul={sMul} finish={finish} />
            </div>
          )}
          {subtitle && (
            <div style={{ opacity: subOpacity, transform: `translateY(${subY}px)` }}>
              <AnimatedText
                text={subtitle}
                glowColor={theme.primaryColor}
                fontFamilyName={theme.fontFamilyName}
                overlayType={theme.overlayType}
                animationMode={animMode}
                fontSize={theme.overlayType === "vhs-glitch" ? 26 : 30}
                fontScale={fscale}
                textCase={look.titleCase}
                align={textAlignMode}
                springMul={sMul}
                finish={finish}
              />
            </div>
          )}
        </div>
      </AbsoluteFill>
    );
  }

  // --- TESTIMONIAL scene (quote with left accent bar) ---
  if (type === "testimonial") {
    const quoteEntrance = spring({
      fps,
      frame: Math.max(0, frame - 10),
      config: { damping: 14, stiffness: Math.round(100 * sMul) },
      durationInFrames: 22,
    });
    const quoteX = interpolate(quoteEntrance, [0, 1], [-40, 0]);
    const quoteOpacity = interpolate(quoteEntrance, [0, 1], [0, 1]);

    return (
      <AbsoluteFill>
        {BackgroundLayer}
        {SharedLayers}
        {/* Use lower-third for the attribution */}
        {subtitle && (
          <LowerThird
            title={subtitle}
            accentColor={theme.primaryColor}
            secondaryColor={theme.secondaryColor}
            durationInFrames={durationInFrames}
            variant="minimal"
            fontFamily={getFontFamily(theme.fontFamilyName)}
            titleWeight={FONT_METRICS[theme.fontFamilyName].displayWeight}
          />
        )}
        {/* bottom 32%: the caption band tops out near 30%, and 28% used to
            clip the quote's last line under the caption box */}
        <div style={{ position: "absolute", bottom: "32%", left: "8%", right: "8%", zIndex: 20, opacity: quoteOpacity, transform: `translateX(${quoteX}px)` }}>
          {title && <div style={{ fontSize: `${fs(28)}px`, color: theme.secondaryColor, fontWeight: FONT_METRICS[theme.fontFamilyName].bodyWeight, fontFamily: getFontFamily(theme.fontFamilyName), marginBottom: "12px", textTransform: "uppercase", letterSpacing: "0.1em" }}>{title}</div>}
          {text && (
            <div style={{
              fontSize: "32px",
              fontStyle: "italic",
              borderLeft: `4px solid ${theme.primaryColor}`,
              paddingLeft: "24px",
              color: "#fff",
              lineHeight: 1.4,
              textShadow: "0 2px 16px rgba(0,0,0,0.8)",
              boxShadow: `inset 4px 0 12px ${theme.primaryColor}20`,
            }}>
              "{text}"
            </div>
          )}
        </div>
      </AbsoluteFill>
    );
  }

  // --- METRIC scene (giant number with glow ring) ---
  if (type === "metric") {
    // Count the hero stat up (eased, lands with weight) — the one element that
    // deserves motion in this scene used to render completely static.
    const numberText = text || "0";
    const numMatch = numberText.match(/^([\d][\d,.]*)(.*)$/);
    const numericValue = numMatch ? parseFloat(numMatch[1].replace(/,/g, "")) : null;
    const numericSuffix = numMatch ? numMatch[2] : "";
    const hasDecimals = numMatch ? /\.\d/.test(numMatch[1]) : false;
    const countProgress = interpolate(frame, [8, 48], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    });

    // Glow ring animation (steady glow — oscillating shadows read as shimmer)
    const ringRotation = frame * 1.2;
    const ringPulse = Math.sin(frame * 0.06) * 0.1 + 1;
    const ringGlow = 16;

    // Label follows the number instead of popping in unanimated at frame 0
    const labelIn = spring({
      fps,
      frame: Math.max(0, frame - 18),
      config: { damping: 18, stiffness: Math.round(100 * sMul) },
      durationInFrames: 16,
    });

    return (
      <AbsoluteFill>
        {BackgroundLayer}
        {SharedLayers}
        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", display: "flex", flexDirection: "column", alignItems: "center", gap: "16px", zIndex: 20 }}>
          {title && (
            <AnimatedText
              text={title}
              glowColor={theme.secondaryColor}
              fontFamilyName={theme.fontFamilyName}
              overlayType={theme.overlayType}
              animationMode={animMode}
              fontSize={theme.overlayType === "vhs-glitch" ? 38 : 42}
              fontScale={fscale}
              textCase={look.titleCase}
              treatment={titleTreatment}
              springMul={sMul}
              finish={finish}
            />
          )}
          {/* Glow ring around number */}
          <div style={{ position: "relative", margin: "20px 0" }}>
            <div
              style={{
                position: "absolute",
                top: "-40px",
                left: "-40px",
                right: "-40px",
                bottom: "-40px",
                borderRadius: "50%",
                border: `2px solid ${theme.primaryColor}25`,
                transform: `rotate(${ringRotation}deg) scale(${ringPulse})`,
              }}
            >
              <div style={{
                position: "absolute", top: 0, left: 0, width: "100%", height: "100%",
                borderRadius: "50%", border: `3px solid transparent`, borderTopColor: `${theme.primaryColor}60`,
                boxShadow: `0 0 ${ringGlow}px ${theme.primaryColor}30`,
              }} />
            </div>
            {numericValue !== null ? (
              <div
                style={{
                  fontSize: `${fs(theme.overlayType === "vhs-glitch" ? 72 : 80)}px`,
                  // Real loaded weight only — 900 was synthesized for every
                  // family except Orbitron and rendered fuzzy.
                  fontWeight: FONT_METRICS[theme.fontFamilyName].displayWeight,
                  fontFamily: getFontFamily(theme.fontFamilyName),
                  color: theme.primaryColor,
                  textShadow: ft.textGlow(theme.primaryColor),
                  fontVariantNumeric: "tabular-nums",
                  textAlign: "center",
                  whiteSpace: "nowrap",
                }}
              >
                {hasDecimals
                  ? (numericValue * countProgress).toFixed(1)
                  : Math.round(numericValue * countProgress).toLocaleString("en-US")}
                {numericSuffix}
              </div>
            ) : (
              <AnimatedText
                text={numberText}
                glowColor={theme.primaryColor}
                fontFamilyName={theme.fontFamilyName}
                overlayType={theme.overlayType}
                animationMode={animMode}
                fontSize={theme.overlayType === "vhs-glitch" ? 72 : 80}
                fontScale={fscale}
              />
            )}
          </div>
          {secondaryText && (
            <div style={{ fontSize: `${fs(28)}px`, color: theme.secondaryColor, fontWeight: FONT_METRICS[theme.fontFamilyName].bodyWeight, fontFamily: getFontFamily(theme.fontFamilyName), textTransform: "uppercase", letterSpacing: "0.1em", textShadow: ft.textGlow(theme.secondaryColor), opacity: labelIn, transform: `translateY(${interpolate(labelIn, [0, 1], [16, 0])}px)` }}>
              {secondaryText}
            </div>
          )}
        </div>
      </AbsoluteFill>
    );
  }

  // --- COUNTDOWN scene ---
  if (type === "countdown") {
    const from = countFrom ?? 100;
    const to = countTo ?? 0;
    const suffix = countSuffix ?? "";
    // Fast start, weighty landing — a constant-speed tick has no drama.
    const currentValue = Math.round(
      interpolate(frame, [0, durationInFrames * 0.8], [from, to], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
        easing: Easing.out(Easing.cubic),
      })
    );
    // One-shot settle pop on landing, then rest — not an endless wobble.
    const landedAt = Math.round(durationInFrames * 0.8);
    const landedSpring = spring({
      fps,
      frame: Math.max(0, frame - landedAt),
      config: { damping: 12, stiffness: 200, mass: 0.6 },
      durationInFrames: 14,
    });
    const pulseScale = frame > landedAt ? 1 + interpolate(landedSpring, [0, 1], [0.1, 0]) : 1;

    const ringProgress = interpolate(frame, [0, durationInFrames * 0.8], [0, 100], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.out(Easing.cubic),
    });

    // Ring geometry: one 280px instrument centering both the dial and the
    // number. (The old markup put a 110px number in an 80px-wide box next to a
    // separately-offset 200px ring — number and ring never actually aligned.)
    const RING = 280;
    const RING_R = 126;
    const RING_C = 2 * Math.PI * RING_R;

    return (
      <AbsoluteFill>
        {BackgroundLayer}
        {SharedLayers}
        <div style={{ position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)", display: "flex", flexDirection: "column", alignItems: "center", gap: "18px", zIndex: 20 }}>
          {title && (
            <AnimatedText text={title} glowColor={theme.secondaryColor} fontFamilyName={theme.fontFamilyName} overlayType={theme.overlayType} animationMode={animMode} fontSize={theme.overlayType === "vhs-glitch" ? 38 : 42} fontScale={fscale} textCase={look.titleCase} treatment={titleTreatment} springMul={sMul} finish={finish} />
          )}
          <div style={{ position: "relative", width: RING, height: RING, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width={RING} height={RING} style={{ position: "absolute", inset: 0 }}>
              {/* Instrument tick marks — static, subtle */}
              <g>
                {Array.from({ length: 60 }, (_, i) => {
                  const a = (i / 60) * Math.PI * 2;
                  const x1 = RING / 2 + Math.cos(a) * (RING_R + 6);
                  const y1 = RING / 2 + Math.sin(a) * (RING_R + 6);
                  const x2 = RING / 2 + Math.cos(a) * (RING_R + 11);
                  const y2 = RING / 2 + Math.sin(a) * (RING_R + 11);
                  return (
                    <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="rgba(255,255,255,0.12)" strokeWidth={i % 5 === 0 ? 2 : 1} />
                  );
                })}
              </g>
              <circle cx={RING / 2} cy={RING / 2} r={RING_R} fill="none" stroke={palette.edge} strokeWidth="3" />
              <circle
                cx={RING / 2}
                cy={RING / 2}
                r={RING_R}
                fill="none"
                stroke={theme.primaryColor}
                strokeWidth="4"
                strokeDasharray={`${(ringProgress / 100) * RING_C} ${RING_C}`}
                strokeLinecap="round"
                transform={`rotate(-90 ${RING / 2} ${RING / 2})`}
                style={{ filter: `drop-shadow(0 0 6px ${withAlpha(theme.primaryColor, 0.38)})` }}
              />
            </svg>
            <div
              style={{
                fontSize: `${fs(88)}px`,
                fontWeight: FONT_METRICS[theme.fontFamilyName].displayWeight,
                fontFamily: getFontFamily(theme.fontFamilyName),
                fontVariantNumeric: "tabular-nums",
                color: theme.primaryColor,
                textShadow: ft.textGlow(theme.primaryColor),
                transform: `scale(${pulseScale})`,
                textAlign: "center",
                whiteSpace: "nowrap",
                maxWidth: `${RING - 40}px`,
                overflow: "hidden",
              }}
            >
              {currentValue}{suffix}
            </div>
          </div>
          {text && (
            <AnimatedText text={text} glowColor={theme.primaryColor} fontFamilyName={theme.fontFamilyName} overlayType={theme.overlayType} animationMode={animMode} fontSize={28} fontScale={fscale} textCase={look.titleCase} springMul={sMul} finish={finish} />
          )}
        </div>
      </AbsoluteFill>
    );
  }

  // --- COMPARISON scene ---
  if (type === "comparison") {
    // The story is always "AFTER wins" — the design says so: the before panel
    // sits back (dimmer, 0.97 scale, hairline border), the after panel lands
    // 8 frames later with a pop spring, accent border and shadow.
    const slideInLeft = spring({ fps, frame, config: { damping: 17, stiffness: Math.round(130 * sMul), mass: 0.7 }, durationInFrames: 18 });
    const slideInRight = spring({ fps, frame: Math.max(0, frame - 8), config: springCfg("pop", sMul), durationInFrames: 18 });
    const leftX = interpolate(slideInLeft, [0, 1], [-60, 0]);
    const rightX = interpolate(slideInRight, [0, 1], [60, 0]);
    const cmpMetrics = FONT_METRICS[theme.fontFamilyName];
    const cmpLabelStyle: React.CSSProperties = {
      fontSize: `${fs(24)}px`,
      fontWeight: cmpMetrics.bodyWeight,
      marginBottom: "16px",
      textTransform: "uppercase",
      fontFamily: getFontFamily(theme.fontFamilyName),
      letterSpacing: `${Math.max(0.06, cmpMetrics.trackTitleEm + 0.05)}em`,
    };

    return (
      <AbsoluteFill>
        {BackgroundLayer}
        {SharedLayers}
        <div style={{ position: "absolute", top: "15%", left: 0, right: 0, bottom: "15%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "24px", zIndex: 20 }}>
          {title && (
            <AnimatedText text={title} glowColor={theme.secondaryColor} fontFamilyName={theme.fontFamilyName} overlayType={theme.overlayType} animationMode={animMode} fontScale={fscale} textCase={look.titleCase} treatment={titleTreatment} springMul={sMul} finish={finish} />
          )}
          <div style={{ display: "flex", width: "88%", gap: "20px", justifyContent: "center", alignItems: "stretch" }}>
            {/* BEFORE — recedes */}
            <div
              style={{
                flex: 1,
                background: ft.panelBg(palette),
                backdropFilter: "blur(12px)",
                borderRadius: `${ft.radiusPanel}px`,
                border: ft.panelBorder(palette),
                padding: "28px 20px",
                textAlign: "center",
                opacity: slideInLeft * 0.9,
                transform: `translateX(${leftX}px) scale(0.97)`,
                boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
              }}
            >
              <div style={{ ...cmpLabelStyle, color: "rgba(255,255,255,0.55)" }}>
                {leftLabel ?? "BEFORE"}
              </div>
              <div style={{ fontSize: `${fs(30)}px`, color: "rgba(255,255,255,0.85)", fontWeight: cmpMetrics.bodyWeight, lineHeight: 1.3, fontFamily: getFontFamily(theme.fontFamilyName) }}>
                {text}
              </div>
            </div>
            {/* Divider — quiet gradient rule + rotated chip, not a shouting VS */}
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "10px" }}>
              <div style={{ width: "2px", flex: 1, background: `linear-gradient(to bottom, transparent, ${withAlpha(theme.secondaryColor, 0.5)}, transparent)` }} />
              <div
                style={{
                  width: "14px",
                  height: "14px",
                  transform: "rotate(45deg)",
                  background: theme.secondaryColor,
                  borderRadius: "2px",
                  boxShadow: `0 0 12px ${withAlpha(theme.secondaryColor, 0.5)}`,
                }}
              />
              <div style={{ width: "2px", flex: 1, background: `linear-gradient(to bottom, transparent, ${withAlpha(theme.secondaryColor, 0.5)}, transparent)` }} />
            </div>
            {/* AFTER — wins */}
            <div
              style={{
                flex: 1,
                background: ft.panelBg(palette),
                backdropFilter: "blur(12px)",
                borderRadius: `${ft.radiusPanel}px`,
                border: `2px solid ${withAlpha(theme.secondaryColor, 0.55)}`,
                padding: "28px 20px",
                textAlign: "center",
                opacity: slideInRight,
                transform: `translateX(${rightX}px)`,
                boxShadow: `${ft.panelShadow}, inset 0 2px 0 ${withAlpha(palette.primarySoft, 0.25)}`,
              }}
            >
              <div style={{ ...cmpLabelStyle, color: theme.secondaryColor }}>
                {rightLabel ?? "AFTER"}
              </div>
              <div style={{ fontSize: `${fs(30)}px`, color: "#fff", fontWeight: cmpMetrics.displayWeight, lineHeight: 1.3, fontFamily: getFontFamily(theme.fontFamilyName) }}>
                {secondaryText ?? subtitle ?? ""}
              </div>
            </div>
          </div>
        </div>
      </AbsoluteFill>
    );
  }

  // --- LIST scene (staggered reveal with animated bullets) ---
  if (type === "list") {
    const items = listItems ?? (text ? text.split("|").map((s) => s.trim()) : ["Item 1", "Item 2", "Item 3"]);
    // 6-12 frames between rows is the professional band for list reveals —
    // duration-proportional stagger ballooned to 1.5s gaps on long scenes.
    const framesPerItem = Math.floor(durationInFrames * 0.55 / items.length);
    const itemStagger = Math.min(12, Math.max(6, framesPerItem));

    return (
      <AbsoluteFill>
        {BackgroundLayer}
        {SharedLayers}
        {/* Title as lower-third */}
        {title && (
          <LowerThird
            title={title}
            accentColor={theme.secondaryColor}
            secondaryColor={theme.primaryColor}
            durationInFrames={durationInFrames}
            variant="accent-bar"
            fontFamily={getFontFamily(theme.fontFamilyName)}
            titleWeight={FONT_METRICS[theme.fontFamilyName].displayWeight}
          />
        )}
        <div style={{ position: "absolute", top: "18%", left: "8%", right: "8%", zIndex: 20, display: "flex", flexDirection: "column", gap: "10px" }}>
          {!title && <div style={{ height: "10px" }} />}
          {items.map((item, i) => {
            const itemStart = 12 + i * itemStagger;
            const localFrame = Math.max(0, frame - itemStart);
            const itemProgress = spring({ fps, frame: localFrame, config: { damping: 16, stiffness: Math.round(110 * sMul) }, durationInFrames: 16 });
            const itemX = interpolate(itemProgress, [0, 1], [-50, 0]);
            const itemScale = interpolate(itemProgress, [0, 1], [0.9, 1]);
            const color = i % 2 === 0 ? theme.primaryColor : theme.secondaryColor;

            // Animated check mark
            const checkProgress = spring({ fps, frame: Math.max(0, localFrame - 8), config: { damping: 12, stiffness: 130 }, durationInFrames: 12 });
            const checkScale = interpolate(checkProgress, [0, 1], [0, 1]);

            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "16px",
                  opacity: itemProgress,
                  transform: `translateX(${itemX}px) scale(${itemScale})`,
                  padding: "14px 20px",
                  background: ft.panelBg(palette),
                  backdropFilter: "blur(10px)",
                  borderRadius: `${ft.radiusPanel}px`,
                  borderLeft: `${ft.accentBarWidth}px solid ${color}`,
                  boxShadow: `inset 0 1px 0 rgba(255,255,255,0.04), 0 4px 16px rgba(0,0,0,0.3)`,
                }}
              >
                <div
                  style={{
                    width: "44px",
                    height: "44px",
                    borderRadius: "50%",
                    background: `linear-gradient(135deg, ${color}30, ${color}60)`,
                    border: `2px solid ${color}`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "24px",
                    fontWeight: FONT_METRICS[theme.fontFamilyName].displayWeight,
                    fontFamily: getFontFamily(theme.fontFamilyName),
                    color: "#fff",
                    flexShrink: 0,
                    transform: `scale(${checkScale})`,
                    boxShadow: `0 0 10px ${color}30`,
                  }}
                >
                  {i + 1}
                </div>
                <div style={{ fontSize: `${fs(30)}px`, color: "#fff", fontWeight: FONT_METRICS[theme.fontFamilyName].bodyWeight, fontFamily: getFontFamily(theme.fontFamilyName), lineHeight: 1.3 }}>
                  {item}
                </div>
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    );
  }

  // --- CTA (Call-to-Action) scene (animated gradient border button) ---
  if (type === "cta") {
    // Button entrance: one clean settle from 0.85 — a 0.5-scale pop-in with
    // heavy overshoot plus stacked perpetual pulses read as "make it pop".
    const buttonEntrance = spring({
      fps,
      frame: Math.max(0, frame - 20),
      config: { damping: 13, stiffness: Math.round(170 * sMul), mass: 0.6 },
      durationInFrames: 16,
    });
    const buttonScale = interpolate(buttonEntrance, [0, 1], [0.85, 1]);
    const buttonOpacity = interpolate(buttonEntrance, [0, 1], [0, 1]);
    // Ambience is gated until the entrance has settled, and kept subtle
    const settledFrame = Math.max(0, frame - 45);
    const buttonPulse = frame > 45 ? 1 + Math.sin(settledFrame * 0.08) * 0.015 : 1;
    // Specular sweep: a soft white band crosses the pill once every ~75 frames
    // (replaces the perpetually spinning conic border — a dated trope).
    const sweepT = frame > 50 ? ((frame - 50) % 75) / 18 : -1;
    const sweepX = sweepT >= 0 && sweepT <= 1 ? interpolate(sweepT, [0, 1], [-30, 130]) : -100;
    const buttonGlow = 20;
    const ctaMetrics = FONT_METRICS[theme.fontFamilyName];

    // Arrow: one eased nudge per cycle instead of endless wiggling
    const arrowX =
      frame > 45
        ? interpolate(settledFrame % 45, [0, 8, 16, 45], [0, 7, 0, 0], {
            easing: Easing.inOut(Easing.quad),
          })
        : 0;

    return (
      <AbsoluteFill>
        {BackgroundLayer}
        {SharedLayers}
        <div style={{ position: "absolute", top: "30%", left: 0, right: 0, display: "flex", flexDirection: "column", alignItems: "center", gap: "28px", zIndex: 20, padding: "0 8%" }}>
          {title && (
            <AnimatedText
              text={title}
              glowColor={theme.secondaryColor}
              fontFamilyName={theme.fontFamilyName}
              overlayType={theme.overlayType}
              animationMode={animMode}
              fontSize={theme.overlayType === "vhs-glitch" ? 46 : 50}
              fontScale={fscale}
              textCase={look.titleCase}
              treatment={titleTreatment}
              springMul={sMul}
              finish={finish}
            />
          )}
          {text && (
            <AnimatedText text={text} glowColor={theme.primaryColor} fontFamilyName={theme.fontFamilyName} overlayType={theme.overlayType} animationMode={animMode} fontSize={30} fontScale={fscale} textCase={look.titleCase} springMul={sMul} finish={finish} />
          )}
          {/* CTA Button — static gradient border + periodic specular sweep */}
          <div
            style={{
              transform: `scale(${buttonScale * buttonPulse})`,
              opacity: buttonOpacity,
              position: "relative",
              padding: "3px",
              borderRadius: `${ft.radiusPill}px`,
              background: `linear-gradient(135deg, ${theme.primaryColor}, ${theme.secondaryColor})`,
              boxShadow: `0 0 ${buttonGlow}px ${withAlpha(theme.primaryColor, 0.3)}, ${ft.panelShadow}`,
            }}
          >
            <div
              style={{
                position: "relative",
                overflow: "hidden",
                padding: "20px 56px",
                background: finish === "print" ? theme.primaryColor : "rgba(4,6,10,0.82)",
                borderRadius: `${ft.radiusPill === 999 ? 999 : Math.max(2, ft.radiusPill - 2)}px`,
                fontSize: `${fs(32)}px`,
                fontWeight: ctaMetrics.displayWeight,
                fontFamily: getFontFamily(theme.fontFamilyName),
                color: finish === "print" ? inkOn(theme.primaryColor) : "#ffffff",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                textAlign: "center",
                display: "flex",
                alignItems: "center",
                gap: "12px",
                justifyContent: "center",
              }}
            >
              {ctaText ?? subtitle ?? "GET STARTED"}
              <span style={{ transform: `translateX(${arrowX}px)`, display: "inline-block", fontSize: `${fs(28)}px` }}>→</span>
              {/* Specular sweep band */}
              {sweepX > -60 && (
                <div
                  style={{
                    position: "absolute",
                    top: 0,
                    bottom: 0,
                    left: `${sweepX}%`,
                    width: "30%",
                    background: "linear-gradient(105deg, transparent, rgba(255,255,255,0.22), transparent)",
                    pointerEvents: "none",
                  }}
                />
              )}
            </div>
          </div>
          {subtitle && !ctaText && (
            <div style={{ fontSize: "28px", color: "rgba(255,255,255,0.6)", textAlign: "center" }}>
              {subtitle}
            </div>
          )}
        </div>
      </AbsoluteFill>
    );
  }

  if (type === "outro") {
    // Spring animations for logo entrance
    const logoEntrance = spring({
      fps,
      frame: Math.max(0, frame - 10),
      config: { damping: 12, stiffness: Math.round(90 * sMul), mass: 0.8 },
      durationInFrames: 25,
    });
    const logoScale = interpolate(logoEntrance, [0, 1], [0.7, 1]);
    const logoOpacity = interpolate(logoEntrance, [0, 1], [0, 1]);

    // Handle name fade-in
    const handleEntrance = spring({
      fps,
      frame: Math.max(0, frame - 25),
      config: { damping: 15, stiffness: Math.round(80 * sMul) },
      durationInFrames: 20,
    });
    const handleOpacity = interpolate(handleEntrance, [0, 1], [0, 1]);
    const handleY = interpolate(handleEntrance, [0, 1], [20, 0]);

    // Steady glow — oscillating multi-layer shadows fight video compression
    const glowIntensity = 20;

    return (
      <AbsoluteFill>
        {BackgroundLayer}
        {SharedLayers}
        {/* Celebratory particle burst radiating from behind the logo */}
        <ParticleBurst
          originX={50}
          originY={45}
          count={26}
          startFrame={10}
          durationInFrames={48}
          seed={(seed >>> 0) + 202}
          colors={[theme.primaryColor, theme.secondaryColor, "#ffffff"]}
          maxRadius={48}
        />
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "36px",
            zIndex: 20,
            padding: "0 8%",
          }}
        >
          {/* Outro Call to Action Header — "follow" matches the spoken VO
              ("Follow Neon Node…"); "subscribe" is the wrong verb on IG */}
          <div style={{ transform: `translateY(${(1 - logoEntrance) * -20}px)`, opacity: logoOpacity }}>
            <AnimatedText
              text={"FOLLOW FOR MORE"}
              glowColor={theme.secondaryColor}
              fontFamilyName={theme.fontFamilyName}
              overlayType={theme.overlayType}
              animationMode={animMode}
              fontSize={32}
              finish={finish}
            />
          </div>

          {/* Neon Node Logo */}
          <div
            style={{
              transform: `scale(${logoScale})`,
              opacity: logoOpacity,
              position: "relative",
              width: "220px",
              height: "220px",
              borderRadius: "24px",
              padding: "4px",
              background: `linear-gradient(135deg, ${theme.primaryColor}, ${theme.secondaryColor})`,
              boxShadow: `0 0 ${glowIntensity}px ${theme.primaryColor}60, 0 0 ${glowIntensity * 1.5}px ${theme.secondaryColor}40`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <img
              src={imageUrl || staticFile("tech_logo.png")}
              style={{
                width: "100%",
                height: "100%",
                borderRadius: "20px",
                objectFit: "contain",
                backgroundColor: "rgba(0,0,0,0.8)",
                padding: "16px",
              }}
              alt="Neon Node Logo"
            />
          </div>

          {/* Brand Name & Handle */}
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: "12px",
              opacity: handleOpacity,
              transform: `translateY(${handleY}px)`,
            }}
          >
            <AnimatedText
              text={title || "NEON NODE"}
              glowColor={theme.primaryColor}
              fontFamilyName={theme.fontFamilyName}
              overlayType={theme.overlayType}
              animationMode={animMode}
              fontSize={54}
              finish={finish}
            />
            <div
              style={{
                fontSize: "28px",
                color: "rgba(255,255,255,0.75)",
                fontFamily: theme.fontFamilyName === "Share Tech Mono" ? "monospace" : "sans-serif",
                letterSpacing: "5px",
                textTransform: "uppercase",
                textShadow: `0 0 10px ${theme.primaryColor}40`
              }}
            >
              {/* The props carry the real handle in `text` (from
                  INSTAGRAM_TECH_USERNAME) — hardcoding it here once shipped
                  a stale "@neon.node" */}
              {text || "@neon.node"}
            </div>
          </div>
        </div>
      </AbsoluteFill>
    );
  }

  // ========================================================================
  // DATA-DRIVEN SCENES (article: animated charts, ratings, UI demos).
  // Each renders only when its data is present; otherwise it falls through to
  // the SPLIT default below, so a chart scene with no data never breaks.
  // ========================================================================

  // Shared shell for chart / rating scenes: a heading with a draw-on underline,
  // the visual centered in a glass panel, and an optional caption underneath.
  const DataSceneShell = (opts: {
    heading?: string;
    caption?: string;
    children: React.ReactNode;
    panelPadding?: string;
  }) => (
    <AbsoluteFill>
      {BackgroundLayer}
      {SharedLayers}
      <div
        style={{
          position: "absolute",
          top: "14%",
          left: "7%",
          right: "7%",
          bottom: "26%",
          zIndex: 20,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "24px",
        }}
      >
        {opts.heading && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "10px" }}>
            <AnimatedText
              text={opts.heading}
              glowColor={theme.secondaryColor}
              fontFamilyName={theme.fontFamilyName}
              overlayType={theme.overlayType}
              animationMode={sceneIndex === 0 ? "none" : animMode}
              fontSize={theme.overlayType === "vhs-glitch" ? 38 : 42}
              fontScale={fscale}
              textCase={look.titleCase}
              treatment={titleTreatment}
              springMul={sMul}
              finish={finish}
            />
            <DrawnUnderline width={200} color1={theme.primaryColor} color2={theme.secondaryColor} startFrame={14} />
          </div>
        )}
        <GlassCard
          accentColor={theme.primaryColor}
          style={{
            padding: opts.panelPadding ?? "32px 28px",
            width: "100%",
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            borderRadius: `${ft.radiusPanel}px`,
            background: ft.panelBg(palette),
            boxShadow: ft.panelShadow,
          }}
        >
          {opts.children}
        </GlassCard>
        {opts.caption && (
          <div
            style={{
              fontSize: `${fs(26)}px`,
              color: "rgba(255,255,255,0.8)",
              fontFamily: getFontFamily(theme.fontFamilyName),
              textAlign: "center",
              maxWidth: "92%",
              lineHeight: 1.3,
              textShadow: "0 2px 10px rgba(0,0,0,0.7)",
            }}
          >
            {opts.caption}
          </div>
        )}
      </div>
    </AbsoluteFill>
  );

  // --- BAR CHART scene ---
  if (type === "bar-chart" && chartData && chartData.length >= 1) {
    return DataSceneShell({
      heading: title,
      caption: subtitle,
      children: (
        <BarChart
          data={chartData}
          primaryColor={theme.primaryColor}
          secondaryColor={theme.secondaryColor}
          fontFamily={getFontFamily(theme.fontFamilyName)}
          startFrame={12}
        />
      ),
    });
  }

  // --- DONUT / PIE CHART scene ---
  if (type === "chart" && chartData && chartData.length >= 1) {
    return DataSceneShell({
      heading: title,
      caption: subtitle,
      panelPadding: "26px",
      children: (
        <DonutChart
          data={chartData}
          primaryColor={theme.primaryColor}
          secondaryColor={theme.secondaryColor}
          fontFamily={getFontFamily(theme.fontFamilyName)}
          startFrame={12}
        />
      ),
    });
  }

  // --- LINE CHART scene ---
  if (type === "line-chart" && chartData && chartData.length >= 2) {
    return DataSceneShell({
      heading: title,
      caption: subtitle,
      children: (
        <LineChart
          data={chartData}
          primaryColor={theme.primaryColor}
          secondaryColor={theme.secondaryColor}
          fontFamily={getFontFamily(theme.fontFamilyName)}
          startFrame={12}
        />
      ),
    });
  }

  // --- RATING scene (star rating with partial clip-path fill + count-up) ---
  if (type === "rating" && typeof ratingValue === "number") {
    return DataSceneShell({
      heading: title,
      caption: subtitle ?? (text && !/^\d/.test(text) ? text : undefined),
      panelPadding: "40px 30px",
      children: (
        <StarRating
          value={ratingValue}
          max={ratingMax ?? 5}
          primaryColor={theme.primaryColor}
          secondaryColor={theme.secondaryColor}
          fontFamily={getFontFamily(theme.fontFamilyName)}
          startFrame={10}
          idPrefix={`sr${sceneIndex}`}
        />
      ),
    });
  }

  // --- UI-DEMO scene (simulated app walkthrough: cursor + typing + results) ---
  // The article's flagship idea — a product/app demo built entirely in code:
  // a moving cursor (never teleports), a click ripple, a field that types
  // itself, a loading spinner, then results that check in one by one.
  if (type === "ui-demo") {
    const ff = getFontFamily(theme.fontFamilyName);
    const query = (text || title || "search anything").slice(0, 30);
    const rows = (listItems && listItems.length
      ? listItems
      : subtitle
      ? [subtitle]
      : ["Result found", "Ready to go"]
    ).slice(0, 4);
    // Timeline is BUDGETED against the scene length so the full beat (type →
    // load → results → click) always lands — even on a short 90-frame scene,
    // where a fixed timeline used to push the results past the end.
    const budget = durationInFrames;
    const typeStart = Math.round(budget * 0.12);
    const typeEnd = Math.round(budget * 0.48);
    const typeFrames = Math.max(6, typeEnd - typeStart);
    // Chars/sec chosen so the query finishes typing exactly by typeEnd.
    const CPS = Math.max(6, query.length / (typeFrames / fps));
    const fieldClick = Math.max(6, typeStart - 4);
    const spinnerStart = typeEnd + 2;
    const spinnerDur = Math.max(8, Math.round(budget * 0.1));
    const resultsStart = spinnerStart + spinnerDur;
    const rowSpan = Math.max(4, Math.min(8, Math.floor((budget * 0.86 - resultsStart) / Math.max(1, rows.length))));
    const rowsEnd = resultsStart + rows.length * rowSpan;
    const buttonClick = Math.min(budget - 6, rowsEnd + 8);

    const windowIn = spring({ fps, frame, config: { damping: 18, stiffness: 120, mass: 0.7 }, durationInFrames: 12 });

    // Cursor clicks the field just before typing, holds, then travels to the
    // button and clicks it around buttonClick (holds derived from a 14f travel).
    const cStart = 4;
    const cTravel = 14;
    const cursorWaypoints: CursorWaypoint[] = [
      { x: 30, y: 26, hold: Math.max(0, fieldClick - cStart - cTravel) },
      { x: 50, y: 34, hold: Math.max(4, buttonClick - fieldClick - cTravel) },
      { x: 50, y: 70 },
    ];

    const btnIn = spring({ fps, frame: Math.max(0, frame - rowsEnd), config: { damping: 14, stiffness: 160, mass: 0.6 }, durationInFrames: 14 });
    const depress = frame >= buttonClick && frame < buttonClick + 6 ? 0.95 : 1;

    return (
      <AbsoluteFill>
        {BackgroundLayer}
        {SharedLayers}
        {/* App window */}
        <div
          style={{
            position: "absolute",
            top: "20%",
            left: "11%",
            right: "11%",
            bottom: "27%",
            zIndex: 20,
            opacity: windowIn,
            transform: `translateY(${interpolate(windowIn, [0, 1], [30, 0])}px) scale(${interpolate(windowIn, [0, 1], [0.94, 1])})`,
            display: "flex",
            flexDirection: "column",
            borderRadius: "20px",
            overflow: "hidden",
            background: "rgba(12,14,20,0.82)",
            backdropFilter: "blur(16px)",
            border: `1px solid ${theme.primaryColor}30`,
            boxShadow: `0 24px 70px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.04)`,
          }}
        >
          {/* Chrome header */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px", padding: "14px 18px", background: "rgba(255,255,255,0.05)", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
            <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#ff5f57" }} />
            <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#febc2e" }} />
            <div style={{ width: 12, height: 12, borderRadius: "50%", background: "#28c840" }} />
            <div style={{ flex: 1, marginLeft: "12px", padding: "6px 14px", borderRadius: "8px", background: "rgba(255,255,255,0.06)", fontSize: "18px", color: "rgba(255,255,255,0.6)", fontFamily: "monospace", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {title ? title.toLowerCase().replace(/\s+/g, "") + ".app" : "preview.app"}
            </div>
          </div>
          {/* Body */}
          <div style={{ position: "relative", flex: 1, padding: "26px 26px", display: "flex", flexDirection: "column", gap: "18px" }}>
            <TypingField
              text={query}
              startFrame={typeStart}
              charsPerSec={CPS}
              label={subtitle || "PROMPT"}
              placeholder="Type here…"
              accentColor={theme.primaryColor}
              fontFamily={ff}
            />
            {/* Results appear after the loading spinner */}
            <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
              {rows.map((r, i) => {
                const rs = resultsStart + i * rowSpan;
                const p = spring({ fps, frame: Math.max(0, frame - rs), config: { damping: 18, stiffness: 130 }, durationInFrames: 12 });
                if (frame < rs) return null;
                return (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "12px",
                      opacity: p,
                      transform: `translateX(${interpolate(p, [0, 1], [-24, 0])}px)`,
                      padding: "10px 14px",
                      borderRadius: "10px",
                      background: "rgba(255,255,255,0.05)",
                      border: "1px solid rgba(255,255,255,0.06)",
                    }}
                  >
                    <AnimatedCheck size={30} color={theme.primaryColor} startFrame={rs + 4} />
                    <div style={{ fontSize: "24px", color: "#fff", fontFamily: ff, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{r}</div>
                  </div>
                );
              })}
            </div>
            {/* CTA button inside the app */}
            {ctaText && frame >= rowsEnd - 2 && (
              <div style={{ marginTop: "auto", display: "flex", justifyContent: "center" }}>
                <div
                  style={{
                    transform: `scale(${interpolate(btnIn, [0, 1], [0.8, 1]) * depress})`,
                    opacity: btnIn,
                    padding: "14px 40px",
                    borderRadius: "40px",
                    background: `linear-gradient(90deg, ${theme.primaryColor}, ${theme.secondaryColor})`,
                    color: "#fff",
                    fontSize: "26px",
                    fontWeight: FONT_METRICS[theme.fontFamilyName].displayWeight,
                    fontFamily: ff,
                    letterSpacing: "2px",
                    textTransform: "uppercase",
                    boxShadow: `0 8px 24px ${theme.primaryColor}50`,
                  }}
                >
                  {ctaText}
                </div>
              </div>
            )}
            {/* Loading spinner overlays the body while "fetching" */}
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", pointerEvents: "none" }}>
              <LoadingSpinner startFrame={spinnerStart} durationInFrames={spinnerDur} size={64} color={theme.primaryColor} />
            </div>
          </div>
        </div>
        {/* Click ripples at the field and the button */}
        <ClickRipple x={50} y={34} startFrame={fieldClick} color={theme.primaryColor} />
        <ClickRipple x={50} y={70} startFrame={buttonClick} color={theme.secondaryColor} />
        {/* The cursor, above everything */}
        <AnimatedCursor waypoints={cursorWaypoints} startFrame={cStart} travelFrames={cTravel} color="#ffffff" />
      </AbsoluteFill>
    );
  }

  // --- SPLIT scene (default/fallback — now uses lower-third layout) ---
  // Title goes into a lower-third, main text stays centered
  return (
    <AbsoluteFill>
      {BackgroundLayer}
      {SharedLayers}
      {/* Lower-third for title */}
      {title && (
        <LowerThird
          title={title}
          subtitle={subtitle}
          accentColor={theme.primaryColor}
          secondaryColor={theme.secondaryColor}
          durationInFrames={durationInFrames}
          variant="accent-bar"
          fontFamily={getFontFamily(theme.fontFamilyName)}
          titleWeight={FONT_METRICS[theme.fontFamilyName].displayWeight}
        />
      )}
      {/* Main text stack — anchor + alignment follow the look's text layout.
          Counter-parallax against the camera pan (calm looks stay planar). */}
      <div style={{ position: "absolute", top: textLayout === "banner-low" ? "48%" : textLayout === "top-ticker" ? "16%" : "35%", left: 0, right: 0, display: "flex", flexDirection: "column", gap: "16px", zIndex: 20, transform: look.motion === "calm" ? undefined : `translate(${(-basePanX * 0.15).toFixed(2)}px, ${(-basePanY * 0.15).toFixed(2)}px)`, ...stackStyle }}>
        {text && (
          <AnimatedText
            text={text}
            glowColor={theme.primaryColor}
            fontFamilyName={theme.fontFamilyName}
            overlayType={theme.overlayType}
            animationMode={animMode}
            fontScale={fscale}
            textCase={look.titleCase}
            align={textAlignMode}
            treatment={titleTreatment === "gradient-fill" ? "gradient-fill" : "solid"}
            springMul={sMul}
            finish={finish}
          />
        )}
        {!title && subtitle && (
          <AnimatedText
            text={subtitle}
            glowColor={theme.primaryColor}
            fontFamilyName={theme.fontFamilyName}
            overlayType={theme.overlayType}
            animationMode={animMode}
            fontSize={theme.overlayType === "vhs-glitch" ? 26 : 30}
            fontScale={fscale}
            textCase={look.titleCase}
            align={textAlignMode}
            springMul={sMul}
            finish={finish}
          />
        )}
        {secondaryText && (
          <div style={{
            fontSize: `${fs(28)}px`,
            color: theme.secondaryColor,
            fontFamily: getFontFamily(theme.fontFamilyName),
            fontWeight: FONT_METRICS[theme.fontFamilyName].bodyWeight,
            textShadow: ft.textGlow(theme.secondaryColor),
            backgroundColor: ft.panelBg(palette),
            backdropFilter: "blur(8px)",
            padding: "10px 20px",
            borderRadius: `${ft.radiusChip}px`,
            border: ft.panelBorder(palette),
            letterSpacing: "0.07em",
            textTransform: "uppercase",
          }}>
          {secondaryText}
          </div>
        )}
      </div>
    </AbsoluteFill>
    );
};

// Every scene layout reserves its text bands assuming captions live at the
// bottom (see the heroTop comment): "center" sits exactly on metric/countdown
// numbers and "top" on list/comparison/data headers, and at zIndex 40 the
// caption always wins. All positions therefore clamp to the bottom band; the
// parameter survives only for props-JSON compatibility.
const getSubtitleWrapperStyle = (_position?: "top" | "center" | "bottom"): React.CSSProperties => {
  return {
    position: "absolute",
    width: "100%",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    zIndex: 40,
    bottom: "24%",
  };
};

const getSubtitleBoxStyle = (
  theme: ThemeProps,
  palette: Palette,
  finish: Finish,
): React.CSSProperties => {
  const isRetro = theme.overlayType === "vhs-glitch";
  const ft = FINISH_TOKENS[finish] ?? FINISH_TOKENS.neon;
  return {
    display: "flex",
    flexWrap: "wrap",
    justifyContent: "center",
    alignItems: "center",
    padding: "16px 28px",
    // 78% keeps the box clear of Instagram's right-side icon rail (~120px of
    // the 1080px width is covered by UI) while staying centered.
    maxWidth: "78%",
    background: isRetro ? "rgba(0, 0, 0, 0.65)" : ft.panelBg(palette),
    backdropFilter: "blur(12px)",
    borderRadius: `${ft.radiusPanel}px`,
    border: isRetro ? "3px solid #ffffff" : ft.panelBorder(palette) || "1px solid rgba(255, 255, 255, 0.1)",
    boxShadow: isRetro ? "5px 5px 0px rgba(0,0,0,1)" : ft.panelShadow,
  };
};

interface Word {
  text: string;
  start: number;
  end: number;
}

interface Phrase {
  words: Word[];
  start: number;
  end: number;
  styleIndex: number;
}

// Max characters per phrase — keeps a phrase short enough to fit on ONE line
// at full subtitle size, so words never wrap (let alone break mid-word).
const PHRASE_MAX_CHARS = 24;

const groupSubtitlesIntoPhrases = (subtitles: Word[]): Phrase[] => {
  const phrases: Phrase[] = [];
  let currentWords: Word[] = [];

  for (let i = 0; i < subtitles.length; i++) {
    const word = subtitles[i];
    const prevWord = currentWords[currentWords.length - 1];
    const currentChars = currentWords.reduce((acc, w) => acc + w.text.length + 1, 0);

    // Start a new phrase if:
    // 1. Current phrase has 4 words
    // 2. Or adding this word would exceed the one-line character budget
    // 3. Or there is a significant pause between words (> 0.5 seconds)
    // 4. Or it's the first word
    const isNewPhrase = currentWords.length === 0 ||
                        currentWords.length >= 4 ||
                        currentChars + word.text.length > PHRASE_MAX_CHARS ||
                        (prevWord && (word.start - prevWord.end) > 0.5);
                        
    if (isNewPhrase && currentWords.length > 0) {
      phrases.push({
        words: currentWords,
        start: currentWords[0].start,
        end: currentWords[currentWords.length - 1].end,
        styleIndex: phrases.length,
      });
      currentWords = [];
    }
    
    currentWords.push(word);
  }
  
  if (currentWords.length > 0) {
    phrases.push({
      words: currentWords,
      start: currentWords[0].start,
      end: currentWords[currentWords.length - 1].end,
      styleIndex: phrases.length,
    });
  }
  
  return phrases;
};

// Font size that guarantees the whole phrase fits on one line inside the
// subtitle box (~85% of a 1080px frame). Never drops below the 28px
// mobile-readability floor; single overlong words shrink instead of splitting.
const getPhraseFontSize = (phrase: Phrase, wordOverheadPx = 16): number => {
  const chars =
    phrase.words.reduce((acc, w) => acc + w.text.length, 0) +
    Math.max(0, phrase.words.length - 1);
  // ~0.62em average glyph width for a bold sans + per-word margin/padding
  const available = 860 - phrase.words.length * wordOverheadPx;
  return Math.max(28, Math.min(36, Math.floor(available / (chars * 0.62))));
};

// Stat tokens (numbers, percents, prices) get the accent color in captions —
// data is what the viewer should catch, and color-coding it is a standard
// pro-caption habit. Color-only (never size/weight), so metrics stay constant
// and the one-line guarantee holds.
const isStatToken = (t: string) => /[\d%$]/.test(t);

const KaraokeSubtitles: React.FC<{
  subtitles: Array<{ text: string; start: number; end: number }>;
  theme: ThemeProps;
  palette: Palette;
  finish: Finish;
}> = ({ subtitles, theme, palette, finish }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentTime = frame / fps;

  // Group words into static phrases
  const phrases = React.useMemo(() => {
    return groupSubtitlesIntoPhrases(subtitles);
  }, [subtitles]);

  // ONE karaoke style per video (seed-picked). Rotating styles per phrase
  // within a single video reads as randomized template output; cross-video
  // variety is preserved by the seed.
  // 0 bounce / 1 pill / 2 neon / 3 grow-lift / 4 underline sweep /
  // 5 spoken-word pop-in (words materialize as spoken, each in its own pill) /
  // 6 karaoke fill (color sweeps through the active word).
  const styleType = ((theme.seed ?? 0) >>> 3) % 7;

  // Find active phrase
  const activePhraseIndex = phrases.findIndex(
    (p) => currentTime >= p.start && currentTime <= p.end
  );

  if (activePhraseIndex === -1) {
    // Style 5's whole idea is that words DON'T pre-show — no lead-in preview.
    if (styleType === 5) return null;
    // Static dim lead-in for the 8 frames before the next phrase starts (the
    // old spring evaluated at negative frames and rendered at scale 0).
    const nextPhraseIndex = phrases.findIndex((p) => p.start > currentTime);
    if (nextPhraseIndex === -1) return null;
    const phrase = phrases[nextPhraseIndex];
    const phraseStartFrame = phrase.start * fps;
    if (frame < phraseStartFrame - 8) return null;

    const leadOpacity = interpolate(
      frame,
      [phraseStartFrame - 8, phraseStartFrame],
      [0, 0.35],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
    );
    const previewFontSize = getPhraseFontSize(phrase);
    return (
      <div style={getSubtitleWrapperStyle(theme.subtitlePosition)}>
        <div style={{ ...getSubtitleBoxStyle(theme, palette, finish), opacity: leadOpacity }}>
          {phrase.words.map((word, idx) => (
            <span
              key={idx}
              style={{
                color: "rgba(255, 255, 255, 0.4)",
                margin: "0 8px",
                fontSize: `${previewFontSize}px`,
                fontWeight: FONT_METRICS[theme.fontFamilyName].displayWeight,
                fontFamily: getFontFamily(theme.fontFamilyName),
                display: "inline-block",
                whiteSpace: "nowrap",
              }}
            >
              {word.text}
            </span>
          ))}
        </div>
      </div>
    );
  }

  const phrase = phrases[activePhraseIndex];

  // Last STARTED word. findIndex over start..end ranges returns -1 inside the
  // natural gaps in ASR word timings, which flipped already-spoken words back
  // to dim several times a second — constant flicker.
  let activeWordIndex = -1;
  for (let i = 0; i < phrase.words.length; i++) {
    if (currentTime >= phrase.words[i].start) activeWordIndex = i;
  }

  // Phrase box: settle in from 96% + quick fade — never scale a caption from
  // zero. Fade out over the trailing gap (skipped when the next phrase butts
  // up directly, so contiguous speech never blinks).
  const phraseStartFrame = phrase.start * fps;
  const phraseEndFrame = phrase.end * fps;
  const relativeFrame = frame - phraseStartFrame;
  const boxIn = spring({
    frame: relativeFrame,
    fps,
    config: { damping: 200, stiffness: 160, mass: 0.6 },
    durationInFrames: 8,
  });
  const boxScale = interpolate(boxIn, [0, 1], [0.96, 1]);
  const nextPhrase = phrases[activePhraseIndex + 1];
  const hasTrailingGap = !nextPhrase || nextPhrase.start - phrase.end > 0.15;
  const boxOpacity =
    interpolate(relativeFrame, [0, 5], [0, 1], {
      easing: Easing.out(Easing.quad),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }) *
    (hasTrailingGap
      ? interpolate(frame, [phraseEndFrame - 4, phraseEndFrame], [1, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 1);

  // Style 1's constant pill padding (24px) + 4px margins widens every word —
  // budget for it so the one-line guarantee (no wrapping, no split words) holds.
  // Style 5's per-word pills are wider still (28px padding + 8px margins).
  const phraseFontSize = `${getPhraseFontSize(phrase, styleType === 1 ? 28 : styleType === 5 ? 38 : 16)}px`;

  // Style 5 drops the shared caption box entirely — every spoken word carries
  // its own pill, so a mostly-empty container plate would just read as a slab.
  const boxOverride: React.CSSProperties =
    styleType === 5
      ? { background: "transparent", backdropFilter: "none", border: "none", boxShadow: "none" }
      : {};

  return (
    <div style={getSubtitleWrapperStyle(theme.subtitlePosition)}>
      <div style={{ ...getSubtitleBoxStyle(theme, palette, finish), ...boxOverride, opacity: boxOpacity, transform: `scale(${boxScale})` }}>
        {phrase.words.map((word, idx) => {
          const isActive =
            idx === activeWordIndex && currentTime <= word.end + 0.08;
          const isPast =
            idx < activeWordIndex || (idx === activeWordIndex && !isActive);

          const wordRelativeFrame = frame - word.start * fps;
          const wordBounce = spring({
            frame: wordRelativeFrame,
            fps,
            config: { damping: 14, mass: 0.5, stiffness: 160 },
            durationInFrames: 10,
          });
          // Highlight resolve driven explicitly from frames — CSS `transition`
          // never runs in Remotion (each frame renders independently).
          const wordT = interpolate(wordRelativeFrame, [0, 3], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });

          let wordStyle: React.CSSProperties = {};

          if (styleType === 0) {
            // Style 0: Bounce Highlight
            wordStyle = {
              color: isActive
                ? theme.primaryColor
                : isPast
                ? "#ffffff"
                : "rgba(255, 255, 255, 0.4)",
              fontSize: phraseFontSize,
              transform: isActive
                ? `scale(${interpolate(wordBounce, [0, 1], [1.0, 1.1])})`
                : "scale(1.0)",
              textShadow: isActive
                ? `0 0 12px ${theme.primaryColor}${alphaHex(wordT * 0.5)}`
                : "none",
            };
          } else if (styleType === 1) {
            // Style 1: Karaoke Block / Pill — constant padding so the line
            // never reflows; only the background color animates.
            wordStyle = {
              color: isActive || isPast ? "#ffffff" : "rgba(255, 255, 255, 0.4)",
              backgroundColor: isActive
                ? `${theme.secondaryColor}${alphaHex(wordT)}`
                : "transparent",
              padding: "4px 12px",
              borderRadius: "8px",
              fontSize: phraseFontSize,
              transform: isActive
                ? `scale(${interpolate(wordBounce, [0, 1], [1.0, 1.05])})`
                : "scale(1.0)",
              boxShadow: isActive
                ? "0 4px 10px rgba(0,0,0,0.3)"
                : "none",
            };
          } else if (styleType === 2) {
            // Style 2: Neon Glow (single soft layer — stacked 30px shadows
            // read as compression shimmer)
            wordStyle = {
              color: isActive ? "#ffffff" : isPast ? "#e2e8f0" : "rgba(255, 255, 255, 0.3)",
              fontSize: phraseFontSize,
              transform: isActive
                ? `scale(${interpolate(wordBounce, [0, 1], [1.0, 1.1])})`
                : "scale(1.0)",
              textShadow: isActive
                ? `0 0 12px ${theme.primaryColor}${alphaHex(wordT * 0.8)}`
                : "none",
            };
          } else if (styleType === 3) {
            // Style 3: Minimalist Grow & Lift
            wordStyle = {
              color: isActive ? theme.primaryColor : isPast ? "#ffffff" : "rgba(255, 255, 255, 0.4)",
              fontSize: phraseFontSize,
              transform: isActive
                ? `scale(${interpolate(wordBounce, [0, 1], [1.0, 1.1])}) translateY(${interpolate(wordBounce, [0, 1], [0, -3])}px)`
                : "scale(1.0) translateY(0px)",
            };
          } else if (styleType === 4) {
            // Style 4: Underline Sweep — a colored bar sweeps in under the
            // active word (constant metrics: border-bottom is always present,
            // only its color animates, so the line never reflows).
            wordStyle = {
              color: isActive || isPast ? "#ffffff" : "rgba(255, 255, 255, 0.4)",
              fontSize: phraseFontSize,
              borderBottom: `4px solid ${
                isActive ? `${theme.primaryColor}${alphaHex(wordT)}` : "transparent"
              }`,
              paddingBottom: "2px",
              transform: isActive
                ? `scale(${interpolate(wordBounce, [0, 1], [1.0, 1.06])})`
                : "scale(1.0)",
            };
          } else if (styleType === 5) {
            // Style 5: Spoken-word pop-in — the modern Reels caption: a word
            // exists ONLY once it is spoken, springing in inside its own pill;
            // the active word's pill is the accent color. Every span always
            // occupies layout (opacity/transform only), so nothing reflows.
            wordStyle = {
              color: "#ffffff",
              fontSize: phraseFontSize,
              opacity: wordT,
              padding: "6px 14px",
              borderRadius: "10px",
              backgroundColor: isActive
                ? theme.primaryColor
                : "rgba(8, 10, 16, 0.78)",
              textShadow: isActive ? "0 1px 3px rgba(0,0,0,0.45)" : "none",
              transform: `translateY(${interpolate(wordBounce, [0, 1], [10, 0])}px) scale(${interpolate(wordBounce, [0, 1], [0.8, 1])})`,
              boxShadow: isActive
                ? `0 6px 18px ${theme.primaryColor}55`
                : "0 4px 12px rgba(0,0,0,0.35)",
            };
          } else {
            // Style 6: Karaoke Fill — the accent color sweeps left-to-right
            // through the active word (classic karaoke, done with a
            // background-clip gradient; color-only, so metrics are constant).
            if (isActive) {
              const wordSpan = Math.max(0.001, word.end - word.start);
              const wp = Math.min(1, Math.max(0, (currentTime - word.start) / wordSpan));
              wordStyle = {
                fontSize: phraseFontSize,
                backgroundImage: `linear-gradient(90deg, ${theme.primaryColor} ${wp * 100}%, rgba(255,255,255,0.38) ${wp * 100}%)`,
                WebkitBackgroundClip: "text",
                backgroundClip: "text",
                color: "transparent",
                textShadow: "none",
              };
            } else {
              wordStyle = {
                fontSize: phraseFontSize,
                color: isPast ? theme.primaryColor : "rgba(255, 255, 255, 0.38)",
              };
            }
          }

          // Accent-tint stat tokens (numbers / % / $) in the classic styles so
          // data pops even before/after it is spoken. Color-only override.
          if (styleType <= 4 && !isActive && isStatToken(word.text)) {
            wordStyle.color = isPast
              ? theme.secondaryColor
              : `${theme.secondaryColor}99`;
          }

          return (
            <span
              key={idx}
              style={{
                margin: styleType === 1 ? "0 2px" : styleType === 5 ? "0 4px" : "0 8px",
                // Real loaded weight — 800 was synthetic (fuzzy) for every
                // family except Inter; Share Tech Mono has no bold at all.
                fontWeight: FONT_METRICS[theme.fontFamilyName].displayWeight,
                fontFamily: getFontFamily(theme.fontFamilyName),
                display: "inline-block",
                whiteSpace: "nowrap",
                ...wordStyle,
              }}
            >
              {word.text}
            </span>
          );
        })}
      </div>
    </div>
  );
};

// ============================================================================
// Main composition
// ============================================================================
export const Main = ({ scenes, theme, pipeline, voiceoverUrl, subtitles }: z.infer<typeof CompositionProps>) => {
  const resolvedVoiceoverUrl = React.useMemo(() => {
    if (!voiceoverUrl) return "";
    if (!voiceoverUrl.startsWith("http://") && !voiceoverUrl.startsWith("https://")) {
      return staticFile(voiceoverUrl);
    }
    try {
      const parsed = new URL(voiceoverUrl);
      if (parsed.pathname.startsWith("/public/")) {
        const filename = parsed.pathname.substring("/public/".length);
        return staticFile(filename);
      }
    } catch (e) {
      // ignore
    }
    return voiceoverUrl;
  }, [voiceoverUrl]);

  if (!scenes || scenes.length === 0) {
    return (
      <AbsoluteFill style={{ backgroundColor: "#020205" }}>
        <div style={{ color: "#ffffff", padding: 20, fontFamily: "sans-serif" }}>No scenes loaded.</div>
      </AbsoluteFill>
    );
  }

  // Fallback default theme parameters if undefined
  const activeTheme: ThemeProps = {
    primaryColor: theme?.primaryColor ?? defaultTheme.primaryColor,
    secondaryColor: theme?.secondaryColor ?? defaultTheme.secondaryColor,
    overlayType: theme?.overlayType ?? defaultTheme.overlayType,
    fontFamilyName: theme?.fontFamilyName ?? defaultTheme.fontFamilyName,
    musicTrack: theme?.musicTrack ?? defaultTheme.musicTrack ?? "none",
    cameraMotion: theme?.cameraMotion ?? defaultTheme.cameraMotion ?? "ken-burns",
    subtitlePosition: theme?.subtitlePosition ?? defaultTheme.subtitlePosition ?? "bottom",
    overlayOpacity: theme?.overlayOpacity ?? defaultTheme.overlayOpacity ?? 1,
    transitionStyle: theme?.transitionStyle ?? defaultTheme.transitionStyle ?? "crossfade",
    gradientOverlay: theme?.gradientOverlay ?? defaultTheme.gradientOverlay ?? "none",
    seed: theme?.seed ?? defaultTheme.seed ?? 0,
  };

  // Derive the per-video "look" from the seed. This is the single source of
  // the big, perceptible variety between videos (background treatment, chrome,
  // color grade, motion personality, layout) — computed once, shared by all
  // scenes so it stays consistent within a video and unique between videos.
  const look = React.useMemo(() => deriveLook((activeTheme.seed ?? 0) >>> 0), [activeTheme.seed]);

  // Full working palette from the two style-pack hexes (pure color math) and
  // the per-video design language (independent seeded stream, overlay-aware).
  const palette = React.useMemo(
    () => derivePalette(activeTheme.primaryColor, activeTheme.secondaryColor),
    [activeTheme.primaryColor, activeTheme.secondaryColor],
  );
  const finish = React.useMemo(
    () => deriveFinish((activeTheme.seed ?? 0) >>> 0, look, activeTheme.overlayType ?? "clean"),
    [activeTheme.seed, look, activeTheme.overlayType],
  );

  // Per-BOUNDARY cut plan: both sides of every cut share one spec, so exit
  // and enter motion are complementary (a real edit, not two uncoordinated
  // edge animations). Derived render-side from the seed — no schema changes.
  const cutPlan = React.useMemo(
    () =>
      deriveCutPlan(
        (activeTheme.seed ?? 0) >>> 0,
        scenes.length,
        activeTheme.transitionStyle ?? "crossfade",
        look.motion,
      ),
    [activeTheme.seed, scenes.length, activeTheme.transitionStyle, look.motion],
  );

  // Absolute start frame of each scene (prefix sums); sceneStarts[i] is where
  // scene i begins, sceneStarts[scenes.length] is the total duration.
  const sceneStarts = React.useMemo(() => {
    const starts: number[] = [0];
    for (const s of scenes) starts.push(starts[starts.length - 1] + s.durationInFrames);
    return starts;
  }, [scenes]);

  // Seed-driven finishing layers (grain, leaks, letterbox, edge frame, ...)
  // matched to the look so they read as designed, not random.
  const polish = React.useMemo(
    () => derivePolish((activeTheme.seed ?? 0) >>> 0, look, activeTheme.overlayType ?? "clean"),
    [activeTheme.seed, look, activeTheme.overlayType],
  );

  const cutBoundaries = React.useMemo(
    () =>
      sceneStarts
        .slice(1, -1)
        .map((frame, i) => ({ frame, spec: cutPlan[i + 1] })),
    [sceneStarts, cutPlan],
  );

  // Watermark text from pipeline config
  const watermarkText = pipeline?.watermark;
  const totalScenes = scenes.length;

  return (
    <AbsoluteFill style={{ backgroundColor: "#010103" }}>
      {/* Global Voiceover Audio Track */}
      {resolvedVoiceoverUrl && (
        <Audio
          src={resolvedVoiceoverUrl}
          volume={1.0}
        />
      )}

      {/* Dynamic Background Music */}
      {activeTheme.musicTrack !== "none" && (
        <Audio
          src={staticFile(MUSIC_MAP[activeTheme.musicTrack!])}
          volume={0.2}
          loop
        />
      )}

      {/* Sequenced Scenes with Transitions */}
      <Series>
        {scenes.map((scene, index) => (
          <Series.Sequence
            key={index}
            durationInFrames={scene.durationInFrames}
            layout="none"
          >
            {/* Audio pattern-interrupts: impact under the hook punch, pop
                under animated stats — but a whoosh ONLY under the heavy
                dressed cuts (the cut plan makes those every ~3rd boundary).
                A whoosh on every scene change is the loudest amateur tell in
                short-form sound design. Calm looks stay silent throughout. */}
            {look.motion !== "calm" && (
              index === 0 ? (
                <Audio src={staticFile("sfx/impact.wav")} volume={0.5} />
              ) : (
                cutPlan[index] && WHOOSH_CUTS.has(cutPlan[index].style) ? (
                  <Audio src={staticFile("sfx/whoosh.wav")} volume={0.25} />
                ) : null
              )
            )}
            {look.motion !== "calm" && (scene.type === "metric" || scene.type === "countdown") && (
              <Audio src={staticFile("sfx/pop.wav")} volume={0.35} />
            )}
            <SceneTransition
              durationInFrames={scene.durationInFrames}
              transitionStyle={activeTheme.transitionStyle!}
              sceneIndex={index}
              seed={activeTheme.seed}
              enterCut={cutPlan[index]}
              exitCut={cutPlan[index + 1]}
              accentColor={activeTheme.primaryColor}
            >
              <DynamicScene
                imageUrl={scene.imageUrl}
                videoUrl={scene.videoUrl}
                text={scene.text}
                title={scene.title}
                subtitle={scene.subtitle}
                secondaryText={scene.secondaryText}
                type={scene.type}
                durationInFrames={scene.durationInFrames}
                theme={activeTheme}
                look={look}
                palette={palette}
                finish={finish}
                textAnimation={scene.textAnimation}
                sceneIndex={index}
                totalScenes={totalScenes}
                leftLabel={scene.leftLabel}
                rightLabel={scene.rightLabel}
                listItems={scene.listItems}
                countFrom={scene.countFrom}
                countTo={scene.countTo}
                countSuffix={scene.countSuffix}
                ctaText={scene.ctaText}
                chartData={scene.chartData}
                ratingValue={scene.ratingValue}
                ratingMax={scene.ratingMax}
              />
            </SceneTransition>
          </Series.Sequence>
        ))}
      </Series>

      {/* Global Theme Overlay wrapper with customizable opacity.
          Minimal/editorial looks damp the HUD so it doesn't fight the design. */}
      <div style={{ position: "absolute", inset: 0, opacity: (activeTheme.overlayOpacity ?? 1) * (look.mutedHud ? 0.4 : 1) }}>
        <HudOverlay
          primaryColor={activeTheme.primaryColor}
          secondaryColor={activeTheme.secondaryColor}
          overlayType={activeTheme.overlayType}
          gradientOverlay={activeTheme.gradientOverlay}
        />
      </div>

      {/* Seed-driven cinematic finishing layers (grain / leaks / letterbox /
          edge frame / pulse) — cohesive with the look, capped at 3 textures. */}
      <PolishStack
        polish={polish}
        look={look}
        primaryColor={activeTheme.primaryColor}
        secondaryColor={activeTheme.secondaryColor}
        totalFrames={sceneStarts[scenes.length]}
        seed={(activeTheme.seed ?? 0) >>> 0}
      />

      {/* Global Karaoke Subtitles Overlay */}
      {subtitles && subtitles.length > 0 && (
        <KaraokeSubtitles subtitles={subtitles} theme={activeTheme} palette={palette} finish={finish} />
      )}

      {/* Cross-cut cover: carries each cut's peak ACROSS the boundary —
          the one thing butted sequences can't do from inside a scene. */}
      <CutCover boundaries={cutBoundaries} primaryColor={activeTheme.primaryColor} />

      {/* Watermark overlay (from pipeline config) */}
      {watermarkText && (
        <div
          style={{
            position: "absolute",
            // Instagram's caption/actions UI covers the bottom ~320px and the
            // right ~120px of a 1080x1920 Reel — a bottom-right watermark is
            // invisible there. Bottom-left above the caption zone is safe.
            bottom: "18%",
            left: "4%",
            fontSize: "14px",
            color: "rgba(255,255,255,0.35)",
            fontFamily: "monospace",
            letterSpacing: "2px",
            textTransform: "uppercase",
            zIndex: 100,
            pointerEvents: "none",
          }}
        >
          {watermarkText}
        </div>
      )}
    </AbsoluteFill>
  );
};

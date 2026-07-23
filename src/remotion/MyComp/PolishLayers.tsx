// ============================================================================
// PolishLayers.tsx — Cinematic finishing layers + the cross-cut CutCover
// ----------------------------------------------------------------------------
// Render-side polish selected by polish.ts. Perf rules for CI CPU rendering:
// no per-frame feTurbulence (the grain tile is a module-scope data URI Chrome
// rasterizes once), no filter:blur in any layer (light leaks are pre-blurred
// radial gradients), CutCover renders null on ~90% of frames.
// ============================================================================

import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { LookConfig } from "./looks";
import type { PolishConfig } from "./polish";
import type { CutSpec } from "./transitions";

// --- Film grain -------------------------------------------------------------
// A single static noise tile; "animation" comes from cycling 4 seeded offsets
// (frame % 4), which reads as live grain at near-zero CPU cost.
const GRAIN_TILE = `data:image/svg+xml;utf8,${encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter><rect width="240" height="240" filter="url(#n)" opacity="0.9"/></svg>',
)}`;

const GRAIN_JITTER: ReadonlyArray<readonly [number, number]> = [
  [0, 0],
  [-7, 4],
  [5, -6],
  [-3, -8],
];

const FilmGrain: React.FC<{ opacity: number; seed: number }> = ({ opacity, seed }) => {
  const frame = useCurrentFrame();
  const [jx, jy] = GRAIN_JITTER[(frame + (seed % 4)) % 4];
  return (
    <div
      style={{
        position: "absolute",
        inset: "-12%",
        backgroundImage: `url("${GRAIN_TILE}")`,
        backgroundRepeat: "repeat",
        transform: `translate(${jx}px, ${jy}px)`,
        opacity,
        mixBlendMode: "overlay",
        pointerEvents: "none",
      }}
    />
  );
};

// --- Light leaks ------------------------------------------------------------
// Two soft color blobs drifting slowly — pre-blurred via gradient falloff.
const LightLeaks: React.FC<{
  primaryColor: string;
  secondaryColor: string;
  phase: number;
}> = ({ primaryColor, secondaryColor, phase }) => {
  const frame = useCurrentFrame();
  const x1 = Math.sin(frame * 0.008 + phase) * 9;
  const y1 = Math.cos(frame * 0.006 + phase) * 7;
  const x2 = Math.cos(frame * 0.007 + phase * 1.7) * 8;
  const y2 = Math.sin(frame * 0.009 + phase * 1.7) * 6;
  const blob = (
    color: string,
    left: string,
    top: string,
    dx: number,
    dy: number,
    key: string,
  ) => (
    <div
      key={key}
      style={{
        position: "absolute",
        left,
        top,
        width: "85%",
        height: "55%",
        borderRadius: "50%",
        background: `radial-gradient(closest-side, ${color}, transparent 70%)`,
        transform: `translate(${dx}%, ${dy}%)`,
        opacity: 0.13,
        mixBlendMode: "screen",
        pointerEvents: "none",
      }}
    />
  );
  return (
    <>
      {blob(primaryColor, "-25%", "-15%", x1, y1, "leak-a")}
      {blob(secondaryColor, "45%", "60%", x2, y2, "leak-b")}
    </>
  );
};

// --- Edge frame -------------------------------------------------------------
const EdgeFrame: React.FC<{
  kind: "gradient" | "hairline";
  primaryColor: string;
  secondaryColor: string;
}> = ({ kind, primaryColor, secondaryColor }) => {
  const frame = useCurrentFrame();
  if (kind === "hairline") {
    return (
      <div
        style={{
          position: "absolute",
          inset: 18,
          border: "1px solid rgba(255,255,255,0.18)",
          pointerEvents: "none",
        }}
      />
    );
  }
  const gradient = `linear-gradient(90deg, ${primaryColor}, ${secondaryColor}, ${primaryColor})`;
  const pos = `${(frame * 0.6) % 300}% 0`;
  const bar = (style: React.CSSProperties, key: string) => (
    <div
      key={key}
      style={{
        position: "absolute",
        backgroundImage: gradient,
        backgroundSize: "300% 100%",
        backgroundPosition: pos,
        opacity: 0.55,
        pointerEvents: "none",
        ...style,
      }}
    />
  );
  return (
    <>
      {bar({ top: 0, left: 0, right: 0, height: 3 }, "ef-t")}
      {bar({ bottom: 0, left: 0, right: 0, height: 3 }, "ef-b")}
      {bar({ top: 0, bottom: 0, left: 0, width: 3 }, "ef-l")}
      {bar({ top: 0, bottom: 0, right: 0, width: 3 }, "ef-r")}
    </>
  );
};

// --- Letterbox --------------------------------------------------------------
// Cinema bars sweep in on the hook, retract while the body plays, and close
// again over the final second. Max 7% per bar — the subtitle band (bottom
// ~24%) is never touched.
const Letterbox: React.FC<{ totalFrames: number }> = ({ totalFrames }) => {
  const frame = useCurrentFrame();
  const open = interpolate(frame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const retract = interpolate(frame, [30, 48], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const closing = interpolate(frame, [totalFrames - 24, totalFrames - 4], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const barH = 7 * Math.max(open * retract, closing);
  if (barH <= 0.05) return null;
  const bar = (side: "top" | "bottom") => (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        [side]: 0,
        height: `${barH}%`,
        backgroundColor: "#010103",
        pointerEvents: "none",
      }}
    />
  );
  return (
    <>
      {bar("top")}
      {bar("bottom")}
    </>
  );
};

// --- Pulse glow -------------------------------------------------------------
// A beat-like inset glow. Opacity-only triangular pulse — no transforms, so
// it can never fight camera moves or subtitle legibility.
const PulseGlow: React.FC<{ primaryColor: string; period: number }> = ({
  primaryColor,
  period,
}) => {
  const frame = useCurrentFrame();
  const ph = (frame % period) / period;
  const tri = ph < 0.5 ? ph * 2 : 2 - ph * 2;
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        boxShadow: `inset 0 0 140px 20px ${primaryColor}`,
        opacity: 0.04 + 0.06 * tri,
        pointerEvents: "none",
      }}
    />
  );
};

// --- Halftone texture -------------------------------------------------------
const Halftone: React.FC = () => (
  <div
    style={{
      position: "absolute",
      inset: 0,
      backgroundImage:
        "radial-gradient(circle, rgba(255,255,255,0.05) 1px, transparent 1.6px)",
      backgroundSize: "12px 12px",
      opacity: 0.5,
      pointerEvents: "none",
    }}
  />
);

// --- End settle -------------------------------------------------------------
// The final ~30 frames deepen the vignette — a filmic settle into the outro.
const EndSettle: React.FC<{ totalFrames: number }> = ({ totalFrames }) => {
  const frame = useCurrentFrame();
  const k = interpolate(frame, [totalFrames - 30, totalFrames], [0, 0.15], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  if (k <= 0.005) return null;
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: "radial-gradient(ellipse at center, transparent 45%, rgba(0,0,0,0.9) 100%)",
        opacity: k,
        pointerEvents: "none",
      }}
    />
  );
};

// --- The stack --------------------------------------------------------------
export const PolishStack: React.FC<{
  polish: PolishConfig;
  look: LookConfig;
  primaryColor: string;
  secondaryColor: string;
  totalFrames: number;
  seed: number;
}> = ({ polish, primaryColor, secondaryColor, totalFrames, seed }) => {
  return (
    <AbsoluteFill style={{ zIndex: 45, pointerEvents: "none" }}>
      {polish.leaks && (
        <LightLeaks
          primaryColor={primaryColor}
          secondaryColor={secondaryColor}
          phase={polish.leakPhase}
        />
      )}
      {polish.halftone && <Halftone />}
      {polish.grain && <FilmGrain opacity={polish.grainOpacity} seed={seed} />}
      {polish.edgeFrame !== "none" && (
        <EdgeFrame
          kind={polish.edgeFrame}
          primaryColor={primaryColor}
          secondaryColor={secondaryColor}
        />
      )}
      {polish.pulse && <PulseGlow primaryColor={primaryColor} period={polish.pulsePeriod} />}
      {polish.letterbox && <Letterbox totalFrames={totalFrames} />}
      {polish.endSettle && <EndSettle totalFrames={totalFrames} />}
    </AbsoluteFill>
  );
};

// --- CutCover ---------------------------------------------------------------
// The one truly cross-cut element: a global layer above the scenes that
// carries the peak of a cut ACROSS the boundary (butted sequences can't do
// this from inside a scene). Null except within ±5 frames of a boundary.
export const CutCover: React.FC<{
  boundaries: ReadonlyArray<{ frame: number; spec: CutSpec }>;
  primaryColor: string;
}> = ({ boundaries, primaryColor }) => {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();
  const hit = boundaries.find((b) => Math.abs(frame - b.frame) <= 5);
  if (!hit) return null;
  const { spec } = hit;
  const d = frame - hit.frame;
  const progress = 1 - Math.abs(d) / 5; // triangular, peaks exactly at the cut

  if (spec.style === "whip-pan") {
    const slide = spec.dir * d * 0.12 * width;
    const streak = (top: string, h: number, delay: number, key: string) => (
      <div
        key={key}
        style={{
          position: "absolute",
          top,
          left: "-20%",
          right: "-20%",
          height: h,
          background:
            "linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent)",
          transform: `translateX(${slide + delay * spec.dir * 30}px) skewX(-8deg)`,
          opacity: 0.5 * progress,
          mixBlendMode: "screen",
          pointerEvents: "none",
        }}
      />
    );
    return (
      <AbsoluteFill style={{ zIndex: 55, pointerEvents: "none" }}>
        {streak("30%", 3, 0, "s1")}
        {streak("50%", 2, 1, "s2")}
        {streak("68%", 4, 2, "s3")}
      </AbsoluteFill>
    );
  }

  if (spec.style === "film-burn") {
    const side = spec.flavor < 0.5 ? "20% 15%" : "80% 80%";
    return (
      <AbsoluteFill style={{ zIndex: 55, pointerEvents: "none" }}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(circle at ${side}, rgba(255,179,107,0.9), ${primaryColor} 40%, transparent 75%)`,
            opacity: 0.6 * progress * spec.intensity,
            mixBlendMode: "screen",
          }}
        />
      </AbsoluteFill>
    );
  }

  if (
    spec.style === "stutter-zoom" ||
    spec.style === "chromatic-punch" ||
    spec.style === "glitch-cut" ||
    spec.style === "zoom-through"
  ) {
    // 2-frame white veil right at the cut — sells the impact.
    const veil = Math.max(0, 1 - Math.abs(d) / 2);
    if (veil <= 0) return null;
    return (
      <AbsoluteFill style={{ zIndex: 55, pointerEvents: "none" }}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundColor: "#ffffff",
            opacity: 0.25 * veil * spec.intensity,
          }}
        />
      </AbsoluteFill>
    );
  }

  return null;
};

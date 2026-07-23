// ============================================================================
// VideoFX.tsx — Reusable, render-safe motion primitives
// ----------------------------------------------------------------------------
// A library of self-contained animation components inspired by the "Claude Code
// video prompts" playbook: animated count-ups, spring-grown bar charts, SVG
// stroke draw-on donut/line charts, clip-path star ratings, a simulated app-UI
// kit (moving cursor + click ripple + loading spinner + typing field), and a
// seeded particle burst.
//
// EVERY component here is a PURE function of the current frame (+ an optional
// deterministic seed). No Math.random / Date.now / new Date, no CSS
// transitions — so they are safe under Remotion's concurrent, frame-parallel
// renderer, exactly like the rest of MyComp. They are intentionally decoupled
// from the theme system: callers pass already-resolved colors and a resolved
// CSS `fontFamily` string, so this file can be reused by any composition.
// ============================================================================

import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";
import { makeRng } from "./looks";

// ----------------------------------------------------------------------------
// Color helpers — small, dependency-free hex utilities so charts can build a
// palette by blending the two theme colors.
// ----------------------------------------------------------------------------
const clampByte = (n: number) => Math.max(0, Math.min(255, Math.round(n)));

const parseHex = (hex: string): [number, number, number] => {
  let h = (hex || "#000000").replace("#", "").trim();
  if (h.length === 3) h = h.split("").map((c) => c + c).join("");
  if (h.length < 6) h = h.padEnd(6, "0");
  const n = parseInt(h.slice(0, 6), 16);
  if (Number.isNaN(n)) return [0, 0, 0];
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};

const toHex = (r: number, g: number, b: number) =>
  "#" + [r, g, b].map((x) => clampByte(x).toString(16).padStart(2, "0")).join("");

/** Linear blend between two hex colors (t in 0..1). */
export const lerpHex = (a: string, b: string, t: number): string => {
  const [ar, ag, ab] = parseHex(a);
  const [br, bg, bb] = parseHex(b);
  return toHex(ar + (br - ar) * t, ag + (bg - ag) * t, ab + (bb - ab) * t);
};

/** 00..FF hex alpha suffix from a 0..1 value (for `${color}${alpha(t)}`). */
export const alpha = (t: number) =>
  clampByte(Math.max(0, Math.min(1, t)) * 255)
    .toString(16)
    .padStart(2, "0");

/** N-color palette blended across primary → secondary (wraps if N>2 evenly). */
export const palette = (primary: string, secondary: string, n: number): string[] => {
  if (n <= 1) return [primary];
  return Array.from({ length: n }, (_, i) => lerpHex(primary, secondary, i / (n - 1)));
};

// ----------------------------------------------------------------------------
// Number formatting for count-ups.
// ----------------------------------------------------------------------------
const formatNumber = (
  value: number,
  decimals: number,
  separator: boolean
): string => {
  if (decimals > 0) {
    const fixed = value.toFixed(decimals);
    if (!separator) return fixed;
    const [int, frac] = fixed.split(".");
    return Number(int).toLocaleString("en-US") + "." + frac;
  }
  const rounded = Math.round(value);
  return separator ? rounded.toLocaleString("en-US") : String(rounded);
};

// ============================================================================
// 1. CountUp — eased number that counts from `from` up to `value`.
// tabular-nums keeps digit columns from jittering as the value changes.
// ============================================================================
export const CountUp: React.FC<{
  value: number;
  from?: number;
  startFrame?: number;
  durationInFrames?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  separator?: boolean;
  style?: React.CSSProperties;
}> = ({
  value,
  from = 0,
  startFrame = 0,
  durationInFrames = 40,
  decimals = 0,
  prefix = "",
  suffix = "",
  separator = true,
  style,
}) => {
  const frame = useCurrentFrame();
  const current = interpolate(
    frame,
    [startFrame, startFrame + durationInFrames],
    [from, value],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }
  );
  return (
    <span style={{ fontVariantNumeric: "tabular-nums", ...style }}>
      {prefix}
      {formatNumber(current, decimals, separator)}
      {suffix}
    </span>
  );
};

// ============================================================================
// 2. AnimatedBar — a single horizontal bar that grows from width 0 via spring,
// with a rounded-right cap, gradient fill and a count-up value label.
// ============================================================================
export const AnimatedBar: React.FC<{
  label: string;
  value: number;
  maxValue: number;
  index?: number;
  startFrame?: number;
  color1: string;
  color2: string;
  fontFamily?: string;
  suffix?: string;
  height?: number;
}> = ({
  label,
  value,
  maxValue,
  index = 0,
  startFrame = 0,
  color1,
  color2,
  fontFamily,
  suffix = "",
  height = 40,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const delay = startFrame + 8 + index * 8; // 8-frame stagger (article default)
  const grow = spring({
    fps,
    frame: Math.max(0, frame - delay),
    config: { damping: 18, stiffness: 90, mass: 0.8 },
    durationInFrames: 22,
  });
  const target = maxValue > 0 ? Math.max(0, Math.min(1, value / maxValue)) : 0;
  const widthPct = interpolate(grow, [0, 1], [0, target * 100]);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "14px", width: "100%" }}>
      <div
        style={{
          width: "26%",
          textAlign: "right",
          fontSize: "22px",
          fontWeight: 700,
          color: "#fff",
          fontFamily,
          whiteSpace: "nowrap",
          overflow: "hidden",
          textOverflow: "ellipsis",
          textShadow: "0 1px 6px rgba(0,0,0,0.6)",
        }}
      >
        {label}
      </div>
      <div
        style={{
          flex: 1,
          height,
          borderRadius: height / 2,
          background: "rgba(255,255,255,0.07)",
          overflow: "hidden",
          position: "relative",
          boxShadow: "inset 0 1px 2px rgba(0,0,0,0.4)",
        }}
      >
        <div
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            bottom: 0,
            width: `${widthPct}%`,
            borderRadius: height / 2,
            background: `linear-gradient(90deg, ${color1}, ${color2})`,
            boxShadow: `0 0 14px ${color2}55`,
          }}
        />
      </div>
      <div
        style={{
          width: "18%",
          fontSize: "24px",
          fontWeight: 900,
          color: color2,
          fontFamily,
          textShadow: `0 0 10px ${color2}40`,
          whiteSpace: "nowrap",
        }}
      >
        <CountUp value={value} startFrame={delay} durationInFrames={22} suffix={suffix} />
      </div>
    </div>
  );
};

// ============================================================================
// 3. BarChart — a stack of AnimatedBars auto-scaled to the largest value.
// ============================================================================
export const BarChart: React.FC<{
  data: { label: string; value: number }[];
  primaryColor: string;
  secondaryColor: string;
  fontFamily?: string;
  suffix?: string;
  startFrame?: number;
}> = ({ data, primaryColor, secondaryColor, fontFamily, suffix = "", startFrame = 0 }) => {
  const rows = data.slice(0, 6);
  const maxValue = Math.max(1, ...rows.map((d) => Math.abs(d.value)));
  const colors = palette(primaryColor, secondaryColor, rows.length);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "18px", width: "100%" }}>
      {rows.map((d, i) => (
        <AnimatedBar
          key={i}
          index={i}
          label={d.label}
          value={d.value}
          maxValue={maxValue}
          startFrame={startFrame}
          color1={lerpHex(colors[i], "#ffffff", 0.12)}
          color2={colors[i]}
          fontFamily={fontFamily}
          suffix={suffix}
        />
      ))}
    </div>
  );
};

// ============================================================================
// 4. DonutChart — SVG donut drawn segment-by-segment via stroke-dashoffset.
// The center label swaps to whichever segment is currently drawing.
// ============================================================================
export const DonutChart: React.FC<{
  data: { label: string; value: number }[];
  primaryColor: string;
  secondaryColor: string;
  fontFamily?: string;
  startFrame?: number;
}> = ({ data, primaryColor, secondaryColor, fontFamily, startFrame = 0 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const rows = data.slice(0, 6).filter((d) => d.value > 0);
  // A donut needs at least one positive share; degenerate all-zero/negative
  // data renders nothing rather than crashing on an empty segment list.
  if (!rows.length) return null;
  const total = Math.max(1, rows.reduce((a, d) => a + d.value, 0));
  const colors = palette(primaryColor, secondaryColor, Math.max(1, rows.length));

  const R = 120;
  const STROKE = 42;
  const C = 2 * Math.PI * R;

  // Precompute per-segment geometry + draw window.
  let cumulative = 0;
  const segs = rows.map((d, i) => {
    const frac = d.value / total;
    const startAngle = (cumulative / total) * 360 - 90; // start at 12 o'clock
    const delay = startFrame + 10 + i * 12;
    cumulative += d.value;
    return { ...d, frac, startAngle, delay, pct: Math.round(frac * 100), color: colors[i % colors.length] };
  });

  // Which segment is "active" (currently drawing) → drives the center label.
  let activeIndex = 0;
  for (let i = 0; i < segs.length; i++) {
    if (frame >= segs[i].delay) activeIndex = i;
  }
  const active = segs[activeIndex];
  const labelReveal = interpolate(frame, [active.delay, active.delay + 6], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div style={{ position: "relative", width: 300, height: 300 }}>
      <svg width="300" height="300" viewBox="0 0 300 300">
        {/* Track */}
        <circle cx="150" cy="150" r={R} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth={STROKE} />
        {segs.map((s, i) => {
          const draw = spring({
            fps,
            frame: Math.max(0, frame - s.delay),
            config: { damping: 20, stiffness: 60 },
            durationInFrames: 20,
          });
          const segLen = s.frac * C;
          const dashOffset = interpolate(draw, [0, 1], [C, C - segLen]);
          return (
            <circle
              key={i}
              cx="150"
              cy="150"
              r={R}
              fill="none"
              stroke={s.color}
              strokeWidth={STROKE}
              strokeDasharray={`${segLen} ${C - segLen}`}
              strokeDashoffset={dashOffset}
              strokeLinecap="butt"
              transform={`rotate(${s.startAngle} 150 150)`}
              style={{ filter: `drop-shadow(0 0 6px ${s.color}55)` }}
            />
          );
        })}
      </svg>
      {/* Center label swaps to the active segment */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          opacity: labelReveal,
          transform: `scale(${interpolate(labelReveal, [0, 1], [0.9, 1])})`,
        }}
      >
        <div style={{ fontSize: "56px", fontWeight: 900, color: active.color, fontFamily, fontVariantNumeric: "tabular-nums", textShadow: `0 0 14px ${active.color}55` }}>
          {active.pct}%
        </div>
        <div style={{ fontSize: "22px", fontWeight: 700, color: "#fff", fontFamily, textTransform: "uppercase", letterSpacing: "2px", maxWidth: 180, textAlign: "center", lineHeight: 1.2 }}>
          {active.label}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// 5. LineChart — polyline drawn left→right via stroke-dashoffset, with a
// gradient area fill and data-point circles that pop in on a scale spring.
// ============================================================================
export const LineChart: React.FC<{
  data: { label: string; value: number }[];
  primaryColor: string;
  secondaryColor: string;
  fontFamily?: string;
  startFrame?: number;
}> = ({ data, primaryColor, secondaryColor, fontFamily, startFrame = 0 }) => {
  const frame = useCurrentFrame();
  const rows = data.slice(0, 8);
  if (rows.length < 2) return null;

  const W = 560;
  const H = 300;
  const padL = 20;
  const padR = 20;
  const padT = 24;
  const padB = 48;
  const values = rows.map((d) => d.value);
  const minV = Math.min(...values);
  const maxV = Math.max(...values);
  const range = maxV - minV || 1;
  const baseY = H - padB;

  const pts = rows.map((d, i) => {
    const x = padL + (i / (rows.length - 1)) * (W - padL - padR);
    const y = padT + (1 - (d.value - minV) / range) * (H - padT - padB);
    return { x, y, ...d };
  });

  const polyline = pts.map((p) => `${p.x},${p.y}`).join(" ");
  // Approximate path length for the draw-on effect.
  let pathLen = 0;
  for (let i = 1; i < pts.length; i++) {
    pathLen += Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y);
  }
  const drawOffset = interpolate(frame, [startFrame + 8, startFrame + 55], [pathLen, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const areaFill = interpolate(frame, [startFrame + 30, startFrame + 55], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <svg width="100%" viewBox={`0 0 ${W} ${H}`} style={{ maxWidth: W }}>
      <defs>
        <linearGradient id="lc-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={`${primaryColor}55`} />
          <stop offset="100%" stopColor={`${primaryColor}00`} />
        </linearGradient>
        <linearGradient id="lc-line" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={primaryColor} />
          <stop offset="100%" stopColor={secondaryColor} />
        </linearGradient>
      </defs>
      {/* baseline */}
      <line x1={padL} y1={baseY} x2={W - padR} y2={baseY} stroke="rgba(255,255,255,0.15)" strokeWidth={1} />
      {/* area fill */}
      <polygon
        points={`${padL},${baseY} ${polyline} ${W - padR},${baseY}`}
        fill="url(#lc-area)"
        opacity={areaFill}
      />
      {/* the line, drawn on */}
      <polyline
        points={polyline}
        fill="none"
        stroke="url(#lc-line)"
        strokeWidth={4}
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={pathLen}
        strokeDashoffset={drawOffset}
        style={{ filter: `drop-shadow(0 0 6px ${primaryColor}60)` }}
      />
      {/* data points pop in */}
      {pts.map((p, i) => {
        const dotDelay = startFrame + 12 + i * ((45 / Math.max(1, pts.length - 1)) | 0);
        const pop = interpolate(frame, [dotDelay, dotDelay + 8], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.out(Easing.back(1.6)),
        });
        return (
          <g key={i} opacity={interpolate(frame, [dotDelay, dotDelay + 4], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })}>
            <circle cx={p.x} cy={p.y} r={5 * pop} fill="#fff" stroke={secondaryColor} strokeWidth={2} />
            <text x={p.x} y={baseY + 26} textAnchor="middle" fill="rgba(255,255,255,0.7)" fontSize={18} fontFamily={fontFamily}>
              {p.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

// ============================================================================
// 6. StarRating — 5 stars with partial clip-path fill (4.8 → 5th star 80%),
// each star popping in on a stagger, plus a count-up of the numeric rating.
// ============================================================================
const StarShape: React.FC<{
  fillPercent: number;
  color: string;
  idPrefix: string;
  index: number;
  size?: number;
}> = ({ fillPercent, color, idPrefix, index, size = 56 }) => {
  const clipId = `${idPrefix}-star-${index}`; // deterministic (no Math.random)
  const d =
    "M12 2l2.9 6.26L21.5 9.3l-5 4.87 1.18 6.88L12 17.77 6.32 21.05 7.5 14.17l-5-4.87 6.6-1.04L12 2z";
  const clipW = (Math.max(0, Math.min(100, fillPercent)) / 100) * 24;
  return (
    <svg width={size} height={size} viewBox="0 0 24 24">
      <defs>
        <clipPath id={clipId}>
          <rect x="0" y="0" width={clipW} height="24" />
        </clipPath>
      </defs>
      <path d={d} fill="rgba(255,255,255,0.14)" stroke="rgba(255,255,255,0.25)" strokeWidth={0.8} />
      <path d={d} fill={color} clipPath={`url(#${clipId})`} style={{ filter: `drop-shadow(0 0 4px ${color}70)` }} />
    </svg>
  );
};

export const StarRating: React.FC<{
  value: number;
  max?: number;
  primaryColor: string;
  secondaryColor: string;
  fontFamily?: string;
  startFrame?: number;
  showValue?: boolean;
  idPrefix?: string;
}> = ({
  value,
  max = 5,
  primaryColor,
  secondaryColor,
  fontFamily,
  startFrame = 0,
  showValue = true,
  idPrefix = "sr",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const clampedMax = Math.max(1, Math.min(10, Math.round(max)));
  // Reveal the fill as a count-up so the stars "fill up" to the final rating.
  const revealed = interpolate(
    frame,
    [startFrame + 6, startFrame + 40],
    [0, Math.max(0, Math.min(clampedMax, value))],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "16px" }}>
      <div style={{ display: "flex", gap: "8px" }}>
        {Array.from({ length: clampedMax }, (_, i) => {
          const fillPercent =
            revealed >= i + 1 ? 100 : revealed > i ? (revealed - i) * 100 : 0;
          const pop = spring({
            fps,
            frame: Math.max(0, frame - (startFrame + i * 6)),
            config: { damping: 12, stiffness: 170, mass: 0.6 },
            durationInFrames: 14,
          });
          return (
            <div key={i} style={{ transform: `scale(${interpolate(pop, [0, 1], [0.2, 1])})`, opacity: pop }}>
              <StarShape
                index={i}
                idPrefix={idPrefix}
                fillPercent={fillPercent}
                color={lerpHex(primaryColor, secondaryColor, clampedMax > 1 ? i / (clampedMax - 1) : 0)}
              />
            </div>
          );
        })}
      </div>
      {showValue && (
        <div style={{ fontSize: "44px", fontWeight: 900, color: primaryColor, fontFamily, fontVariantNumeric: "tabular-nums", textShadow: `0 0 14px ${primaryColor}50` }}>
          <CountUp value={value} startFrame={startFrame + 6} durationInFrames={34} decimals={value % 1 === 0 ? 0 : 1} separator={false} />
          <span style={{ fontSize: "26px", color: "rgba(255,255,255,0.6)" }}> / {clampedMax}</span>
        </div>
      )}
    </div>
  );
};

// ============================================================================
// 7. DrawnUnderline — a stroke that draws itself on left→right. Handy accent
// under a heading (article: SVG stroke-dashoffset draw-on).
// ============================================================================
export const DrawnUnderline: React.FC<{
  width?: number;
  color1: string;
  color2: string;
  startFrame?: number;
  thickness?: number;
}> = ({ width = 240, color1, color2, startFrame = 0, thickness = 5 }) => {
  const frame = useCurrentFrame();
  const len = width;
  const offset = interpolate(frame, [startFrame, startFrame + 16], [len, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  return (
    <svg width={width} height={thickness * 2} viewBox={`0 0 ${width} ${thickness * 2}`}>
      <defs>
        <linearGradient id={`ul-${startFrame}-${width}`} x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor={color1} />
          <stop offset="100%" stopColor={color2} />
        </linearGradient>
      </defs>
      <line
        x1={0}
        y1={thickness}
        x2={width}
        y2={thickness}
        stroke={`url(#ul-${startFrame}-${width})`}
        strokeWidth={thickness}
        strokeLinecap="round"
        strokeDasharray={len}
        strokeDashoffset={offset}
      />
    </svg>
  );
};

// ============================================================================
// 8. AnimatedCheck — a checkmark that draws itself on (stroke-dashoffset).
// ============================================================================
export const AnimatedCheck: React.FC<{
  size?: number;
  color: string;
  startFrame?: number;
}> = ({ size = 40, color, startFrame = 0 }) => {
  const frame = useCurrentFrame();
  const LEN = 28; // approx length of the check polyline in the 24x24 viewBox
  const offset = interpolate(frame, [startFrame, startFrame + 12], [LEN, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="11" fill={`${color}22`} stroke={color} strokeWidth="1.5" />
      <polyline
        points="7 12.5 10.5 16 17 8.5"
        fill="none"
        stroke={color}
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeDasharray={LEN}
        strokeDashoffset={offset}
      />
    </svg>
  );
};

// ============================================================================
// 9. ClickRipple — an expanding, fading ring at a point (x/y in % of parent).
// ============================================================================
export const ClickRipple: React.FC<{
  x: number;
  y: number;
  startFrame: number;
  color?: string;
  size?: number;
}> = ({ x, y, startFrame, color = "#ffffff", size = 90 }) => {
  const frame = useCurrentFrame();
  const l = frame - startFrame;
  if (l < 0 || l > 24) return null;
  const scale = interpolate(l, [0, 24], [0.15, 1.7], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const opacity = interpolate(l, [0, 4, 24], [0, 0.55, 0], { extrapolateRight: "clamp" });
  return (
    <div
      style={{
        position: "absolute",
        left: `${x}%`,
        top: `${y}%`,
        width: size,
        height: size,
        marginLeft: -size / 2,
        marginTop: -size / 2,
        borderRadius: "50%",
        border: `2px solid ${color}`,
        boxShadow: `0 0 18px ${color}80`,
        transform: `scale(${scale})`,
        opacity,
        pointerEvents: "none",
        zIndex: 45,
      }}
    />
  );
};

// ============================================================================
// 10. AnimatedCursor — a pointer dot that eases between waypoints (never
// teleports) leaving a short fading trail. Coordinates are in % of the parent.
// ============================================================================
export interface CursorWaypoint {
  x: number;
  y: number;
  /** Frames to pause on this waypoint before travelling to the next. */
  hold?: number;
}

export const AnimatedCursor: React.FC<{
  waypoints: CursorWaypoint[];
  startFrame?: number;
  travelFrames?: number;
  color?: string;
  size?: number;
}> = ({ waypoints, startFrame = 0, travelFrames = 18, color = "#ffffff", size = 26 }) => {
  const frame = useCurrentFrame();
  const local = frame - startFrame;
  if (!waypoints.length) return null;

  // Build the travel timeline once.
  const segs: { startT: number; endT: number; from: CursorWaypoint; to: CursorWaypoint }[] = [];
  let t = waypoints[0].hold ?? 0;
  for (let k = 0; k < waypoints.length - 1; k++) {
    const startT = t;
    const endT = startT + travelFrames;
    segs.push({ startT, endT, from: waypoints[k], to: waypoints[k + 1] });
    t = endT + (waypoints[k + 1].hold ?? 0);
  }

  const posAt = (l: number): { x: number; y: number } => {
    if (l <= 0 || !segs.length) return { x: waypoints[0].x, y: waypoints[0].y };
    for (const s of segs) {
      if (l < s.startT) return { x: s.from.x, y: s.from.y };
      if (l <= s.endT) {
        const p = interpolate(l, [s.startT, s.endT], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.inOut(Easing.cubic),
        });
        return { x: s.from.x + (s.to.x - s.from.x) * p, y: s.from.y + (s.to.y - s.from.y) * p };
      }
    }
    const last = waypoints[waypoints.length - 1];
    return { x: last.x, y: last.y };
  };

  const appear = interpolate(local, [0, 6], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const trail = [
    { l: local - 3, o: 0.28, s: 0.85 },
    { l: local - 6, o: 0.16, s: 0.7 },
  ];
  const pos = posAt(local);

  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 46, opacity: appear }}>
      {trail.map((tr, i) => {
        const p = posAt(tr.l);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${p.x}%`,
              top: `${p.y}%`,
              width: size * tr.s,
              height: size * tr.s,
              marginLeft: (-size * tr.s) / 2,
              marginTop: (-size * tr.s) / 2,
              borderRadius: "50%",
              background: color,
              opacity: tr.o,
              filter: "blur(2px)",
            }}
          />
        );
      })}
      {/* the pointer */}
      <div
        style={{
          position: "absolute",
          left: `${pos.x}%`,
          top: `${pos.y}%`,
          width: size,
          height: size,
          marginLeft: -size / 2,
          marginTop: -size / 2,
          borderRadius: "50%",
          background: color,
          boxShadow: `0 2px 10px rgba(0,0,0,0.5), 0 0 12px ${color}70`,
          border: "2px solid rgba(0,0,0,0.25)",
        }}
      />
    </div>
  );
};

// ============================================================================
// 11. LoadingSpinner — a rotating SVG arc. Deterministic (rotation = frame·k).
// ============================================================================
export const LoadingSpinner: React.FC<{
  startFrame?: number;
  durationInFrames?: number;
  size?: number;
  color: string;
  strokeWidth?: number;
}> = ({ startFrame = 0, durationInFrames = 20, size = 64, color, strokeWidth = 6 }) => {
  const frame = useCurrentFrame();
  const l = frame - startFrame;
  if (l < 0 || l > durationInFrames) return null;
  const r = (size - strokeWidth) / 2;
  const c = 2 * Math.PI * r;
  const rotation = l * 9; // deg/frame
  const fade = interpolate(l, [0, 4, durationInFrames - 4, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ opacity: fade }}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth={strokeWidth} />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        stroke={color}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeDasharray={`${c * 0.28} ${c * 0.72}`}
        transform={`rotate(${rotation} ${size / 2} ${size / 2})`}
        style={{ filter: `drop-shadow(0 0 6px ${color}70)` }}
      />
    </svg>
  );
};

// ============================================================================
// 12. TypingField — an input-field mock that types text in character-by-
// character at `charsPerSec`, with a blinking caret.
// ============================================================================
export const TypingField: React.FC<{
  text: string;
  startFrame?: number;
  charsPerSec?: number;
  label?: string;
  placeholder?: string;
  accentColor: string;
  fontFamily?: string;
  width?: number | string;
}> = ({
  text,
  startFrame = 0,
  charsPerSec = 18,
  label,
  placeholder = "",
  accentColor,
  fontFamily,
  width = "100%",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const local = Math.max(0, frame - startFrame);
  const charsShown = Math.max(0, Math.min(text.length, Math.floor((local / fps) * charsPerSec)));
  const done = charsShown >= text.length;
  const shown = text.slice(0, charsShown);
  const caretOn = frame % 20 < 10;
  const focusGlow = interpolate(local, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

  return (
    <div style={{ width, display: "flex", flexDirection: "column", gap: "8px" }}>
      {label && (
        <div style={{ fontSize: "18px", fontWeight: 700, color: "rgba(255,255,255,0.7)", fontFamily, textTransform: "uppercase", letterSpacing: "2px" }}>
          {label}
        </div>
      )}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "16px 20px",
          borderRadius: "14px",
          background: "rgba(255,255,255,0.06)",
          border: `2px solid ${accentColor}${alpha(0.3 + 0.5 * focusGlow)}`,
          boxShadow: `0 0 ${12 * focusGlow}px ${accentColor}40, inset 0 1px 0 rgba(255,255,255,0.05)`,
          backdropFilter: "blur(10px)",
        }}
      >
        <div style={{ fontSize: "26px", color: shown ? "#fff" : "rgba(255,255,255,0.4)", fontFamily: fontFamily || "monospace", whiteSpace: "nowrap", overflow: "hidden" }}>
          {shown || placeholder}
          {!done && caretOn && <span style={{ color: accentColor }}>▌</span>}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// 13. ParticleBurst — N circles fly outward from a point on seeded random
// trajectories, then fade. Great behind a logo / on a hook (article).
// ============================================================================
export const ParticleBurst: React.FC<{
  originX?: number;
  originY?: number;
  count?: number;
  startFrame?: number;
  durationInFrames?: number;
  seed?: number;
  colors?: string[];
  maxRadius?: number;
}> = ({
  originX = 50,
  originY = 50,
  count = 20,
  startFrame = 0,
  durationInFrames = 40,
  seed = 1,
  colors = ["#ffffff"],
  maxRadius = 42,
}) => {
  const frame = useCurrentFrame();
  const l = frame - startFrame;

  // Precompute per-particle trajectory once from the seed (deterministic).
  const particles = React.useMemo(() => {
    const rng = makeRng((seed >>> 0) || 1);
    return Array.from({ length: count }, () => {
      const angle = rng() * Math.PI * 2;
      const dist = maxRadius * (0.5 + rng() * 0.5);
      const size = 4 + rng() * 8;
      const speed = 0.7 + rng() * 0.6;
      const color = colors[Math.floor(rng() * colors.length) % colors.length];
      return { angle, dist, size, speed, color };
    });
  }, [seed, count, maxRadius, colors]);

  if (l < 0 || l > durationInFrames) return null;

  return (
    <div style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden", zIndex: 5 }}>
      {particles.map((p, i) => {
        const prog = interpolate(l, [0, durationInFrames * p.speed], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.out(Easing.cubic),
        });
        const r = p.dist * prog;
        const x = originX + Math.cos(p.angle) * r;
        const y = originY + Math.sin(p.angle) * r;
        const opacity = interpolate(prog, [0, 0.15, 1], [0, 0.9, 0]);
        const scale = interpolate(prog, [0, 1], [1, 0.3]);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${x}%`,
              top: `${y}%`,
              width: p.size,
              height: p.size,
              marginLeft: -p.size / 2,
              marginTop: -p.size / 2,
              borderRadius: "50%",
              background: p.color,
              opacity,
              transform: `scale(${scale})`,
              boxShadow: `0 0 8px ${p.color}`,
            }}
          />
        );
      })}
    </div>
  );
};

// ============================================================================
// 14. GlassCard — reusable glass-morphism container.
// ============================================================================
export const GlassCard: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
  accentColor?: string;
  bgOpacity?: number;
  blur?: number;
}> = ({ children, style, accentColor, bgOpacity = 0.06, blur = 16 }) => (
  <div
    style={{
      background: `rgba(255,255,255,${bgOpacity})`,
      backdropFilter: `blur(${blur}px)`,
      WebkitBackdropFilter: `blur(${blur}px)`,
      border: `1px solid ${accentColor ? `${accentColor}40` : "rgba(255,255,255,0.12)"}`,
      borderRadius: "18px",
      boxShadow: "inset 0 1px 0 rgba(255,255,255,0.06), 0 12px 40px rgba(0,0,0,0.35)",
      ...style,
    }}
  >
    {children}
  </div>
);

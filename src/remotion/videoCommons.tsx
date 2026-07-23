import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Easing,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

// ─── Font Loading ────────────────────────────────────────────────────────────
const interFont = loadFont("normal", {
  subsets: ["latin"],
  weights: ["400", "600", "700", "800"],
});

export const FONT_FAMILY = interFont.fontFamily;

// ─── Safe Zone Constants ─────────────────────────────────────────────────────
export const SAFE = {
  top: 150,
  bottom: 170,
  side: 60,
};

// ─── Safe Zone Wrapper ───────────────────────────────────────────────────────
export const SafeZone: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
}> = ({ children, style }) => (
  <div
    style={{
      position: "absolute",
      top: SAFE.top,
      bottom: SAFE.bottom,
      left: SAFE.side,
      right: SAFE.side,
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      ...style,
    }}
  >
    {children}
  </div>
);

// ─── Spring Entrance Hook ────────────────────────────────────────────────────
export const useSpringEntrance = (
  delay: number = 0,
  config?: { damping?: number; stiffness?: number; mass?: number }
) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    fps,
    frame: Math.max(0, frame - delay),
    config: {
      damping: config?.damping ?? 14,
      stiffness: config?.stiffness ?? 110,
      mass: config?.mass ?? 0.7,
    },
  });
  return {
    progress: s,
    translateY: interpolate(s, [0, 1], [50, 0]),
    translateX: interpolate(s, [0, 1], [40, 0]),
    scale: interpolate(s, [0, 1], [0.7, 1]),
    opacity: interpolate(s, [0, 1], [0, 1]),
  };
};

// ─── Count-Up Component ──────────────────────────────────────────────────────
export const CountUp: React.FC<{
  from?: number;
  to: number;
  startFrame?: number;
  endFrame?: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  style?: React.CSSProperties;
}> = ({
  from = 0,
  to,
  startFrame = 0,
  endFrame = 45,
  decimals = 0,
  prefix = "",
  suffix = "",
  style,
}) => {
  const frame = useCurrentFrame();
  const current = interpolate(frame, [startFrame, endFrame], [from, to], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  return (
    <span style={style}>
      {prefix}
      {decimals > 0 ? current.toFixed(decimals) : Math.round(current)}
      {suffix}
    </span>
  );
};

// ─── Progress Bar Component ──────────────────────────────────────────────────
export const ProgressBar: React.FC<{
  percent: number;
  delay?: number;
  barColor?: string;
  trackColor?: string;
  height?: number;
  borderRadius?: number;
  style?: React.CSSProperties;
}> = ({
  percent,
  delay = 0,
  barColor = "#2563eb",
  trackColor = "#e2e8f0",
  height = 14,
  borderRadius = 7,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    fps,
    frame: Math.max(0, frame - delay),
    config: { damping: 26, stiffness: 90, mass: 1 },
  });
  const width = interpolate(s, [0, 1], [0, percent]);
  return (
    <div
      style={{
        width: "100%",
        height,
        backgroundColor: trackColor,
        borderRadius,
        overflow: "hidden",
        ...style,
      }}
    >
      <div
        style={{
          width: `${width}%`,
          height: "100%",
          backgroundColor: barColor,
          borderRadius,
        }}
      />
    </div>
  );
};

// ─── SVG Icon Library ────────────────────────────────────────────────────────

export const Icons = {
  star: (size = 24, color = "#f59e0b") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color} stroke="none">
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
  ),

  check: (size = 24, color = "#22c55e") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  ),

  checkCircle: (size = 24, color = "#22c55e") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  ),

  people: (size = 24, color = "#64748b") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
      <path d="M16 3.13a4 4 0 0 1 0 7.75" />
    </svg>
  ),

  mapPin: (size = 24, color = "#64748b") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
      <circle cx="12" cy="10" r="3" />
    </svg>
  ),

  calendar: (size = 24, color = "#64748b") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
      <line x1="16" y1="2" x2="16" y2="6" />
      <line x1="8" y1="2" x2="8" y2="6" />
      <line x1="3" y1="10" x2="21" y2="10" />
    </svg>
  ),

  clock: (size = 24, color = "#64748b") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  ),

  arrowRight: (size = 24, color = "#ffffff") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="5" y1="12" x2="19" y2="12" />
      <polyline points="12 5 19 12 12 19" />
    </svg>
  ),

  play: (size = 24, color = "#ffffff") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color} stroke="none">
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  ),

  youtube: (size = 24, color = "#FF0000") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
    </svg>
  ),

  twitter: (size = 24, color = "#ffffff") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  ),

  instagram: (size = 24, color = "#E4405F") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color}>
      <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 1 0 0 12.324 6.162 6.162 0 0 0 0-12.324zM12 16a4 4 0 1 1 0-8 4 4 0 0 1 0 8zm6.406-11.845a1.44 1.44 0 1 0 0 2.881 1.44 1.44 0 0 0 0-2.881z" />
    </svg>
  ),

  mic: (size = 24, color = "#ffffff") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" y1="19" x2="12" y2="23" />
      <line x1="8" y1="23" x2="16" y2="23" />
    </svg>
  ),

  trendingUp: (size = 24, color = "#22c55e") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="23 6 13.5 15.5 8.5 10.5 1 18" />
      <polyline points="17 6 23 6 23 12" />
    </svg>
  ),

  zap: (size = 24, color = "#f59e0b") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color} stroke="none">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  ),

  globe: (size = 24, color = "#64748b") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  ),

  sparkles: (size = 24, color = "#f59e0b") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill={color} stroke="none">
      <path d="M12 2L9.19 8.63 2 9.24l5.46 4.73L5.82 21 12 17.27 18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2z" />
      <circle cx="5" cy="5" r="1.5" />
      <circle cx="19" cy="3" r="1" />
      <circle cx="20" cy="18" r="1.5" />
    </svg>
  ),

  barChart: (size = 24, color = "#2563eb") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="20" x2="12" y2="10" />
      <line x1="18" y1="20" x2="18" y2="4" />
      <line x1="6" y1="20" x2="6" y2="16" />
    </svg>
  ),

  shield: (size = 24, color = "#2563eb") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),

  layers: (size = 24, color = "#8b5cf6") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="12 2 2 7 12 12 22 7 12 2" />
      <polyline points="2 17 12 22 22 17" />
      <polyline points="2 12 12 17 22 12" />
    </svg>
  ),

  cpu: (size = 24, color = "#06b6d4") => (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="4" y="4" width="16" height="16" rx="2" ry="2" />
      <rect x="9" y="9" width="6" height="6" />
      <line x1="9" y1="1" x2="9" y2="4" />
      <line x1="15" y1="1" x2="15" y2="4" />
      <line x1="9" y1="20" x2="9" y2="23" />
      <line x1="15" y1="20" x2="15" y2="23" />
      <line x1="20" y1="9" x2="23" y2="9" />
      <line x1="20" y1="14" x2="23" y2="14" />
      <line x1="1" y1="9" x2="4" y2="9" />
      <line x1="1" y1="14" x2="4" y2="14" />
    </svg>
  ),
};

// ─── Glassmorphic Card ───────────────────────────────────────────────────────
export const GlassCard: React.FC<{
  children: React.ReactNode;
  style?: React.CSSProperties;
  blur?: number;
  bgOpacity?: number;
  borderOpacity?: number;
}> = ({ children, style, blur = 20, bgOpacity = 0.05, borderOpacity = 0.1 }) => (
  <div
    style={{
      background: `rgba(255,255,255,${bgOpacity})`,
      backdropFilter: `blur(${blur}px)`,
      WebkitBackdropFilter: `blur(${blur}px)`,
      border: `1px solid rgba(255,255,255,${borderOpacity})`,
      borderRadius: 20,
      padding: "28px 24px",
      ...style,
    }}
  >
    {children}
  </div>
);

// ─── Animated Gradient Background ────────────────────────────────────────────
export const AnimatedGradientBg: React.FC<{
  color1?: string;
  color2?: string;
  color3?: string;
}> = ({ color1 = "#7c3aed", color2 = "#06b6d4", color3 = "#1e1b4b" }) => {
  const frame = useCurrentFrame();
  const x1 = 30 + Math.sin(frame * 0.01) * 20;
  const y1 = 30 + Math.cos(frame * 0.015) * 20;
  const x2 = 70 + Math.cos(frame * 0.012) * 20;
  const y2 = 70 + Math.sin(frame * 0.008) * 20;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: `
          radial-gradient(ellipse at ${x1}% ${y1}%, ${color1}40 0%, transparent 50%),
          radial-gradient(ellipse at ${x2}% ${y2}%, ${color2}30 0%, transparent 50%),
          ${color3}
        `,
      }}
    />
  );
};

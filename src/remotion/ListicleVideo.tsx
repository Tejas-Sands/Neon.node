import React from "react";
import {
  AbsoluteFill,
  Series,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
} from "remotion";
import {
  FONT_FAMILY,
  SafeZone,
  Icons,
} from "./videoCommons";

// ─── Demo Data ───────────────────────────────────────────────────────────────
const LISTICLE = {
  title: "5 AI Tools",
  subtitle: "You Need in 2025",
  items: [
    {
      title: "Cursor",
      desc: "The AI code editor that actually works.",
      icon: "cpu",
    },
    {
      title: "Midjourney v6",
      desc: "Photorealistic image generation.",
      icon: "sparkles",
    },
    {
      title: "Claude 3.5 Sonnet",
      desc: "The best reasoning model right now.",
      icon: "layers",
    },
    {
      title: "Runway Gen-3",
      desc: "High-fidelity video from text.",
      icon: "play",
    },
    {
      title: "Perplexity",
      desc: "The Google Search killer.",
      icon: "globe",
    },
  ],
  cta: "Follow for daily AI tips",
};

// ─── Colors ──────────────────────────────────────────────────────────────────
const C = {
  bgDark: "#0f172a",
  textLight: "#ffffff",
  textMutedLight: "#cbd5e1",
  textDark: "#0f172a",
  textMutedDark: "#334155",
};

// High-contrast accent colors for each item
const itemColors = ["#7c3aed", "#059669", "#dc2626", "#2563eb", "#d97706"];

const iconMap: Record<string, (s: number, c: string) => React.ReactNode> = {
  cpu: Icons.cpu,
  sparkles: Icons.sparkles,
  layers: Icons.layers,
  play: Icons.play,
  globe: Icons.globe,
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 1 — Hook (5s = 150 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene1Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleSpring = spring({
    fps,
    frame,
    config: { damping: 13, stiffness: 100 },
  });
  const titleY = interpolate(titleSpring, [0, 1], [100, 0]);

  const subSpring = spring({
    fps,
    frame: Math.max(0, frame - 15),
    config: { damping: 14, stiffness: 90 },
  });
  const subY = interpolate(subSpring, [0, 1], [60, 0]);

  const bgNumberOpacity = interpolate(frame, [10, 30], [0, 0.08], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bgDark }}>
      {/* Giant background number */}
      <div
        style={{
          position: "absolute",
          top: -100,
          left: -50,
          fontFamily: FONT_FAMILY,
          fontWeight: 800,
          fontSize: 800,
          color: "#ffffff",
          opacity: bgNumberOpacity,
          lineHeight: 1,
        }}
      >
        5
      </div>

      <SafeZone>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 100,
            color: C.textLight,
            textAlign: "center",
            transform: `translateY(${titleY}px)`,
            opacity: titleSpring,
            textTransform: "uppercase",
            lineHeight: 1.1,
          }}
        >
          {LISTICLE.title}
        </div>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 700,
            fontSize: 60,
            color: itemColors[0],
            textAlign: "center",
            transform: `translateY(${subY}px)`,
            opacity: subSpring,
            marginTop: 20,
          }}
        >
          {LISTICLE.subtitle}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 2-6 — List Items (4s = 120 frames each)
// ═════════════════════════════════════════════════════════════════════════════
const ListItemScene: React.FC<{
  item: (typeof LISTICLE.items)[0];
  index: number;
}> = ({ item, index }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const bgColor = itemColors[index % itemColors.length];
  // Determine if background is dark or light to set text color
  // Since our palette is mostly dark/vibrant, we'll stick to white text
  const textColor = C.textLight;
  const textMuted = "rgba(255,255,255,0.8)";

  // Slide in from right
  const entrance = spring({
    fps,
    frame,
    config: { damping: 15, stiffness: 120 },
  });
  const x = interpolate(entrance, [0, 1], [1080, 0]);

  // Icon pop
  const iconSpring = spring({
    fps,
    frame: Math.max(0, frame - 10),
    config: { damping: 12, stiffness: 150 },
  });
  const iconScale = interpolate(iconSpring, [0, 1], [0.3, 1]);

  const iconFn = iconMap[item.icon];

  return (
    <AbsoluteFill
      style={{
        backgroundColor: bgColor,
        transform: `translateX(${x}px)`,
      }}
    >
      {/* Giant background number */}
      <div
        style={{
          position: "absolute",
          top: -40,
          left: 40,
          fontFamily: FONT_FAMILY,
          fontWeight: 800,
          fontSize: 400,
          color: "#000000",
          opacity: 0.1,
          lineHeight: 1,
        }}
      >
        0{index + 1}
      </div>

      <SafeZone>
        {/* Icon */}
        <div
          style={{
            width: 160,
            height: 160,
            borderRadius: 40,
            backgroundColor: "rgba(0,0,0,0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transform: `scale(${iconScale})`,
            marginBottom: 60,
          }}
        >
          {iconFn ? iconFn(80, textColor) : null}
        </div>

        {/* Title */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 72,
            color: textColor,
            textAlign: "center",
            marginBottom: 24,
            opacity: interpolate(frame, [15, 25], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {item.title}
        </div>

        {/* Description */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 600,
            fontSize: 40,
            color: textMuted,
            textAlign: "center",
            lineHeight: 1.4,
            opacity: interpolate(frame, [20, 35], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {item.desc}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 7 — Recap & CTA (5s = 150 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene7RecapCTA: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bgDark }}>
      <SafeZone style={{ justifyContent: "flex-start", paddingTop: 80 }}>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 56,
            color: C.textLight,
            marginBottom: 40,
            textAlign: "center",
            width: "100%",
            opacity: titleOpacity,
          }}
        >
          Recap
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 20,
            width: "100%",
            marginBottom: 60,
          }}
        >
          {LISTICLE.items.map((item, i) => {
            const delay = 10 + i * 8;
            const s = spring({
              fps,
              frame: Math.max(0, frame - delay),
              config: { damping: 15, stiffness: 100 },
            });
            const x = interpolate(s, [0, 1], [-50, 0]);

            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 24,
                  transform: `translateX(${x}px)`,
                  opacity: s,
                }}
              >
                <div
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontWeight: 800,
                    fontSize: 32,
                    color: itemColors[i],
                    width: 40,
                  }}
                >
                  {i + 1}.
                </div>
                <div
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontWeight: 700,
                    fontSize: 36,
                    color: C.textLight,
                  }}
                >
                  {item.title}
                </div>
              </div>
            );
          })}
        </div>

        <div
          style={{
            width: "100%",
            padding: "32px",
            borderRadius: 20,
            backgroundColor: itemColors[0],
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            opacity: interpolate(frame, [50, 65], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            transform: `scale(${interpolate(
              spring({
                fps,
                frame: Math.max(0, frame - 50),
                config: { damping: 12, stiffness: 100 },
              }),
              [0, 1],
              [0.8, 1]
            )})`,
          }}
        >
          <span
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 800,
              fontSize: 40,
              color: "#fff",
            }}
          >
            {LISTICLE.cta}
          </span>
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// MAIN COMPOSITION
// ═════════════════════════════════════════════════════════════════════════════
export const ListicleVideo: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: C.bgDark }}>
    <Series>
      <Series.Sequence durationInFrames={150} layout="none">
        <Scene1Hook />
      </Series.Sequence>
      {LISTICLE.items.map((item, i) => (
        <Series.Sequence key={i} durationInFrames={120} layout="none">
          <ListItemScene item={item} index={i} />
        </Series.Sequence>
      ))}
      <Series.Sequence durationInFrames={150} layout="none">
        <Scene7RecapCTA />
      </Series.Sequence>
    </Series>
  </AbsoluteFill>
);

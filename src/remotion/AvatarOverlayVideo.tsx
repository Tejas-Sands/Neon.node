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
  useSpringEntrance,
  GlassCard,
  AnimatedGradientBg,
  Icons,
} from "./videoCommons";

// ─── Demo Data ───────────────────────────────────────────────────────────────
const CREATOR = {
  name: "Sample Creator",
  handle: "@yourhandle",
  title: "Tech Creator & AI Enthusiast",
  followers: "1.2M",
  followersNum: 1200000,
  videos: 500,
  views: 50000000,
  tags: ["Tech Reviews", "AI Tutorials", "Startup Tips"],
  socials: [
    { platform: "youtube", handle: "@yourhandle", color: "#FF0000" },
    { platform: "twitter", handle: "@yourhandle", color: "#ffffff" },
    { platform: "instagram", handle: "@your.handle", color: "#E4405F" },
  ],
};

// ─── Colors ──────────────────────────────────────────────────────────────────
const C = {
  bg: "#0a0a0f",
  purple: "#8b5cf6",
  cyan: "#06b6d4",
  text: "#ffffff",
  textMuted: "#94a3b8",
  glassBg: "rgba(255,255,255,0.05)",
  glassBorder: "rgba(255,255,255,0.1)",
};

// ─── Animated Avatar Ring ────────────────────────────────────────────────────
const AvatarRing: React.FC<{ size: number }> = ({ size }) => {
  const frame = useCurrentFrame();
  const rotation = frame * 1.2;
  const pulseScale = 1 + Math.sin(frame * 0.08) * 0.03;

  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: "50%",
        position: "relative",
        transform: `scale(${pulseScale})`,
      }}
    >
      {/* Animated neon ring */}
      <div
        style={{
          position: "absolute",
          inset: -4,
          borderRadius: "50%",
          background: `conic-gradient(from ${rotation}deg, ${C.purple}, ${C.cyan}, ${C.purple})`,
          filter: "blur(3px)",
        }}
      />
      {/* Inner mask */}
      <div
        style={{
          position: "absolute",
          inset: 3,
          borderRadius: "50%",
          background: C.bg,
        }}
      />
      {/* Avatar placeholder — gradient circle */}
      <div
        style={{
          position: "absolute",
          inset: 6,
          borderRadius: "50%",
          background: `linear-gradient(135deg, ${C.purple}80, ${C.cyan}60)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <span
          style={{
            fontSize: size * 0.35,
            fontWeight: 800,
            fontFamily: FONT_FAMILY,
            color: C.text,
            opacity: 0.9,
          }}
        >
          {CREATOR.name
            .split(" ")
            .map((n) => n[0])
            .join("")}
        </span>
      </div>
    </div>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 1 — Avatar Intro (4s = 120 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene1AvatarIntro: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Avatar drops in from top
  const avatarSpring = spring({
    fps,
    frame,
    config: { damping: 13, stiffness: 100, mass: 0.8 },
  });
  const avatarY = interpolate(avatarSpring, [0, 1], [-200, 0]);
  const avatarScale = interpolate(avatarSpring, [0, 1], [0.5, 1]);

  // Name enters below avatar
  const nameEntrance = useSpringEntrance(12);
  // Title enters after name
  const titleEntrance = useSpringEntrance(22);
  // Handle fades in
  const handleOpacity = interpolate(frame, [30, 45], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <AnimatedGradientBg color1={C.purple} color2={C.cyan} color3={C.bg} />

      <SafeZone>
        {/* Avatar */}
        <div
          style={{
            transform: `translateY(${avatarY}px) scale(${avatarScale})`,
            opacity: avatarSpring,
          }}
        >
          <AvatarRing size={240} />
        </div>

        {/* Name */}
        <div
          style={{
            marginTop: 40,
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 56,
            color: C.text,
            textAlign: "center",
            transform: `translateY(${nameEntrance.translateY}px)`,
            opacity: nameEntrance.opacity,
          }}
        >
          {CREATOR.name}
        </div>

        {/* Title */}
        <div
          style={{
            marginTop: 12,
            fontFamily: FONT_FAMILY,
            fontWeight: 400,
            fontSize: 32,
            color: C.textMuted,
            textAlign: "center",
            transform: `translateY(${titleEntrance.translateY}px)`,
            opacity: titleEntrance.opacity,
          }}
        >
          {CREATOR.title}
        </div>

        {/* Handle */}
        <div
          style={{
            marginTop: 16,
            fontFamily: FONT_FAMILY,
            fontWeight: 600,
            fontSize: 28,
            background: `linear-gradient(90deg, ${C.purple}, ${C.cyan})`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            opacity: handleOpacity,
          }}
        >
          {CREATOR.handle}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 2 — Stats Bar (3s = 90 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene2Stats: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const stats = [
    { icon: Icons.people(32, C.cyan), label: "Followers", value: "1.2M" },
    { icon: Icons.play(32, C.purple), label: "Videos", value: "500+" },
    { icon: Icons.trendingUp(32, "#22c55e"), label: "Views", value: "50M+" },
  ];

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <AnimatedGradientBg color1={C.purple} color2={C.cyan} color3={C.bg} />

      <SafeZone>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 700,
            fontSize: 40,
            color: C.text,
            marginBottom: 50,
            textAlign: "center",
            opacity: interpolate(frame, [0, 15], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          By the Numbers
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 24,
            width: "100%",
          }}
        >
          {stats.map((stat, i) => {
            const delay = 8 + i * 10;
            const s = spring({
              fps,
              frame: Math.max(0, frame - delay),
              config: { damping: 14, stiffness: 100 },
            });
            const x = interpolate(s, [0, 1], [i % 2 === 0 ? -300 : 300, 0]);

            return (
              <GlassCard
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
                    width: 60,
                    height: 60,
                    borderRadius: 16,
                    background: `linear-gradient(135deg, ${C.purple}20, ${C.cyan}20)`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                  }}
                >
                  {stat.icon}
                </div>
                <div>
                  <div
                    style={{
                      fontFamily: FONT_FAMILY,
                      fontWeight: 800,
                      fontSize: 44,
                      color: C.text,
                    }}
                  >
                    {stat.value}
                  </div>
                  <div
                    style={{
                      fontFamily: FONT_FAMILY,
                      fontWeight: 400,
                      fontSize: 24,
                      color: C.textMuted,
                    }}
                  >
                    {stat.label}
                  </div>
                </div>
              </GlassCard>
            );
          })}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 3 — Content Highlights (4s = 120 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene3Highlights: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const tagColors = [C.purple, C.cyan, "#22c55e"];

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <AnimatedGradientBg color1={C.purple} color2={C.cyan} color3={C.bg} />

      <SafeZone>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 700,
            fontSize: 40,
            color: C.text,
            marginBottom: 24,
            textAlign: "center",
            opacity: interpolate(frame, [0, 15], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          Content I Create
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 28,
            width: "100%",
            alignItems: "center",
            marginTop: 30,
          }}
        >
          {CREATOR.tags.map((tag, i) => {
            const delay = 10 + i * 12;
            const s = spring({
              fps,
              frame: Math.max(0, frame - delay),
              config: { damping: 12, stiffness: 120 },
            });
            const scale = interpolate(s, [0, 1], [0.3, 1]);
            const directions = [
              { x: -200, y: -30 },
              { x: 200, y: 0 },
              { x: -100, y: 30 },
            ];
            const tx = interpolate(s, [0, 1], [directions[i].x, 0]);
            const ty = interpolate(s, [0, 1], [directions[i].y, 0]);

            return (
              <div
                key={i}
                style={{
                  transform: `translate(${tx}px, ${ty}px) scale(${scale})`,
                  opacity: s,
                }}
              >
                <GlassCard
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 20,
                    padding: "24px 40px",
                    borderLeft: `4px solid ${tagColors[i]}`,
                  }}
                  bgOpacity={0.08}
                >
                  <div
                    style={{
                      width: 56,
                      height: 56,
                      borderRadius: 14,
                      background: `${tagColors[i]}20`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {i === 0
                      ? Icons.cpu(28, tagColors[i])
                      : i === 1
                      ? Icons.sparkles(28, tagColors[i])
                      : Icons.trendingUp(28, tagColors[i])}
                  </div>
                  <span
                    style={{
                      fontFamily: FONT_FAMILY,
                      fontWeight: 700,
                      fontSize: 38,
                      color: C.text,
                    }}
                  >
                    {tag}
                  </span>
                </GlassCard>
              </div>
            );
          })}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 4 — Social Links (2s = 60 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene4Socials: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const socialIcons: Record<string, (s: number, c: string) => React.ReactNode> = {
    youtube: Icons.youtube,
    twitter: Icons.twitter,
    instagram: Icons.instagram,
  };

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <AnimatedGradientBg color1={C.purple} color2={C.cyan} color3={C.bg} />

      <SafeZone>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 700,
            fontSize: 38,
            color: C.text,
            marginBottom: 50,
            textAlign: "center",
            opacity: interpolate(frame, [0, 12], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          Find Me On
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 28,
            width: "100%",
          }}
        >
          {CREATOR.socials.map((social, i) => {
            const delay = 5 + i * 8;
            const s = spring({
              fps,
              frame: Math.max(0, frame - delay),
              config: { damping: 13, stiffness: 120 },
            });
            const y = interpolate(s, [0, 1], [60, 0]);
            const iconFn = socialIcons[social.platform];

            return (
              <div
                key={i}
                style={{
                  transform: `translateY(${y}px)`,
                  opacity: s,
                }}
              >
                <GlassCard
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 20,
                    padding: "20px 28px",
                  }}
                >
                  <div
                    style={{
                      width: 52,
                      height: 52,
                      borderRadius: 14,
                      backgroundColor: "rgba(255,255,255,0.08)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    {iconFn ? iconFn(28, social.color) : null}
                  </div>
                  <div>
                    <div
                      style={{
                        fontFamily: FONT_FAMILY,
                        fontWeight: 700,
                        fontSize: 30,
                        color: C.text,
                        textTransform: "capitalize",
                      }}
                    >
                      {social.platform === "twitter" ? "X (Twitter)" : social.platform}
                    </div>
                    <div
                      style={{
                        fontFamily: FONT_FAMILY,
                        fontWeight: 400,
                        fontSize: 24,
                        color: C.textMuted,
                      }}
                    >
                      {social.handle}
                    </div>
                  </div>
                </GlassCard>
              </div>
            );
          })}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 5 — CTA (2s = 60 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene5CTA: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const nameSpring = spring({
    fps,
    frame,
    config: { damping: 12, stiffness: 110 },
  });
  const nameScale = interpolate(nameSpring, [0, 1], [0.6, 1]);

  const btnSpring = spring({
    fps,
    frame: Math.max(0, frame - 10),
    config: { damping: 14, stiffness: 100 },
  });
  const btnY = interpolate(btnSpring, [0, 1], [60, 0]);

  const pulse = 1 + Math.sin(frame * 0.15) * 0.02;

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <AnimatedGradientBg color1={C.purple} color2={C.cyan} color3={C.bg} />

      <SafeZone>
        {/* Name */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 52,
            color: C.text,
            textAlign: "center",
            transform: `scale(${nameScale})`,
            opacity: nameSpring,
          }}
        >
          {CREATOR.name}
        </div>

        {/* Follow button */}
        <div
          style={{
            marginTop: 50,
            width: "100%",
            transform: `translateY(${btnY}px) scale(${pulse})`,
            opacity: btnSpring,
          }}
        >
          <div
            style={{
              width: "100%",
              height: 72,
              borderRadius: 16,
              background: `linear-gradient(135deg, ${C.purple}, ${C.cyan})`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              boxShadow: `0 8px 32px ${C.purple}40`,
            }}
          >
            <span
              style={{
                fontFamily: FONT_FAMILY,
                fontWeight: 700,
                fontSize: 36,
                color: C.text,
                letterSpacing: 1,
              }}
            >
              Follow for More
            </span>
          </div>
        </div>

        {/* Handle */}
        <div
          style={{
            marginTop: 20,
            fontFamily: FONT_FAMILY,
            fontWeight: 600,
            fontSize: 30,
            color: C.textMuted,
            textAlign: "center",
            opacity: interpolate(frame, [15, 28], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {CREATOR.handle}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// MAIN COMPOSITION
// ═════════════════════════════════════════════════════════════════════════════
export const AvatarOverlayVideo: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: C.bg }}>
    <Series>
      <Series.Sequence durationInFrames={210} layout="none">
        <Scene1AvatarIntro />
      </Series.Sequence>
      <Series.Sequence durationInFrames={180} layout="none">
        <Scene2Stats />
      </Series.Sequence>
      <Series.Sequence durationInFrames={240} layout="none">
        <Scene3Highlights />
      </Series.Sequence>
      <Series.Sequence durationInFrames={150} layout="none">
        <Scene4Socials />
      </Series.Sequence>
      <Series.Sequence durationInFrames={120} layout="none">
        <Scene5CTA />
      </Series.Sequence>
    </Series>
  </AbsoluteFill>
);

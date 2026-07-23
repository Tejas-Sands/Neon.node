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
  Icons,
} from "./videoCommons";

// ─── Demo Data ───────────────────────────────────────────────────────────────
const PRODUCT = {
  name: "FlowStack",
  tagline: "Workflow automation, reimagined.",
  heroFeature: {
    title: "Smart Pipelines",
    description:
      "Build complex workflows visually. Drag, connect, and deploy automation in minutes — no code required.",
  },
  features: [
    { icon: "zap", title: "Instant Deploy", desc: "Ship in one click" },
    { icon: "shield", title: "Enterprise Security", desc: "SOC2 & GDPR ready" },
    { icon: "layers", title: "100+ Integrations", desc: "Connect everything" },
    { icon: "globe", title: "Global CDN", desc: "Sub-50ms latency" },
  ],
  pricing: {
    plan: "Pro",
    price: 49,
    period: "/month",
    features: [
      "Unlimited pipelines",
      "50,000 executions/mo",
      "Priority support",
      "Custom integrations",
      "Team collaboration",
    ],
  },
  trustedBy: 10000,
  companyNames: ["Acme Corp", "NovaTech", "Zenith AI", "CloudBase", "DataFlow"],
  ctaText: "Start Free Trial",
  website: "www.flowstack.io",
};

// ─── Colors ──────────────────────────────────────────────────────────────────
const C = {
  bg: "#09090b",
  accent: "#3b82f6",
  accentGlow: "#3b82f630",
  text: "#ffffff",
  textMuted: "#a1a1aa",
  cardBg: "#18181b",
  border: "#27272a",
};

const iconMap: Record<string, (s: number, c: string) => React.ReactNode> = {
  zap: Icons.zap,
  shield: Icons.shield,
  layers: Icons.layers,
  globe: Icons.globe,
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 1 — Logo Reveal (2.5s = 75 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene1Logo: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const logoSpring = spring({
    fps,
    frame,
    config: { damping: 12, stiffness: 100 },
  });
  const logoScale = interpolate(logoSpring, [0, 1], [0.4, 1]);

  const taglineOpacity = interpolate(frame, [20, 35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const taglineY = interpolate(frame, [20, 35], [20, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      {/* Spotlight gradient */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at 50% 30%, ${C.accentGlow} 0%, transparent 60%)`,
        }}
      />

      <SafeZone>
        {/* Logo mark */}
        <div
          style={{
            width: 100,
            height: 100,
            borderRadius: 24,
            background: `linear-gradient(135deg, ${C.accent}, #7c3aed)`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transform: `scale(${logoScale})`,
            opacity: logoSpring,
            boxShadow: `0 16px 48px ${C.accent}40`,
            marginBottom: 30,
          }}
        >
          {Icons.zap(48, "#ffffff")}
        </div>

        {/* Product name */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 72,
            color: C.text,
            transform: `scale(${logoScale})`,
            opacity: logoSpring,
            textAlign: "center",
          }}
        >
          {PRODUCT.name}
        </div>

        {/* Tagline */}
        <div
          style={{
            marginTop: 16,
            fontFamily: FONT_FAMILY,
            fontWeight: 400,
            fontSize: 32,
            color: C.textMuted,
            opacity: taglineOpacity,
            transform: `translateY(${taglineY}px)`,
            textAlign: "center",
          }}
        >
          {PRODUCT.tagline}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 2 — Hero Feature (3.5s = 105 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene2HeroFeature: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const cardSpring = spring({
    fps,
    frame,
    config: { damping: 14, stiffness: 90 },
  });
  const cardX = interpolate(cardSpring, [0, 1], [300, 0]);

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at 70% 40%, ${C.accentGlow} 0%, transparent 50%)`,
        }}
      />

      <SafeZone style={{ justifyContent: "flex-start", paddingTop: 60 }}>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 700,
            fontSize: 28,
            color: C.accent,
            textTransform: "uppercase",
            letterSpacing: 4,
            marginBottom: 16,
            opacity: interpolate(frame, [0, 15], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          Featured
        </div>

        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 48,
            color: C.text,
            marginBottom: 40,
            opacity: interpolate(frame, [5, 20], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {PRODUCT.heroFeature.title}
        </div>

        {/* Feature card with mock UI */}
        <div
          style={{
            width: "100%",
            transform: `translateX(${cardX}px)`,
            opacity: cardSpring,
          }}
        >
          <div
            style={{
              backgroundColor: C.cardBg,
              border: `1px solid ${C.border}`,
              borderRadius: 20,
              padding: 32,
              boxShadow: `0 8px 32px rgba(0,0,0,0.4)`,
            }}
          >
            {/* Mock UI */}
            <div
              style={{
                width: "100%",
                height: 220,
                borderRadius: 12,
                backgroundColor: "#0f0f12",
                border: `1px solid ${C.border}`,
                padding: 16,
                display: "flex",
                flexDirection: "column",
                gap: 10,
                marginBottom: 24,
              }}
            >
              {/* Mock toolbar */}
              <div style={{ display: "flex", gap: 6 }}>
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    backgroundColor: "#ef4444",
                  }}
                />
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    backgroundColor: "#f59e0b",
                  }}
                />
                <div
                  style={{
                    width: 10,
                    height: 10,
                    borderRadius: "50%",
                    backgroundColor: "#22c55e",
                  }}
                />
              </div>
              {/* Mock content lines */}
              {[70, 55, 85, 40, 60].map((w, i) => (
                <div
                  key={i}
                  style={{
                    width: `${w}%`,
                    height: 12,
                    borderRadius: 6,
                    backgroundColor:
                      i === 0 ? `${C.accent}40` : `${C.border}`,
                    opacity: interpolate(
                      frame,
                      [20 + i * 5, 30 + i * 5],
                      [0, 1],
                      {
                        extrapolateLeft: "clamp",
                        extrapolateRight: "clamp",
                      }
                    ),
                  }}
                />
              ))}
            </div>

            {/* Description */}
            <div
              style={{
                fontFamily: FONT_FAMILY,
                fontWeight: 400,
                fontSize: 30,
                color: C.textMuted,
                lineHeight: 1.5,
              }}
            >
              {PRODUCT.heroFeature.description}
            </div>
          </div>
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 3 — Feature Grid (4s = 120 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene3Features: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at 50% 50%, ${C.accentGlow} 0%, transparent 50%)`,
        }}
      />

      <SafeZone style={{ justifyContent: "flex-start", paddingTop: 40 }}>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 44,
            color: C.text,
            marginBottom: 40,
            textAlign: "center",
            opacity: titleOpacity,
          }}
        >
          Why {PRODUCT.name}?
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 20,
            width: "100%",
          }}
        >
          {PRODUCT.features.map((feat, i) => {
            const delay = 10 + i * 10;
            const s = spring({
              fps,
              frame: Math.max(0, frame - delay),
              config: { damping: 14, stiffness: 100 },
            });
            const scale = interpolate(s, [0, 1], [0.7, 1]);
            const iconFn = iconMap[feat.icon];

            return (
              <div
                key={i}
                style={{
                  backgroundColor: C.cardBg,
                  border: `1px solid ${C.border}`,
                  borderTop: `3px solid ${C.accent}`,
                  borderRadius: 16,
                  padding: "28px 20px",
                  transform: `scale(${scale})`,
                  opacity: s,
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 12,
                }}
              >
                <div
                  style={{
                    width: 52,
                    height: 52,
                    borderRadius: 14,
                    background: `${C.accent}15`,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {iconFn ? iconFn(28, C.accent) : null}
                </div>
                <div
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontWeight: 700,
                    fontSize: 28,
                    color: C.text,
                    textAlign: "center",
                  }}
                >
                  {feat.title}
                </div>
                <div
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontWeight: 400,
                    fontSize: 22,
                    color: C.textMuted,
                    textAlign: "center",
                  }}
                >
                  {feat.desc}
                </div>
              </div>
            );
          })}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 4 — Pricing (3s = 90 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene4Pricing: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const cardSpring = spring({
    fps,
    frame,
    config: { damping: 13, stiffness: 100 },
  });
  const cardScale = interpolate(cardSpring, [0, 1], [0.8, 1]);

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at 50% 40%, ${C.accent}12 0%, transparent 50%)`,
        }}
      />

      <SafeZone>
        <div
          style={{
            width: "100%",
            transform: `scale(${cardScale})`,
            opacity: cardSpring,
          }}
        >
          <div
            style={{
              backgroundColor: C.cardBg,
              border: `1px solid ${C.border}`,
              borderRadius: 24,
              padding: "36px 32px",
              position: "relative",
              overflow: "hidden",
              boxShadow: `0 12px 40px ${C.accent}15`,
            }}
          >
            {/* Badge */}
            <div
              style={{
                position: "absolute",
                top: 20,
                right: 20,
                backgroundColor: C.accent,
                color: "#fff",
                fontFamily: FONT_FAMILY,
                fontWeight: 700,
                fontSize: 18,
                padding: "6px 16px",
                borderRadius: 20,
              }}
            >
              Most Popular
            </div>

            {/* Plan name */}
            <div
              style={{
                fontFamily: FONT_FAMILY,
                fontWeight: 600,
                fontSize: 28,
                color: C.textMuted,
                textTransform: "uppercase",
                letterSpacing: 3,
              }}
            >
              {PRODUCT.pricing.plan} Plan
            </div>

            {/* Price */}
            <div
              style={{
                display: "flex",
                alignItems: "baseline",
                gap: 4,
                marginTop: 12,
              }}
            >
              <span
                style={{
                  fontFamily: FONT_FAMILY,
                  fontWeight: 800,
                  fontSize: 72,
                  color: C.text,
                }}
              >
                ${PRODUCT.pricing.price}
              </span>
              <span
                style={{
                  fontFamily: FONT_FAMILY,
                  fontWeight: 400,
                  fontSize: 28,
                  color: C.textMuted,
                }}
              >
                {PRODUCT.pricing.period}
              </span>
            </div>

            {/* Divider */}
            <div
              style={{
                width: "100%",
                height: 1,
                backgroundColor: C.border,
                margin: "24px 0",
              }}
            />

            {/* Feature list */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: 16,
              }}
            >
              {PRODUCT.pricing.features.map((feat, i) => {
                const featOpacity = interpolate(
                  frame,
                  [15 + i * 6, 25 + i * 6],
                  [0, 1],
                  { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
                );
                return (
                  <div
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 14,
                      opacity: featOpacity,
                    }}
                  >
                    {Icons.check(22, C.accent)}
                    <span
                      style={{
                        fontFamily: FONT_FAMILY,
                        fontWeight: 400,
                        fontSize: 28,
                        color: C.text,
                      }}
                    >
                      {feat}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 5 — Social Proof (2s = 60 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene5Social: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const entrance = useSpringEntrance(0);

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <SafeZone>
        <div
          style={{
            opacity: entrance.opacity,
            transform: `translateY(${entrance.translateY}px)`,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 30,
          }}
        >
          <div
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 400,
              fontSize: 28,
              color: C.textMuted,
            }}
          >
            Trusted by
          </div>

          <div
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 800,
              fontSize: 64,
              color: C.text,
            }}
          >
            <span
              style={{
                fontFamily: FONT_FAMILY,
                fontWeight: 800,
              }}
            >
              {Math.round(
                interpolate(frame, [5, 40], [0, PRODUCT.trustedBy], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                })
              ).toLocaleString()}
              + teams
            </span>
          </div>

          {/* Company logos (text circles) */}
          <div
            style={{
              display: "flex",
              gap: 16,
              flexWrap: "wrap",
              justifyContent: "center",
              marginTop: 20,
            }}
          >
            {PRODUCT.companyNames.map((name, i) => {
              const delay = 10 + i * 6;
              const s = spring({
                fps,
                frame: Math.max(0, frame - delay),
                config: { damping: 14, stiffness: 120 },
              });
              return (
                <div
                  key={i}
                  style={{
                    opacity: s,
                    transform: `scale(${interpolate(s, [0, 1], [0.5, 1])})`,
                  }}
                >
                  <div
                    style={{
                      width: 100,
                      height: 100,
                      borderRadius: "50%",
                      backgroundColor: C.cardBg,
                      border: `1px solid ${C.border}`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <span
                      style={{
                        fontFamily: FONT_FAMILY,
                        fontWeight: 700,
                        fontSize: 16,
                        color: C.textMuted,
                        textAlign: "center",
                        lineHeight: 1.1,
                      }}
                    >
                      {name.split(" ").map((w) => w[0]).join("")}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 6 — CTA (3s = 90 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene6CTA: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const nameSpring = spring({
    fps,
    frame,
    config: { damping: 12, stiffness: 110 },
  });

  const btnSpring = spring({
    fps,
    frame: Math.max(0, frame - 10),
    config: { damping: 14, stiffness: 100 },
  });
  const btnY = interpolate(btnSpring, [0, 1], [50, 0]);

  const urlOpacity = interpolate(frame, [20, 35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: C.bg }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at 50% 50%, ${C.accent}10 0%, transparent 50%)`,
        }}
      />

      <SafeZone>
        {/* Product name */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 64,
            color: C.text,
            textAlign: "center",
            transform: `scale(${interpolate(nameSpring, [0, 1], [0.6, 1])})`,
            opacity: nameSpring,
          }}
        >
          {PRODUCT.name}
        </div>

        {/* CTA Button with gradient border */}
        <div
          style={{
            marginTop: 50,
            width: "100%",
            transform: `translateY(${btnY}px)`,
            opacity: btnSpring,
          }}
        >
          {/* Gradient border wrapper */}
          <div
            style={{
              width: "100%",
              padding: 3,
              borderRadius: 18,
              background: `linear-gradient(135deg, ${C.accent}, #7c3aed)`,
              boxShadow: `0 8px 32px ${C.accent}30`,
            }}
          >
            <div
              style={{
                width: "100%",
                height: 68,
                borderRadius: 15,
                backgroundColor: C.bg,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <span
                style={{
                  fontFamily: FONT_FAMILY,
                  fontWeight: 700,
                  fontSize: 36,
                  background: `linear-gradient(90deg, ${C.accent}, #7c3aed)`,
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                {PRODUCT.ctaText}
              </span>
            </div>
          </div>
        </div>

        {/* URL */}
        <div
          style={{
            marginTop: 24,
            fontFamily: FONT_FAMILY,
            fontWeight: 600,
            fontSize: 30,
            color: C.textMuted,
            opacity: urlOpacity,
            textAlign: "center",
          }}
        >
          {PRODUCT.website}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// MAIN COMPOSITION
// ═════════════════════════════════════════════════════════════════════════════
export const ProductShowcase: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: C.bg }}>
    <Series>
      <Series.Sequence durationInFrames={120} layout="none">
        <Scene1Logo />
      </Series.Sequence>
      <Series.Sequence durationInFrames={150} layout="none">
        <Scene2HeroFeature />
      </Series.Sequence>
      <Series.Sequence durationInFrames={180} layout="none">
        <Scene3Features />
      </Series.Sequence>
      <Series.Sequence durationInFrames={150} layout="none">
        <Scene4Pricing />
      </Series.Sequence>
      <Series.Sequence durationInFrames={150} layout="none">
        <Scene5Social />
      </Series.Sequence>
      <Series.Sequence durationInFrames={150} layout="none">
        <Scene6CTA />
      </Series.Sequence>
    </Series>
  </AbsoluteFill>
);

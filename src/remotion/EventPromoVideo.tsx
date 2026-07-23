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
  GlassCard,
} from "./videoCommons";

// ─── Demo Data ───────────────────────────────────────────────────────────────
const EVENT = {
  title: "AI Summit 2025",
  date: "July 15-17",
  location: "Bangalore, India",
  venue: "BIEC Center",
  speakers: [
    { name: "Dr. Maya Rao", title: "Chief AI Scientist", bg: "#7c3aed" },
    { name: "Sam Chen", title: "Founder @ Neuro Labs", bg: "#06b6d4" },
    { name: "Priya Patel", title: "VP Engineering", bg: "#f59e0b" },
  ],
  highlights: [
    { text: "20+ Speakers", icon: "people" },
    { text: "3 Days", icon: "calendar" },
    { text: "Networking", icon: "globe" },
  ],
  cta: "Register Now",
  urgency: "Early bird ends soon",
  website: "aisummit.io",
};

// ─── Colors ──────────────────────────────────────────────────────────────────
const C = {
  bgStart: "#4c1d95", // Deep purple
  bgEnd: "#ea580c", // Vibrant orange
  text: "#ffffff",
  textMuted: "rgba(255,255,255,0.8)",
  cardBg: "rgba(0,0,0,0.15)",
  border: "rgba(255,255,255,0.2)",
};

const iconMap: Record<string, (s: number, c: string) => React.ReactNode> = {
  people: Icons.people,
  calendar: Icons.calendar,
  globe: Icons.globe,
  mapPin: Icons.mapPin,
};

// ─── Dynamic Background ──────────────────────────────────────────────────────
const EventBackground: React.FC = () => {
  const frame = useCurrentFrame();
  const angle = 135 + Math.sin(frame * 0.01) * 20;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: `linear-gradient(${angle}deg, ${C.bgStart} 0%, ${C.bgEnd} 100%)`,
      }}
    >
      {/* Floating geometric shapes */}
      <svg
        width="1080"
        height="1920"
        style={{ position: "absolute", opacity: 0.15 }}
      >
        <circle
          cx={200 + Math.sin(frame * 0.02) * 40}
          cy={300 + Math.cos(frame * 0.015) * 40}
          r="80"
          fill="none"
          stroke="#fff"
          strokeWidth="4"
        />
        <rect
          x={800 + Math.cos(frame * 0.01) * 30}
          y={400 + Math.sin(frame * 0.02) * 30}
          width="120"
          height="120"
          rx="20"
          fill="none"
          stroke="#fff"
          strokeWidth="4"
          transform={`rotate(${frame * 0.5} ${
            800 + Math.cos(frame * 0.01) * 30 + 60
          } ${400 + Math.sin(frame * 0.02) * 30 + 60})`}
        />
        <polygon
          points="500,1400 580,1550 420,1550"
          fill="none"
          stroke="#fff"
          strokeWidth="4"
          transform={`translate(${Math.sin(frame * 0.015) * 50}, ${
            Math.cos(frame * 0.01) * 50
          }) rotate(${frame * -0.3} 500 1475)`}
        />
        <circle
          cx={150 + Math.cos(frame * 0.025) * 30}
          cy={1600 + Math.sin(frame * 0.02) * 30}
          r="40"
          fill="#fff"
        />
      </svg>
    </div>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 1 — Event Title (6s = 180 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene1Title: React.FC = () => {
  const frame = useCurrentFrame();

  const entrance = useSpringEntrance(0, { damping: 12, stiffness: 100 });

  const dateOpacity = interpolate(frame, [20, 35], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      <EventBackground />
      <SafeZone>
        {/* Title */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 100,
            color: C.text,
            textAlign: "center",
            lineHeight: 1.1,
            transform: `scale(${entrance.scale}) translateY(${entrance.translateY}px)`,
            opacity: entrance.opacity,
            textShadow: "0 10px 30px rgba(0,0,0,0.3)",
          }}
        >
          {EVENT.title.split(" ").map((word, i) => (
            <React.Fragment key={i}>
              {word}
              <br />
            </React.Fragment>
          ))}
        </div>

        {/* Date Badge */}
        <div
          style={{
            marginTop: 60,
            backgroundColor: "rgba(255,255,255,0.2)",
            backdropFilter: "blur(10px)",
            padding: "16px 40px",
            borderRadius: 40,
            border: `1px solid ${C.border}`,
            opacity: dateOpacity,
            transform: `translateY(${interpolate(
              frame,
              [20, 35],
              [20, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            )}px)`,
          }}
        >
          <span
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 700,
              fontSize: 40,
              color: C.text,
            }}
          >
            {EVENT.date}
          </span>
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 2 — Speakers (8s = 240 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene2Speakers: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      <EventBackground />
      <SafeZone>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 48,
            color: C.text,
            marginBottom: 50,
            textAlign: "center",
            opacity: titleOpacity,
            textTransform: "uppercase",
            letterSpacing: 2,
          }}
        >
          Featured Speakers
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 30,
            width: "100%",
          }}
        >
          {EVENT.speakers.map((speaker, i) => {
            const delay = 10 + i * 15;
            const s = spring({
              fps,
              frame: Math.max(0, frame - delay),
              config: { damping: 14, stiffness: 100 },
            });
            const x = interpolate(s, [0, 1], [100, 0]);

            return (
              <GlassCard
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 24,
                  opacity: s,
                  transform: `translateX(${x}px)`,
                  backgroundColor: C.cardBg,
                }}
              >
                {/* Avatar Placeholder */}
                <div
                  style={{
                    width: 100,
                    height: 100,
                    borderRadius: "50%",
                    backgroundColor: speaker.bg,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    border: "3px solid rgba(255,255,255,0.3)",
                  }}
                >
                  <span
                    style={{
                      fontFamily: FONT_FAMILY,
                      fontWeight: 800,
                      fontSize: 36,
                      color: "#fff",
                    }}
                  >
                    {speaker.name
                      .split(" ")
                      .map((n) => n[0])
                      .join("")}
                  </span>
                </div>
                <div>
                  <div
                    style={{
                      fontFamily: FONT_FAMILY,
                      fontWeight: 700,
                      fontSize: 36,
                      color: C.text,
                    }}
                  >
                    {speaker.name}
                  </div>
                  <div
                    style={{
                      fontFamily: FONT_FAMILY,
                      fontWeight: 400,
                      fontSize: 26,
                      color: C.textMuted,
                      marginTop: 4,
                    }}
                  >
                    {speaker.title}
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
// SCENE 3 — Highlights (6s = 180 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene3Highlights: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const titleOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill>
      <EventBackground />
      <SafeZone>
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 800,
            fontSize: 48,
            color: C.text,
            marginBottom: 60,
            textAlign: "center",
            opacity: titleOpacity,
          }}
        >
          What to Expect
        </div>

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 40,
            width: "100%",
            alignItems: "center",
          }}
        >
          {EVENT.highlights.map((hl, i) => {
            const delay = 10 + i * 12;
            const s = spring({
              fps,
              frame: Math.max(0, frame - delay),
              config: { damping: 13, stiffness: 110 },
            });
            const scale = interpolate(s, [0, 1], [0.5, 1]);
            const iconFn = iconMap[hl.icon];

            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 24,
                  opacity: s,
                  transform: `scale(${scale})`,
                  backgroundColor: "rgba(255,255,255,0.1)",
                  padding: "24px 40px",
                  borderRadius: 24,
                  border: `1px solid ${C.border}`,
                  width: "90%",
                  justifyContent: "center",
                }}
              >
                {iconFn ? iconFn(48, C.text) : null}
                <span
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontWeight: 700,
                    fontSize: 44,
                    color: C.text,
                  }}
                >
                  {hl.text}
                </span>
              </div>
            );
          })}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// SCENE 4 — Date & Venue (5s = 150 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene4DateVenue: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const elements = [
    { icon: Icons.calendar, title: EVENT.date, desc: "Add to Calendar" },
    { icon: Icons.mapPin, title: EVENT.location, desc: EVENT.venue },
  ];

  return (
    <AbsoluteFill>
      <EventBackground />
      <SafeZone>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 60,
            width: "100%",
          }}
        >
          {elements.map((el, i) => {
            const delay = 5 + i * 15;
            const s = spring({
              fps,
              frame: Math.max(0, frame - delay),
              config: { damping: 14, stiffness: 100 },
            });
            const y = interpolate(s, [0, 1], [50, 0]);

            return (
              <GlassCard
                key={i}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  gap: 20,
                  opacity: s,
                  transform: `translateY(${y}px)`,
                  backgroundColor: C.cardBg,
                  padding: "40px",
                }}
              >
                <div
                  style={{
                    width: 80,
                    height: 80,
                    borderRadius: 20,
                    backgroundColor: "rgba(255,255,255,0.2)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  {el.icon(40, C.text)}
                </div>
                <div
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontWeight: 800,
                    fontSize: 48,
                    color: C.text,
                    textAlign: "center",
                  }}
                >
                  {el.title}
                </div>
                <div
                  style={{
                    fontFamily: FONT_FAMILY,
                    fontWeight: 400,
                    fontSize: 32,
                    color: C.textMuted,
                    textAlign: "center",
                  }}
                >
                  {el.desc}
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
// SCENE 5 — Register CTA (5s = 150 frames)
// ═════════════════════════════════════════════════════════════════════════════
const Scene5Register: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const btnSpring = spring({
    fps,
    frame: Math.max(0, frame - 10),
    config: { damping: 12, stiffness: 100 },
  });
  const btnScale = interpolate(btnSpring, [0, 1], [0.5, 1]);

  const pulse = 1 + Math.sin(frame * 0.15) * 0.03;

  return (
    <AbsoluteFill>
      <EventBackground />
      <SafeZone>
        {/* Urgency Text */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 700,
            fontSize: 36,
            color: "#fbbf24", // Yellow for urgency
            textTransform: "uppercase",
            letterSpacing: 2,
            marginBottom: 40,
            opacity: interpolate(frame, [5, 20], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            transform: `translateY(${interpolate(
              frame,
              [5, 20],
              [20, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            )}px)`,
          }}
        >
          {EVENT.urgency}
        </div>

        {/* CTA Button */}
        <div
          style={{
            width: "100%",
            height: 90,
            borderRadius: 45,
            backgroundColor: "#ffffff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transform: `scale(${btnScale * pulse})`,
            opacity: btnSpring,
            boxShadow: "0 20px 50px rgba(0,0,0,0.3)",
            marginBottom: 40,
          }}
        >
          <span
            style={{
              fontFamily: FONT_FAMILY,
              fontWeight: 800,
              fontSize: 40,
              color: C.bgStart, // Text color matches background start
            }}
          >
            {EVENT.cta}
          </span>
        </div>

        {/* Website */}
        <div
          style={{
            fontFamily: FONT_FAMILY,
            fontWeight: 600,
            fontSize: 44,
            color: C.text,
            opacity: interpolate(frame, [25, 40], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          {EVENT.website}
        </div>
      </SafeZone>
    </AbsoluteFill>
  );
};

// ═════════════════════════════════════════════════════════════════════════════
// MAIN COMPOSITION
// ═════════════════════════════════════════════════════════════════════════════
export const EventPromoVideo: React.FC = () => (
  <AbsoluteFill>
    <Series>
      <Series.Sequence durationInFrames={180} layout="none">
        <Scene1Title />
      </Series.Sequence>
      <Series.Sequence durationInFrames={240} layout="none">
        <Scene2Speakers />
      </Series.Sequence>
      <Series.Sequence durationInFrames={180} layout="none">
        <Scene3Highlights />
      </Series.Sequence>
      <Series.Sequence durationInFrames={150} layout="none">
        <Scene4DateVenue />
      </Series.Sequence>
      <Series.Sequence durationInFrames={150} layout="none">
        <Scene5Register />
      </Series.Sequence>
    </Series>
  </AbsoluteFill>
);

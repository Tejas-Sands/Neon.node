import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig } from "remotion";
import { EASE, SPRINGS } from "./motion";

type LowerThirdVariant = "accent-bar" | "minimal" | "news-ticker";

interface LowerThirdProps {
  /** Main title text */
  title: string;
  /** Optional subtitle */
  subtitle?: string;
  /** Accent color for the animated bar */
  accentColor: string;
  /** Secondary accent */
  secondaryColor?: string;
  /** Total scene duration to time the exit animation */
  durationInFrames: number;
  /** Font family name */
  fontFamily?: string;
  /** Title weight — pass the family's REAL loaded weight (FONT_METRICS);
   *  the old hardcoded 800 was synthesized for most families. */
  titleWeight?: number;
  /** Visual variant */
  variant?: LowerThirdVariant;
}

/**
 * LowerThird — a sleek kinetic lower-third title bar.
 *
 * Animates in from the left with a leading accent line, displays title/subtitle
 * on a frosted glass panel, then auto-exits with a reverse slide near scene end.
 */
export const LowerThird: React.FC<LowerThirdProps> = ({
  title,
  subtitle,
  accentColor,
  secondaryColor = "#ffffff",
  durationInFrames,
  fontFamily = "Inter, sans-serif",
  titleWeight = 700,
  variant = "accent-bar",
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // ── Entrance timing ────────────────────────────────────────────────────
  const enterDelay = 10; // start after impact frame
  const exitStart = durationInFrames - 22;

  // Line extends first
  const lineProgress = spring({
    fps,
    frame: Math.max(0, frame - enterDelay),
    config: { damping: 22, stiffness: 140, mass: 0.6 },
    durationInFrames: 16,
  });
  const lineWidth = interpolate(lineProgress, [0, 1], [0, 100], {
    extrapolateRight: "clamp",
  });

  // Panel slides in after line — zero-overshoot settle (motion token)
  const panelProgress = spring({
    fps,
    frame: Math.max(0, frame - enterDelay - 6),
    config: SPRINGS.settle,
    durationInFrames: 20,
  });
  const panelX = interpolate(panelProgress, [0, 1], [-120, 0]);
  const panelOpacity = interpolate(panelProgress, [0, 1], [0, 1]);

  // Subtitle fades in with extra delay
  const subProgress = spring({
    fps,
    frame: Math.max(0, frame - enterDelay - 14),
    config: { damping: 20, stiffness: 90 },
    durationInFrames: 15,
  });
  const subOpacity = interpolate(subProgress, [0, 1], [0, 1]);
  const subY = interpolate(subProgress, [0, 1], [12, 0]);

  // ── Exit animation ─────────────────────────────────────────────────────
  const exitProgress = interpolate(
    frame,
    [exitStart, exitStart + 15],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      // Same accelerate-out curve as the cut engine — exits match the edit.
      easing: EASE.swiftIn,
    }
  );
  const exitX = interpolate(exitProgress, [0, 1], [0, -140]);
  const exitOpacity = interpolate(exitProgress, [0, 1], [1, 0]);

  // ── Combined transforms ────────────────────────────────────────────────
  const totalX = panelX + exitX;
  const totalOpacity = panelOpacity * exitOpacity;

  if (variant === "minimal") {
    return (
      <div
        style={{
          position: "absolute",
          bottom: "16%",
          left: "7%",
          zIndex: 30,
          opacity: totalOpacity,
          transform: `translateX(${totalX}px)`,
        }}
      >
        <div
          style={{
            fontSize: "36px",
            fontWeight: titleWeight,
            color: "#ffffff",
            fontFamily,
            letterSpacing: "1px",
            textShadow: `0 2px 20px rgba(0,0,0,0.8), 0 0 10px ${accentColor}40`,
          }}
        >
          {title}
        </div>
        {subtitle && (
          <div
            style={{
              fontSize: "28px",
              color: "rgba(255,255,255,0.7)",
              fontFamily,
              marginTop: "6px",
              opacity: subOpacity,
              transform: `translateY(${subY}px)`,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    );
  }

  if (variant === "news-ticker") {
    return (
      <div
        style={{
          position: "absolute",
          bottom: "12%",
          left: 0,
          right: 0,
          zIndex: 30,
          opacity: totalOpacity,
        }}
      >
        {/* Full-width accent line */}
        <div
          style={{
            width: `${lineWidth}%`,
            height: "3px",
            background: `linear-gradient(90deg, ${accentColor}, ${secondaryColor}80, transparent)`,
            marginBottom: "4px",
            boxShadow: `0 0 12px ${accentColor}50`,
          }}
        />
        {/* Ticker bar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "16px",
            padding: "14px 28px",
            background: "rgba(0,0,0,0.75)",
            backdropFilter: "blur(16px)",
            transform: `translateX(${totalX}px)`,
          }}
        >
          <div
            style={{
              width: "4px",
              height: "36px",
              backgroundColor: accentColor,
              borderRadius: "2px",
              flexShrink: 0,
              boxShadow: `0 0 8px ${accentColor}80`,
            }}
          />
          <div>
            <div
              style={{
                fontSize: "30px",
                fontWeight: titleWeight,
                color: "#fff",
                fontFamily,
                letterSpacing: "0.5px",
                textTransform: "uppercase",
              }}
            >
              {title}
            </div>
            {subtitle && (
              <div
                style={{
                  fontSize: "28px",
                  color: accentColor,
                  fontFamily,
                  marginTop: "4px",
                  opacity: subOpacity,
                  transform: `translateY(${subY}px)`,
                  letterSpacing: "2px",
                  textTransform: "uppercase",
                }}
              >
                {subtitle}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  // ── Default: accent-bar ────────────────────────────────────────────────
  return (
    <div
      style={{
        position: "absolute",
        bottom: "18%",
        left: "6%",
        zIndex: 30,
        maxWidth: "88%",
      }}
    >
      {/* Animated accent line */}
      <div
        style={{
          width: `${lineWidth}%`,
          maxWidth: "280px",
          height: "3px",
          background: `linear-gradient(90deg, ${accentColor}, ${secondaryColor ?? accentColor}80)`,
          marginBottom: "12px",
          boxShadow: `0 0 14px ${accentColor}60`,
          borderRadius: "2px",
          opacity: exitOpacity,
        }}
      />
      {/* Glassmorphic panel */}
      <div
        style={{
          opacity: totalOpacity,
          transform: `translateX(${totalX}px)`,
          padding: "18px 28px",
          background: "rgba(0,0,0,0.5)",
          backdropFilter: "blur(20px)",
          borderRadius: "14px",
          border: `1px solid ${accentColor}25`,
          boxShadow: `0 8px 32px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)`,
        }}
      >
        <div
          style={{
            fontSize: "34px",
            fontWeight: titleWeight,
            color: "#ffffff",
            fontFamily,
            letterSpacing: "1px",
            lineHeight: 1.2,
          }}
        >
          {title}
        </div>
        {subtitle && (
          <div
            style={{
              fontSize: "28px",
              color: accentColor,
              fontFamily,
              marginTop: "8px",
              opacity: subOpacity,
              transform: `translateY(${subY}px)`,
              letterSpacing: "1.5px",
              textTransform: "uppercase",
              fontWeight: 600,
            }}
          >
            {subtitle}
          </div>
        )}
      </div>
    </div>
  );
};

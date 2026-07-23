import React from "react";
import { useCurrentFrame, interpolate, spring, useVideoConfig, Easing } from "remotion";

interface SceneImpactFrameProps {
  /** Primary accent color for the flash/wipe */
  primaryColor: string;
  /** Secondary accent color */
  secondaryColor: string;
  /** Total frames in this scene */
  durationInFrames: number;
  /** Current scene index (0-based) */
  sceneIndex: number;
  /** Total number of scenes */
  totalScenes: number;
  /** Per-video seed so accent placement varies between videos */
  seed?: number;
  /** Look-driven: whether to show the top progress bar */
  showProgressBar?: boolean;
  /** Look-driven: whether to show the "02 / 05" scene counter badge */
  showSceneCounter?: boolean;
}

/**
 * SceneImpactFrame — fires on the first ~8 frames of every scene entry.
 *
 * Renders:
 * 1. A color-burst flash that fades out quickly
 * 2. An accent line that sweeps across the screen
 * 3. A thin top progress bar showing video progress
 * 4. A scene counter badge ("02 / 05") in the top-right corner
 */
export const SceneImpactFrame: React.FC<SceneImpactFrameProps> = ({
  primaryColor,
  secondaryColor,
  durationInFrames,
  sceneIndex,
  totalScenes,
  seed = 0,
  showProgressBar = true,
  showSceneCounter = true,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  // Mix the per-video seed with the scene index for placement variety
  const placeSeed = ((seed >>> 0) + sceneIndex * 13) >>> 0;

  // ── 1. Color-burst flash (frames 0-10) ─────────────────────────────────
  // Full-strength flash only on the first scene; later scenes stay subtle
  // so back-to-back scene entries don't strobe.
  const flashPeak = sceneIndex === 0 ? 0.3 : 0.15;
  const flashOpacity = interpolate(frame, [0, 2, 10], [flashPeak, flashPeak * 0.6, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // ── 2. Accent sweep line ───────────────────────────────────────────────
  const sweepProgress = spring({
    fps,
    frame,
    config: { damping: 25, stiffness: 150, mass: 0.5 },
    durationInFrames: 18,
  });
  const sweepX = interpolate(sweepProgress, [0, 1], [-10, 110]);
  const sweepOpacity = interpolate(frame, [0, 4, 14, 20], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // ── 3. Top progress bar ────────────────────────────────────────────────
  // Shows cumulative progress across the whole video
  const progressFraction = (sceneIndex + 1) / totalScenes;
  const barEntrance = spring({
    fps,
    frame: Math.max(0, frame - 5),
    config: { damping: 20, stiffness: 100 },
    durationInFrames: 20,
  });
  // Only animate the newly-earned segment; the bar is persistent UI, so it
  // must not re-grow from zero (or fade out) on every scene entry.
  const barWidth = interpolate(
    barEntrance,
    [0, 1],
    [(sceneIndex / totalScenes) * 100, progressFraction * 100]
  );
  const barOpacity =
    sceneIndex === 0
      ? interpolate(frame, [0, 8], [0, 0.85], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 0.85;

  // ── 4. Scene counter badge ─────────────────────────────────────────────
  const badgeEntrance = spring({
    fps,
    frame: Math.max(0, frame - 8),
    config: { damping: 20, stiffness: 150, mass: 0.7 },
    durationInFrames: 18,
  });
  const badgeScale = interpolate(badgeEntrance, [0, 1], [0.8, 1]);
  const badgeOpacity = interpolate(
    frame,
    [6, 16, durationInFrames - 15, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const displayIndex = String(sceneIndex + 1).padStart(2, "0");
  const displayTotal = String(totalScenes).padStart(2, "0");

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        zIndex: 50,
      }}
    >
      {/* Color burst flash */}
      {flashOpacity > 0.01 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: `radial-gradient(ellipse at 50% 50%, ${primaryColor}90, ${secondaryColor}30, transparent 70%)`,
            opacity: flashOpacity,
          }}
        />
      )}

      {/* Accent sweep line */}
      {sweepOpacity > 0.01 && (
        <div
          style={{
            position: "absolute",
            top: `${30 + (placeSeed % 5) * 9}%`,
            left: `${sweepX}%`,
            width: "120px",
            height: `${2 + (placeSeed % 3)}px`,
            background: `linear-gradient(90deg, transparent, ${primaryColor}, ${secondaryColor}, transparent)`,
            opacity: sweepOpacity,
            boxShadow: `0 0 20px ${primaryColor}80, 0 0 40px ${primaryColor}40`,
            transform: "translateX(-50%)",
          }}
        />
      )}

      {/* Top progress bar */}
      {showProgressBar && (
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: "4px",
          backgroundColor: "rgba(255,255,255,0.08)",
          opacity: barOpacity,
        }}
      >
        <div
          style={{
            width: `${barWidth}%`,
            height: "100%",
            background: `linear-gradient(90deg, ${primaryColor}, ${secondaryColor})`,
            boxShadow: `0 0 12px ${primaryColor}60`,
            borderRadius: "0 2px 2px 0",
          }}
        />
      </div>
      )}

      {/* Scene counter badge */}
      {showSceneCounter && (
      <div
        style={{
          position: "absolute",
          // Keep below the ~150px top zone that platform UI (search bar,
          // status icons) covers on Reels/Shorts/TikTok.
          top: "160px",
          right: "60px",
          opacity: badgeOpacity,
          transform: `scale(${badgeScale})`,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            gap: "3px",
            padding: "8px 14px",
            backgroundColor: "rgba(0,0,0,0.55)",
            backdropFilter: "blur(12px)",
            borderRadius: "10px",
            border: `1px solid ${primaryColor}30`,
          }}
        >
          <span
            style={{
              fontSize: "28px",
              fontWeight: 800,
              color: primaryColor,
              fontFamily: "monospace",
              fontVariantNumeric: "tabular-nums",
              letterSpacing: "1px",
            }}
          >
            {displayIndex}
          </span>
          <span
            style={{
              fontSize: "18px",
              color: "rgba(255,255,255,0.4)",
              fontFamily: "monospace",
            }}
          >
            / {displayTotal}
          </span>
        </div>
      </div>
      )}
    </div>
  );
};

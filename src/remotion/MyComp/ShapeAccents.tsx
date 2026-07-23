import React from "react";
import { useCurrentFrame, interpolate, useVideoConfig, Easing } from "remotion";

interface ShapeAccentsProps {
  primaryColor: string;
  secondaryColor: string;
  /** Scene duration for timing */
  durationInFrames: number;
  /** Visual intensity: "subtle" shows fewer elements */
  intensity?: "subtle" | "normal" | "high";
  /** Index of the scene for deterministic random seeding */
  sceneIndex?: number;
  /** Per-video seed so shape motion differs between videos, not just per scene */
  videoSeed?: number;
  /** Look-driven toggles — which decorative layers this video shows */
  showRings?: boolean;
  showBrackets?: boolean;
  showFloating?: boolean;
}

/**
 * ShapeAccents — geometric motion graphics layer.
 *
 * Renders rotating rings, pulsing corner brackets, and drifting geometric
 * shapes behind/above text. All math-driven, deterministic, render-safe.
 */
export const ShapeAccents: React.FC<ShapeAccentsProps> = ({
  primaryColor,
  secondaryColor,
  durationInFrames,
  intensity = "normal",
  sceneIndex = 0,
  videoSeed = 0,
  showRings = true,
  showBrackets = true,
  showFloating = true,
}) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();

  // Entrance fade
  const entranceOpacity = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const exitOpacity = interpolate(
    frame,
    [durationInFrames - 12, durationInFrames],
    [1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.in(Easing.cubic),
    }
  );
  const opacity = entranceOpacity * exitOpacity;

  // ── 1. Rotating concentric rings ───────────────────────────────────────
  const ringRotation1 = (frame * 0.8) % 360;
  const ringRotation2 = -(frame * 0.5) % 360;
  const ringPulse = Math.sin(frame * 0.06) * 0.08 + 1;

  // ── 2. Corner brackets ─────────────────────────────────────────────────
  // Single shared phase so size and opacity breathe together.
  const t = Math.sin(frame * 0.05);
  const bracketSize = 33 + t * 5;
  const bracketOpacity = 0.5 + t * 0.15;

  // ── 3. Floating geometric shapes ───────────────────────────────────────
  const shapes = intensity === "subtle" ? 3 : intensity === "high" ? 7 : 5;

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        zIndex: 15,
        opacity,
      }}
    >
      {/* ── Rotating rings (offset per scene, away from centered text) ─ */}
      {showRings && (
      <div
        style={{
          position: "absolute",
          top: `${34 + ((sceneIndex * 13) % 20)}%`,
          left: `${sceneIndex % 2 === 0 ? 26 : 72}%`,
          transform: `translate(-50%, -50%) scale(${ringPulse})`,
        }}
      >
        {/* Outer ring */}
        <div
          style={{
            width: "320px",
            height: "320px",
            borderRadius: "50%",
            border: `1px solid ${primaryColor}18`,
            position: "absolute",
            top: "-160px",
            left: "-160px",
            transform: `rotate(${ringRotation1}deg)`,
          }}
        >
          {/* Accent arc — only a quarter of the circle glows */}
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              borderRadius: "50%",
              border: `2px solid transparent`,
              borderTopColor: `${primaryColor}50`,
              boxShadow: `0 0 12px ${primaryColor}20`,
            }}
          />
        </div>
        {/* Inner ring */}
        <div
          style={{
            width: "220px",
            height: "220px",
            borderRadius: "50%",
            border: `1px solid ${secondaryColor}15`,
            position: "absolute",
            top: "-110px",
            left: "-110px",
            transform: `rotate(${ringRotation2}deg)`,
          }}
        >
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              borderRadius: "50%",
              border: `2px solid transparent`,
              borderBottomColor: `${secondaryColor}40`,
            }}
          />
        </div>
        {/* Center dot */}
        <div
          style={{
            width: "6px",
            height: "6px",
            borderRadius: "50%",
            backgroundColor: primaryColor,
            position: "absolute",
            top: "-3px",
            left: "-3px",
            boxShadow: `0 0 10px ${primaryColor}60`,
            opacity: 0.6,
          }}
        />
      </div>
      )}

      {/* ── Corner brackets ─────────────────────────────────────────── */}
      {showBrackets && (
      <>
      {/* Top-left */}
      <div
        style={{
          position: "absolute",
          top: "32px",
          left: "32px",
          width: bracketSize,
          height: bracketSize,
          borderTop: `2px solid ${primaryColor}`,
          borderLeft: `2px solid ${primaryColor}`,
          borderRadius: "3px 0 0 0",
          opacity: bracketOpacity * opacity,
          boxShadow: `0 0 8px ${primaryColor}30`,
        }}
      />
      {/* Top-right */}
      <div
        style={{
          position: "absolute",
          top: "32px",
          right: "32px",
          width: bracketSize,
          height: bracketSize,
          borderTop: `2px solid ${primaryColor}`,
          borderRight: `2px solid ${primaryColor}`,
          borderRadius: "0 3px 0 0",
          opacity: bracketOpacity * opacity,
          boxShadow: `0 0 8px ${primaryColor}30`,
        }}
      />
      {/* Bottom-left */}
      <div
        style={{
          position: "absolute",
          bottom: "32px",
          left: "32px",
          width: bracketSize,
          height: bracketSize,
          borderBottom: `2px solid ${secondaryColor}`,
          borderLeft: `2px solid ${secondaryColor}`,
          borderRadius: "0 0 0 3px",
          opacity: bracketOpacity * opacity,
          boxShadow: `0 0 8px ${secondaryColor}30`,
        }}
      />
      {/* Bottom-right */}
      <div
        style={{
          position: "absolute",
          bottom: "32px",
          right: "32px",
          width: bracketSize,
          height: bracketSize,
          borderBottom: `2px solid ${secondaryColor}`,
          borderRight: `2px solid ${secondaryColor}`,
          borderRadius: "0 0 3px 0",
          opacity: bracketOpacity * opacity,
          boxShadow: `0 0 8px ${secondaryColor}30`,
        }}
      />
      </>
      )}

      {/* ── Floating geometric shapes ───────────────────────────────── */}
      {showFloating && Array.from({ length: shapes }).map((_, i) => {
        // Deterministic pseudo-random seed based on the per-video seed, scene
        // index and shape index — so each video's shape field is unique.
        const seed = (((videoSeed >>> 0) * 31 + sceneIndex * 37 + i * 43) >>> 0) % 100;
        
        // Randomize direction: clockwise or counterclockwise
        const direction = seed % 2 === 0 ? 1 : -1;
        
        // Randomize orbit speed
        const speed = (0.2 + (seed % 6) * 0.08) * direction;
        
        // Randomize initial angle offset
        const angleOffset = (seed * 17) % 360;
        
        const angle = (frame * speed + angleOffset) % 360;
        const radians = (angle * Math.PI) / 180;
        
        // Randomize orbit radius
        const orbitRadius = 100 + (seed % 7) * 35;
        
        const cx = 50 + Math.cos(radians) * (orbitRadius / (width / 100)) * 2;
        const cy = 50 + Math.sin(radians) * (orbitRadius / (height / 100)) * 2;
        
        // Randomize size slightly
        const size = 5 + (seed % 4) * 3;
        const shapeOpacity = Math.sin(frame * 0.04 + seed) * 0.25 + 0.35;
        const color = seed % 3 === 0 ? primaryColor : seed % 3 === 1 ? secondaryColor : "#ffffff";
        const rotation = frame * (0.8 + (seed % 5) * 0.2) * direction;

        // Alternate between different shapes
        const shapeType = seed % 3;

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: `${cx}%`,
              top: `${cy}%`,
              opacity: shapeOpacity * opacity,
              transform: `rotate(${rotation}deg)`,
            }}
          >
            {shapeType === 0 && (
              // Small diamond
              <div
                style={{
                  width: size,
                  height: size,
                  backgroundColor: color,
                  transform: "rotate(45deg)",
                  boxShadow: `0 0 ${size}px ${color}50`,
                }}
              />
            )}
            {shapeType === 1 && (
              // Small circle
              <div
                style={{
                  width: size,
                  height: size,
                  borderRadius: "50%",
                  border: `1.5px solid ${color}`,
                  boxShadow: `0 0 ${size}px ${color}30`,
                }}
              />
            )}
            {shapeType === 2 && (
              // Cross / plus
              <div style={{ position: "relative", width: size, height: size }}>
                <div
                  style={{
                    position: "absolute",
                    top: "50%",
                    left: 0,
                    width: "100%",
                    height: "1.5px",
                    backgroundColor: color,
                    transform: "translateY(-50%)",
                    boxShadow: `0 0 4px ${color}40`,
                  }}
                />
                <div
                  style={{
                    position: "absolute",
                    left: "50%",
                    top: 0,
                    width: "1.5px",
                    height: "100%",
                    backgroundColor: color,
                    transform: "translateX(-50%)",
                    boxShadow: `0 0 4px ${color}40`,
                  }}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";

type GradientOverlay = "none" | "top-to-bottom" | "radial-center" | "diagonal";

interface HudOverlayProps {
  primaryColor: string;
  secondaryColor: string;
  overlayType: "grid-hud" | "particles" | "clean" | "vhs-glitch" | "fantasy-sparks" | "aurora";
  gradientOverlay?: GradientOverlay;
}

/** Build CSS gradient string from type + colors */
const getGradientCSS = (
  type: GradientOverlay,
  primary: string,
  secondary: string
): string | null => {
  switch (type) {
    case "top-to-bottom":
      return `linear-gradient(180deg, ${primary}40 0%, transparent 40%, transparent 60%, ${secondary}40 100%)`;
    case "radial-center":
      return `radial-gradient(ellipse at center, ${primary}30 0%, transparent 50%, ${secondary}20 100%)`;
    case "diagonal":
      return `linear-gradient(135deg, ${primary}35 0%, transparent 50%, ${secondary}35 100%)`;
    case "none":
    default:
      return null;
  }
};

export const HudOverlay: React.FC<HudOverlayProps> = ({
  primaryColor = "#00f0ff",
  secondaryColor = "#ff007f",
  overlayType = "grid-hud",
  gradientOverlay = "none",
}) => {
  const frame = useCurrentFrame();
  const { height, fps } = useVideoConfig();

  const monospaceFont = "monospace";

  // Fade-in so overlays don't pop in fully formed at frame 0
  const fadeIn = interpolate(frame, [0, 10], [0, 1], {
    easing: Easing.out(Easing.quad),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Build gradient layer (rendered on top of all overlays)
  const gradientCSS = getGradientCSS(gradientOverlay, primaryColor, secondaryColor);
  const GradientLayer = gradientCSS ? (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: gradientCSS,
        pointerEvents: "none",
        zIndex: 1,
        opacity: fadeIn,
      }}
    />
  ) : null;

  // 1. GRID HUD OVERLAY (enhanced with crosshair + animated corner brackets)
  if (overlayType === "grid-hud") {
    const scanCycle = frame % 90;
    const scanLineY = interpolate(scanCycle, [0, 90], [0, height]);
    const scanLineOpacity = interpolate(scanCycle, [0, 10, 80, 90], [0, 0.6, 0.6, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const scanCycle2 = (frame + 45) % 120;
    const scanLineY2 = interpolate(scanCycle2, [0, 120], [height, 0]);
    const scanLineOpacity2 = interpolate(scanCycle2, [0, 10, 110, 120], [0, 0.3, 0.3, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });

    // Pulsing crosshair at center
    const crosshairPulse = Math.sin(frame * 0.08) * 0.3 + 0.7;
    const crosshairSize = 20 + Math.sin(frame * 0.05) * 6;

    // Corner bracket animation
    const bracketPulse = Math.sin(frame * 0.04) * 4 + 36;

    return (
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, pointerEvents: "none", fontFamily: monospaceFont, color: primaryColor, fontSize: "10px", opacity: fadeIn }}>
        {/* Diagonal grid lines */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundImage: `
              linear-gradient(${primaryColor}0A 1px, transparent 1px),
              linear-gradient(90deg, ${primaryColor}0A 1px, transparent 1px)
            `,
            backgroundSize: "40px 40px",
          }}
        />

        {/* Primary scanning laser line */}
        <div style={{ position: "absolute", top: scanLineY, left: 0, right: 0, height: "2px", backgroundColor: primaryColor, boxShadow: `0 0 10px ${primaryColor}, 0 0 20px ${primaryColor}`, opacity: scanLineOpacity }} />

        {/* Secondary scanning line (reverse direction, dimmer) */}
        <div style={{ position: "absolute", top: scanLineY2, left: 0, right: 0, height: "1px", backgroundColor: secondaryColor, boxShadow: `0 0 8px ${secondaryColor}`, opacity: scanLineOpacity2 }} />

        {/* Center crosshair */}
        <div
          style={{
            position: "absolute",
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            opacity: crosshairPulse * 0.4,
          }}
        >
          <div style={{ position: "absolute", width: `${crosshairSize}px`, height: "1px", backgroundColor: primaryColor, top: 0, left: `-${crosshairSize / 2}px`, boxShadow: `0 0 6px ${primaryColor}` }} />
          <div style={{ position: "absolute", width: "1px", height: `${crosshairSize}px`, backgroundColor: primaryColor, left: 0, top: `-${crosshairSize / 2}px`, boxShadow: `0 0 6px ${primaryColor}` }} />
          <div style={{ position: "absolute", width: "4px", height: "4px", borderRadius: "50%", backgroundColor: primaryColor, top: "-2px", left: "-2px", boxShadow: `0 0 8px ${primaryColor}` }} />
        </div>

        {/* HUD corner brackets */}
        {/* Top-left */}
        <div style={{ position: "absolute", top: "60px", left: "40px" }}>
          <div style={{ width: bracketPulse, height: "2px", backgroundColor: primaryColor, opacity: 0.5, boxShadow: `0 0 6px ${primaryColor}40` }} />
          <div style={{ width: "2px", height: bracketPulse, backgroundColor: primaryColor, opacity: 0.5, boxShadow: `0 0 6px ${primaryColor}40` }} />
        </div>
        {/* Top-right */}
        <div style={{ position: "absolute", top: "60px", right: "40px", display: "flex", flexDirection: "column", alignItems: "flex-end" }}>
          <div style={{ width: bracketPulse, height: "2px", backgroundColor: primaryColor, opacity: 0.5, boxShadow: `0 0 6px ${primaryColor}40` }} />
          <div style={{ width: "2px", height: bracketPulse, backgroundColor: primaryColor, opacity: 0.5, alignSelf: "flex-end", boxShadow: `0 0 6px ${primaryColor}40` }} />
        </div>
        {/* Bottom-left */}
        <div style={{ position: "absolute", bottom: "60px", left: "40px", display: "flex", flexDirection: "column-reverse" }}>
          <div style={{ width: bracketPulse, height: "2px", backgroundColor: secondaryColor, opacity: 0.4, boxShadow: `0 0 6px ${secondaryColor}40` }} />
          <div style={{ width: "2px", height: bracketPulse, backgroundColor: secondaryColor, opacity: 0.4, boxShadow: `0 0 6px ${secondaryColor}40` }} />
        </div>
        {/* Bottom-right */}
        <div style={{ position: "absolute", bottom: "60px", right: "40px", display: "flex", flexDirection: "column-reverse", alignItems: "flex-end" }}>
          <div style={{ width: bracketPulse, height: "2px", backgroundColor: secondaryColor, opacity: 0.4, boxShadow: `0 0 6px ${secondaryColor}40` }} />
          <div style={{ width: "2px", height: bracketPulse, backgroundColor: secondaryColor, opacity: 0.4, alignSelf: "flex-end", boxShadow: `0 0 6px ${secondaryColor}40` }} />
        </div>

        {/* Telemetry data readout */}
        <div style={{ position: "absolute", bottom: "70px", left: "50px", fontSize: "9px", opacity: 0.35, letterSpacing: "2px" }}>
          <div>SYS.OK — {String(Math.floor(frame / 30)).padStart(3, "0")}s</div>
        </div>

        {GradientLayer}
      </div>
    );
  }

  // 2. VHS GLITCH OVERLAY (enhanced with periodic tracking errors)
  if (overlayType === "vhs-glitch") {
    const flicker = Math.sin(frame * 0.5) * 0.02 + 0.98;
    const scanLineY = interpolate(frame % 150, [0, 150], [0, height]);

    // Periodic tracking error: every ~90 frames, a 3-frame horizontal displacement burst
    const trackingCycle = frame % 90;
    const isTrackingError = trackingCycle >= 0 && trackingCycle < 4;
    const trackingShift = isTrackingError ? ((frame * 7919 % 30) - 15) : 0;
    const trackingBarY = isTrackingError ? (30 + (frame * 131 % 40)) : -100;

    // Jitter noise line
    const noiseLine1Y = (frame * 37 % height);
    const noiseLine2Y = ((frame + 60) * 53 % height);

    return (
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, pointerEvents: "none", opacity: flicker * fadeIn }}>
        {/* CRT Scanlines */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundImage: "linear-gradient(rgba(0,0,0,0.2) 50%, rgba(255,255,255,0.03) 50%)",
            backgroundSize: "100% 4px",
          }}
        />
        {/* VHS Rolling Line */}
        <div
          style={{
            position: "absolute",
            top: scanLineY,
            left: 0,
            right: 0,
            height: "8px",
            background: `linear-gradient(transparent, ${primaryColor}20, transparent)`,
            borderTop: `1px solid ${primaryColor}40`,
            borderBottom: `1px solid ${primaryColor}40`,
          }}
        />

        {/* Tracking error burst — horizontal shift bar */}
        {isTrackingError && (
          <div
            style={{
              position: "absolute",
              top: `${trackingBarY}%`,
              left: 0,
              right: 0,
              height: "40px",
              transform: `translateX(${trackingShift}px)`,
              backgroundColor: "rgba(255,255,255,0.06)",
              borderTop: "1px solid rgba(255,255,255,0.15)",
              borderBottom: "1px solid rgba(255,255,255,0.15)",
            }}
          />
        )}

        {/* Static noise lines */}
        <div
          style={{
            position: "absolute",
            top: noiseLine1Y,
            left: 0,
            right: 0,
            height: "1px",
            backgroundColor: "rgba(255,255,255,0.08)",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: noiseLine2Y,
            left: 0,
            right: 0,
            height: "1px",
            backgroundColor: "rgba(255,255,255,0.05)",
          }}
        />

        {/* VHS Text Details */}
        <div style={{ position: "absolute", top: 50, left: 50, fontFamily: monospaceFont, color: "#fff", fontSize: "14px", textShadow: `2px 0 0 ${secondaryColor}, -2px 0 0 ${primaryColor}` }}>
          <div>PLAY ▶</div>
          <div style={{ fontSize: "10px", marginTop: "4px", opacity: 0.8 }}>
            {String(Math.floor(frame / (fps * 60))).padStart(2, "0")}:{String(Math.floor((frame / fps) % 60)).padStart(2, "0")}:{String(frame % fps).padStart(2, "0")}
          </div>
        </div>
        <div style={{ position: "absolute", top: 50, right: 50, fontFamily: monospaceFont, color: "#fff", fontSize: "12px" }}>
          <div>CH 04</div>
        </div>
        {/* REC indicator */}
        <div style={{ position: "absolute", top: 50, right: 120, display: "flex", alignItems: "center", gap: "6px" }}>
          <div style={{ width: "8px", height: "8px", borderRadius: "50%", backgroundColor: "#ff0000", opacity: frame % 40 < 25 ? 1 : 0.3, boxShadow: "0 0 6px #ff0000" }} />
          <div style={{ fontFamily: monospaceFont, color: "#fff", fontSize: "11px", opacity: 0.7 }}>REC</div>
        </div>

        {GradientLayer}
      </div>
    );
  }

  // 3. FANTASY SPARKS (enhanced with light ray beams)
  if (overlayType === "fantasy-sparks") {
    const sparkCount = 12;

    // Light rays from edges
    const rayOpacity = Math.sin(frame * 0.03) * 0.15 + 0.2;
    const rayAngle = frame * 0.2;

    return (
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, pointerEvents: "none", opacity: fadeIn }}>
        {/* Light ray beams */}
        <div
          style={{
            position: "absolute",
            top: "-20%",
            left: "30%",
            width: "40%",
            height: "140%",
            background: `linear-gradient(${rayAngle}deg, transparent 30%, ${primaryColor}08 45%, ${primaryColor}15 50%, ${primaryColor}08 55%, transparent 70%)`,
            opacity: rayOpacity,
            transform: `rotate(${Math.sin(frame * 0.01) * 5}deg)`,
          }}
        />
        <div
          style={{
            position: "absolute",
            top: "-20%",
            left: "50%",
            width: "35%",
            height: "140%",
            background: `linear-gradient(${-rayAngle * 0.7}deg, transparent 30%, ${secondaryColor}06 45%, ${secondaryColor}12 50%, ${secondaryColor}06 55%, transparent 70%)`,
            opacity: rayOpacity * 0.7,
            transform: `rotate(${Math.cos(frame * 0.008) * 8}deg)`,
          }}
        />

        {/* Sparkles */}
        {Array.from({ length: sparkCount }).map((_, i) => {
          const offsetDir = i % 2 === 0 ? 1 : -1;
          const driftX = Math.sin((frame + i * 40) * 0.03) * 60 * offsetDir;
          const driftY = Math.cos((frame + i * 25) * 0.02) * 80;

          const leftPercent = 10 + (i * 8) + driftX / 10;
          const topPercent = 15 + ((i * 13) % 70) + driftY / 10;
          const sparkSize = 3 + (i % 4) * 3;
          const sparkColor = i % 3 === 0 ? primaryColor : i % 3 === 1 ? secondaryColor : "#ffffff";
          const glow = Math.sin((frame + i * 15) * 0.1) * 0.4 + 0.6;

          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: `${leftPercent}%`,
                top: `${topPercent}%`,
                width: sparkSize,
                height: sparkSize,
                borderRadius: "50%",
                backgroundColor: sparkColor,
                boxShadow: `0 0 ${sparkSize * 2}px ${sparkColor}, 0 0 ${sparkSize * 4}px ${sparkColor}60`,
                opacity: glow * 0.7,
              }}
            />
          );
        })}
        {GradientLayer}
      </div>
    );
  }

  // 4. PARTICLES (enhanced: more particles, varied sizes, glow trails)
  if (overlayType === "particles") {
    const dustCount = 18;
    return (
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, pointerEvents: "none", opacity: fadeIn }}>
        {Array.from({ length: dustCount }).map((_, i) => {
          const speed = 1.2 + (i % 4) * 0.4;
          const initialY = 105 - ((frame * speed + i * 35) % 130);
          const driftX = Math.sin((frame + i * 50) * 0.02) * 40;
          const leftPercent = 5 + (i * 5.5);
          const size = 2 + (i % 4) * 2;
          const opacity = Math.sin(frame * 0.05 + i) * 0.25 + 0.45;
          const color = i % 3 === 0 ? secondaryColor : primaryColor;

          return (
            <React.Fragment key={i}>
              {/* Main particle */}
              <div
                style={{
                  position: "absolute",
                  left: `calc(${leftPercent}% + ${driftX}px)`,
                  top: `${initialY}%`,
                  width: size,
                  height: size,
                  borderRadius: "50%",
                  backgroundColor: color,
                  boxShadow: `0 0 ${size + 2}px ${color}60`,
                  opacity: opacity * 0.6,
                }}
              />
              {/* Glow trail (slightly below, dimmer) */}
              <div
                style={{
                  position: "absolute",
                  left: `calc(${leftPercent}% + ${driftX * 0.8}px)`,
                  top: `${initialY + 2}%`,
                  width: size * 0.6,
                  height: size * 3,
                  borderRadius: "50%",
                  backgroundColor: color,
                  opacity: opacity * 0.15,
                  filter: `blur(${size}px)`,
                }}
              />
            </React.Fragment>
          );
        })}
        {GradientLayer}
      </div>
    );
  }

  // 5. AURORA (flowing light-wave curtains + drifting glow blobs)
  if (overlayType === "aurora") {
    const drift1 = Math.sin(frame * 0.012) * 12;
    const drift2 = Math.cos(frame * 0.009) * 16;
    const sway = Math.sin(frame * 0.02) * 8;
    const blobCount = 4;

    return (
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0, pointerEvents: "none", overflow: "hidden", opacity: fadeIn }}>
        {/* Aurora curtain 1 */}
        <div
          style={{
            position: "absolute",
            top: `${-15 + drift1}%`,
            left: "-20%",
            width: "140%",
            height: "80%",
            background: `linear-gradient(${115 + sway}deg, transparent 20%, ${primaryColor}22 42%, ${primaryColor}3a 50%, ${secondaryColor}22 60%, transparent 82%)`,
            filter: "blur(40px)",
            transform: `rotate(${sway * 0.4}deg)`,
            opacity: 0.7,
          }}
        />
        {/* Aurora curtain 2 (opposite drift, secondary tint) */}
        <div
          style={{
            position: "absolute",
            bottom: `${-15 + drift2}%`,
            left: "-20%",
            width: "140%",
            height: "75%",
            background: `linear-gradient(${65 - sway}deg, transparent 22%, ${secondaryColor}20 45%, ${secondaryColor}33 52%, ${primaryColor}20 62%, transparent 80%)`,
            filter: "blur(46px)",
            transform: `rotate(${-sway * 0.4}deg)`,
            opacity: 0.6,
          }}
        />
        {/* Drifting glow blobs */}
        {Array.from({ length: blobCount }).map((_, i) => {
          const speed = 0.006 + i * 0.004;
          const x = 20 + i * 22 + Math.sin(frame * speed + i) * 12;
          const y = 25 + ((i * 29) % 55) + Math.cos(frame * speed * 1.3 + i) * 14;
          const size = 180 + (i % 3) * 90;
          const color = i % 2 === 0 ? primaryColor : secondaryColor;
          const glow = Math.sin(frame * 0.03 + i * 1.7) * 0.1 + 0.22;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: `${x}%`,
                top: `${y}%`,
                width: size,
                height: size,
                borderRadius: "50%",
                background: `radial-gradient(circle, ${color}55 0%, ${color}18 40%, transparent 70%)`,
                filter: "blur(30px)",
                opacity: glow,
                transform: "translate(-50%, -50%)",
              }}
            />
          );
        })}
        {GradientLayer}
      </div>
    );
  }

  // 6. CLEAN (No overlays — but still render gradient if present)
  return GradientLayer ?? null;
};

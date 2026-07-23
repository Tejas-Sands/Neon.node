import React from "react";
import { useCurrentFrame, interpolate, Easing } from "remotion";
import { loadFont as loadShareTech } from "@remotion/google-fonts/ShareTechMono";
import { loadFont as loadOrbitron } from "@remotion/google-fonts/Orbitron";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { loadFont as loadPlayfair } from "@remotion/google-fonts/PlayfairDisplay";

// Load all fonts so they are available in memory
const fontShareTech = loadShareTech("normal", { subsets: ["latin"], weights: ["400"] });
const fontOrbitron = loadOrbitron("normal", { subsets: ["latin"], weights: ["700"] });
const fontInter = loadInter("normal", { subsets: ["latin"], weights: ["700"] });
const fontPlayfair = loadPlayfair("normal", { subsets: ["latin"], weights: ["700"] });

interface GlitchTextProps {
  text: string;
  glowColor?: string;
  fontFamilyName?: "Share Tech Mono" | "Orbitron" | "Inter" | "Playfair Display" | "Courier New";
  overlayType?: "grid-hud" | "particles" | "clean" | "vhs-glitch" | "fantasy-sparks";
}

const GLITCH_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?";

export const GlitchText: React.FC<GlitchTextProps> = ({
  text,
  glowColor = "#00f0ff",
  fontFamilyName = "Share Tech Mono",
  overlayType = "grid-hud",
}) => {
  const frame = useCurrentFrame();

  // Map font family name to loaded font string
  const getFontFamily = () => {
    switch (fontFamilyName) {
      case "Share Tech Mono":
        return fontShareTech.fontFamily;
      case "Orbitron":
        return fontOrbitron.fontFamily;
      case "Inter":
        return fontInter.fontFamily;
      case "Playfair Display":
        return fontPlayfair.fontFamily;
      case "Courier New":
        return "Courier New, monospace";
      default:
        return fontInter.fontFamily;
    }
  };

  // Text decryption duration (20 frames)
  const resolvedCount = Math.floor(
    interpolate(frame, [0, 20], [0, text.length], {
      easing: Easing.out(Easing.cubic),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    })
  );

  // Deterministic per-frame glitch text: pure function of frame, no state/effects
  const getDisplayedText = () => {
    // In clean mode, we skip the glitch animation for a smooth fade-in instead
    if (overlayType === "clean") {
      return text;
    }

    let result = "";
    for (let i = 0; i < text.length; i++) {
      if (i < resolvedCount) {
        result += text[i];
      } else if (text[i] === " ") {
        result += " ";
      } else {
        const seed = Math.floor(frame / 2) * 100 + i;
        const randIndex =
          Math.abs(Math.floor(Math.sin(seed * 9301 + 49297) * 233280)) %
          GLITCH_CHARS.length;
        result += GLITCH_CHARS[randIndex];
      }
    }
    return result;
  };
  const displayedText = getDisplayedText();

  const pulse = Math.sin(frame * 0.1) * 2 + 8;
  const isRetro = overlayType === "vhs-glitch";
  const isClean = overlayType === "clean";

  // Clean mode: smooth fade-in with a gentle upward settle
  const cleanOpacity = interpolate(frame, [0, 12], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const cleanTranslateY = interpolate(frame, [0, 12], [16, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Customize layout borders based on theme style
  const getStyle = (): React.CSSProperties => {
    const common: React.CSSProperties = {
      fontFamily: getFontFamily(),
      fontSize: isRetro ? 36 : 40,
      color: "#ffffff",
      letterSpacing: isClean ? "2px" : "4px",
      textAlign: "center",
      textTransform: "uppercase",
      fontWeight: "bold",
      padding: "12px 24px",
      maxWidth: "90%",
      overflowWrap: "normal",
      wordBreak: "keep-all",
    };

    if (isClean) {
      return {
        ...common,
        color: "#ffffff",
        backgroundColor: "rgba(0, 0, 0, 0.6)",
        borderRadius: "12px",
        border: "1px solid rgba(255, 255, 255, 0.15)",
        backdropFilter: "blur(8px)",
        boxShadow: "0 10px 30px rgba(0, 0, 0, 0.5)",
        opacity: cleanOpacity,
        transform: `translateY(${cleanTranslateY}px)`,
      };
    }

    if (isRetro) {
      // VHS style chromatic aberration shift
      return {
        ...common,
        backgroundColor: "rgba(0, 0, 0, 0.8)",
        border: "3px solid #ffffff",
        textShadow: `3px 0 0 ${glowColor}, -3px 0 0 #ff007f`,
        boxShadow: "5px 5px 0px rgba(0,0,0,1)",
      };
    }

    // Default glowing neon HUD border style
    return {
      ...common,
      textShadow: `0 0 ${pulse}px ${glowColor}, 0 0 ${pulse + 4}px ${glowColor}`,
      backgroundColor: "rgba(0, 0, 0, 0.55)",
      borderLeft: `4px solid ${glowColor}`,
      borderRight: `4px solid ${glowColor}`,
      backdropFilter: "blur(6px)",
      boxShadow: `0 0 20px ${glowColor}15`,
    };
  };

  return <div style={getStyle()}>{displayedText}</div>;
};

import React from "react";
import {interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {BRAND} from "./brand";
import type {SceneEnergy} from "./energy";

/** One opening ribbon, fully readable on the cover. The impact underneath
 * belongs to HookPunch; this adds no flash, particles, sound or intro delay. */
export const BreakingNews: React.FC<{durationInFrames: number; energy: SceneEnergy}> = ({durationInFrames, energy}) => {
  const frame = useCurrentFrame();
  const {width, height, fps} = useVideoConfig();
  const unit = width / 1080;
  const still = energy.still;
  const out = Math.max(12, Math.min(durationInFrames - 8, Math.round(fps * 2.8)));
  // Let the completed cover and HookPunch land before the ribbon's one hit.
  const start = Math.max(energy.landEnd, energy.kineticStart);
  const end = Math.max(start + 1, Math.min(start + 20, out - 10));
  const progress = interpolate(frame, [start, end], [0, 1], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });
  const hit = still || start >= out - 10 ? 0 : Math.sin(Math.PI * progress);
  const sweep = still || start >= out - 10 ? -0.3 : -0.3 + progress * 1.6;
  const opacity = still ? 1 : interpolate(frame, [out - 10, out], [1, 0], {
    extrapolateLeft: "clamp", extrapolateRight: "clamp",
  });

  return <div data-news-alert="breaking" style={{position: "absolute", left: width * 0.08,
    top: height * 0.125, zIndex: 35, pointerEvents: "none", opacity,
    transform: `translateX(${(1 - opacity) * -32 * unit}px) scale(${1 + hit * 0.025})`,
    transformOrigin: "left center", width: width * 0.78, maxWidth: 740 * unit}}>
    <div style={{position: "relative", overflow: "hidden", display: "flex", alignItems: "center",
      gap: 20 * unit, padding: `${20 * unit}px ${28 * unit}px`,
      background: "#c7142b", color: "#fff", borderLeft: `${8 * unit}px solid #fff`,
      clipPath: "polygon(0 0, 100% 0, 96% 100%, 0 100%)",
      fontFamily: BRAND.family, fontWeight: BRAND.strongWeight,
      fontSize: 43 * unit, lineHeight: 1, letterSpacing: "-0.02em", whiteSpace: "nowrap",
      boxShadow: `0 ${12 * unit}px ${28 * unit}px rgba(0,0,0,0.3)`}}>
      <span style={{position: "relative", zIndex: 1}}>BREAKING NEWS</span>
      <div style={{position: "absolute", top: 0, bottom: 0, left: `${sweep * 100}%`,
        width: "18%", transform: "skewX(-20deg)",
        background: "linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent)"}} />
    </div>
    <div style={{height: 4 * unit, width: `${(1 - hit * 0.12) * 94}%`,
      marginTop: 8 * unit, background: "#fff", opacity: 0.8}} />
  </div>;
};

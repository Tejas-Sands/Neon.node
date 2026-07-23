import React from "react";
import { AbsoluteFill, Easing, interpolateColors, useVideoConfig } from "remotion";

const RadialGradient: React.FC<{
  radius: number;
  color: string;
}> = ({ radius, color }) => {
  const height = radius * 2;
  const width = radius * 2;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div
        style={{
          height,
          width,
          backgroundColor: color,
        }}
        className="rounded-[50%] absolute shadow-[0px_0px_100px_rgba(0,0,0,0.05)]"
      ></div>
    </AbsoluteFill>
  );
};

export const Rings: React.FC<{
  outProgress: number;
}> = ({ outProgress }) => {
  // Ease the raw linear progress so the growth accelerates in, and clamp the
  // denominator so the final frame never divides by zero.
  const easedOut = Easing.in(Easing.cubic)(Math.min(1, Math.max(0, outProgress)));
  const scale = 1 / Math.max(0.05, 1 - easedOut);
  const { height } = useVideoConfig();

  return (
    <AbsoluteFill
      style={{
        transform: `scale(${scale})`,
      }}
    >
      {new Array(5)
        .fill(true)
        .map((_, i) => {
          return (
            <RadialGradient
              key={i}
              radius={height * 0.3 * i}
              color={interpolateColors(i, [0, 4], ["#ffffff", "#e6e6e6"])}
            />
          );
        })
        .reverse()}
    </AbsoluteFill>
  );
};

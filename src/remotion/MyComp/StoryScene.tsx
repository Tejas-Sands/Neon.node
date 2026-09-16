import React from "react";
import {AbsoluteFill, Img, useCurrentFrame, useVideoConfig} from "remotion";
import {AnimatedText, FONT_METRICS, getFontFamily} from "./AnimatedText";
import {BRAND} from "./brand";
import {clampAccentLuminance, withAlpha, type Palette} from "./looks";
import {fitStackScale, textWidthFor} from "./fitStack";
import type {SceneEnergy} from "./energy";
import {fitStoryFont, storyProgress, type StoryBeat, type StoryScene as StoryCopy} from "./storyMotion";

type Font = React.ComponentProps<typeof AnimatedText>["fontFamilyName"];

/** Three house layouts, all driven by supplied copy. The mechanism is a
 * labelled schematic, never a fabricated benchmark or product screenshot.
 * No RNG, blur filters, per-letter wrapping or browser-time animation. */
export const StoryScene: React.FC<{
  scene: StoryCopy & {imageUrl?: string};
  beat: StoryBeat;
  energy: SceneEnergy;
  palette: Palette;
  accent: string;
  font: Font;
  subject?: string;
}> = ({scene, beat, energy, palette, accent, font = "Inter", subject}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const progress = storyProgress(frame, beat.revealFrame, energy.still);
  const hit = energy.still ? 0 : Math.sin(Math.min(1, Math.max(0, (frame - beat.revealFrame) / 18)) * Math.PI);
  const color = clampAccentLuminance(accent);
  const unit = Math.min(width / 1080, height / 1350);
  const left = width * 0.08;
  const column = width * 0.78; // clear the right-hand social icon rail
  const top = height * 0.20;
  const available = height * 0.45; // bottom <=65%; captions start around72%
  const isComparison = beat.kind === "comparison";
  const isCompression = beat.kind === "compression";
  const mainSize = (beat.kind === "metric" ? 148 : isComparison ? 62 : 92) * unit;
  const supporting = isComparison ? "" : [scene.secondaryText, scene.subtitle].filter(Boolean).join(" · ");
  const slots = [
    ...(scene.title ? [{text: scene.title, basePx: 30 * unit}] : []),
    {text: scene.text, basePx: mainSize},
    ...(supporting ? [{text: supporting, basePx: 32 * unit}] : []),
  ];
  const fit = fitStackScale({slots, fontScale: 1,
    availablePx: available - (isCompression ? 230 * unit : 0),
    widthPx: textWidthFor(column), lineHeight: FONT_METRICS[font].lineHeight,
    gapPx: 24 * unit, slotPaddingPx: 24, fixedPx: 8 * unit});
  const text = (value: string, size: number, tint = "#f8fafc") => (
    <AnimatedText text={value} fontFamilyName={font} fontSize={fitStoryFont(value, size * fit, textWidthFor(column))}
      overlayType="clean" animationMode="none" textCase="as-is"
      align="left" treatment="solid" finish="print" glowColor={tint} />
  );

  return (
    <AbsoluteFill data-story-kind={beat.kind} style={{background: palette.ink, overflow: "hidden"}}>
      {/* A restrained photographic plane supplies context for the typographic
          story. Data/mechanism scenes reserve the entire frame for the proof. */}
      {beat.kind === "statement" && scene.imageUrl && (
        <div style={{position: "absolute", top: "8%", right: "6%", width: "49%", height: "54%", overflow: "hidden", opacity: 0.28}}>
          <Img src={scene.imageUrl} style={{width: "100%", height: "100%", objectFit: "cover",
            transform: `scale(${1.04 + progress * 0.035})`}} />
          <AbsoluteFill style={{background: `linear-gradient(90deg, ${palette.ink}, transparent), linear-gradient(0deg, ${palette.ink}, transparent 75%)`}} />
        </div>
      )}
      <AbsoluteFill style={{background: `radial-gradient(ellipse at 90% 22%, ${withAlpha(accent, 0.12)}, transparent 55%)`}} />
      {/* Stable subject tab survives matching cuts at the same coordinates. */}
      <div style={{position: "absolute", left, top: "11%", display: "flex", alignItems: "center", gap: 14 * unit,
        fontFamily: BRAND.family, fontWeight: BRAND.chromeWeight, fontSize: 22 * unit,
        letterSpacing: "0.12em", color: "#f8fafc", background: palette.ink, padding: "10px 0"}}>
        <span style={{width: 10 * unit, height: 10 * unit, background: color, borderRadius: 2}} />
        {subject || (isCompression ? "INSIDE THE MECHANISM" : isComparison ? "SIDE BY SIDE" : beat.kind === "metric" ? "THE NUMBER" : "THE DETAIL")}
      </div>

      <div style={{position: "absolute", left, top, width: column, height: available,
        display: "flex", flexDirection: "column", justifyContent: "center", gap: 24 * unit}}>
        {scene.title && text(scene.title, 30 * unit, color)}
        {isComparison ? (
          <div style={{display: "flex", flexDirection: "column", gap: 20 * unit}}>
            {[{label: scene.leftLabel, value: scene.text},
              {label: scene.rightLabel, value: scene.secondaryText || scene.subtitle || ""}].map((side, i) => {
              const sideFit = fitStackScale({slots: [{text: side.value, basePx: 62 * unit}, ...(side.label ? [{text: side.label, basePx: 24 * unit}] : [])],
                widthPx: textWidthFor(column - 56 * unit), availablePx: available * 0.34,
                fontScale: 1, lineHeight: FONT_METRICS[font].lineHeight, gapPx: 10 * unit, slotPaddingPx: 24});
              return <div key={i} style={{position: "relative", padding: 22 * unit,
                border: `1px solid ${withAlpha(color, i === 1 ? 0.35 + progress * 0.35 : 0.25)}`,
                background: palette.ink, boxShadow: `8px 10px 0 ${withAlpha(accent, 0.08)}`,
                transform: `translateX(${i === 1 ? (1 - progress) * 16 * unit : 0}px)`}}>
                {side.label && <AnimatedText text={side.label} fontFamilyName={font}
                  fontSize={fitStoryFont(side.label, 24 * unit * sideFit, textWidthFor(column - 56 * unit))}
                  animationMode="none" textCase="as-is" align="left" finish="print" glowColor={color} />}
                <AnimatedText text={side.value} fontFamilyName={font}
                  fontSize={fitStoryFont(side.value, 62 * unit * sideFit, textWidthFor(column - 56 * unit))}
                  animationMode="none" textCase="as-is" align="left" finish="print" glowColor="#f8fafc" />
                {i === 1 && <div style={{position: "absolute", left: 0, top: 0, bottom: 0, width: 4 * unit, background: color,
                  transform: `scaleY(${0.15 + progress * 0.85})`, transformOrigin: "top"}} />}
              </div>;
            })}
          </div>
        ) : (
          <>
            <div style={{position: "relative", background: palette.ink,
              transform: `translateY(${-hit * 4 * unit}px) scale(${1 + hit * 0.018})`, transformOrigin: "left center"}}>
              {text(scene.text, mainSize)}
              <div style={{height: 4 * unit, width: "100%", background: withAlpha(color, 0.2)}}>
                <div style={{height: "100%", background: color, width: "100%", transform: `scaleX(${0.08 + progress * 0.92})`, transformOrigin: "left"}} />
              </div>
            </div>
            {isCompression && (
              <div style={{height: 230 * unit, flexShrink: 0}}>
                <svg viewBox="0 0 820 190" width="100%" height={190 * unit} aria-label="Compression schematic, not to scale">
                  <rect x="12" y="16" width="796" height="154" rx="14" fill={palette.ink} stroke={withAlpha(color, 0.3)} strokeWidth="2" />
                  {Array.from({length: 8}, (_, i) => {
                    const x = 34 + i * (94 - 45 * progress);
                    const w = 76 - 39 * progress;
                    return <g key={i}>
                      <rect x={x + 6} y="44" width={w} height="106" rx="7" fill={withAlpha(accent, 0.13)} />
                      <rect x={x} y="34" width={w} height="106" rx="7" fill={withAlpha(accent, 0.22)} stroke={color} strokeWidth="2" />
                    </g>;
                  })}
                </svg>
                <div style={{fontFamily: BRAND.family, fontWeight: BRAND.chromeWeight, fontSize: 19 * unit,
                  color: "#d5dae2", letterSpacing: "0.1em", paddingLeft: 12}}>COMPRESSION SCHEMATIC · NOT TO SCALE</div>
              </div>
            )}
            {supporting && text(supporting, 32 * unit, color)}
          </>
        )}
      </div>
      {/* Contact plane, not another moving effect. Every actual text surface
          is white/light-accent on opaque brand ink (independent of imagery). */}
      <div style={{position: "absolute", left, top: "68%", width: column, height: 1,
        background: withAlpha(color, 0.22)}} />
      <div style={{position: "absolute", left, top: "69%", fontFamily: getFontFamily(font),
        fontWeight: FONT_METRICS[font].bodyWeight, fontSize: 16 * unit, color: "#cbd5e1", letterSpacing: "0.14em"}}>
        NEON NODE
      </div>
    </AbsoluteFill>
  );
};

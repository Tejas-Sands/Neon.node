import React from "react";
import {AbsoluteFill, Img, useCurrentFrame, useVideoConfig} from "remotion";
import {FONT_METRICS, getFontFamily, type FontFamilyName} from "./AnimatedText";
import {BRAND, BRAND_MONO} from "./brand";
import {clampAccentLuminance, withAlpha, type Palette} from "./looks";
import {fitStackScale} from "./fitStack";
import type {SceneEnergy} from "./energy";
import {fitStoryFont, storyStage, type StoryBeat, type StoryScene as StoryCopy} from "./storyMotion";

/** Arrive, read, transform. Paper supplies its own contrast. Every position
 * is frame-derived, including the metric that travels across a matching cut. */
export const StoryScene: React.FC<{
  scene: StoryCopy & {imageUrl?: string};
  beat: StoryBeat;
  energy: SceneEnergy;
  palette: Palette;
  accent: string;
  subject?: string;
  incomingMetric?: string;
  outgoingMetric?: string;
}> = ({scene, beat, energy, palette, accent, subject, incomingMetric, outgoingMetric}) => {
  const frame = useCurrentFrame();
  const {width, height} = useVideoConfig();
  const unit = width / 1080;
  const {enter, reveal, dock} = storyStage(frame, scene.durationInFrames ?? 150, beat.revealFrame, energy);
  const color = clampAccentLuminance(accent);
  const paper = "#f4f1e9";
  const ink = "#14191f";
  const left = width * 0.08;
  const column = width * 0.78;
  const top = height * 0.21;
  const available = height * 0.44;
  const pad = 34 * unit;
  const inner = column - 2 * pad;
  const metric = beat.kind === "metric";
  const comparison = beat.kind === "comparison";
  const compression = beat.kind === "compression";
  const headlineFont: FontFamilyName = beat.kind === "statement" ? "Newsreader" : "Geist";
  const mainSize = (metric ? 232 : comparison ? 84 : 120) * unit;
  const supporting = comparison ? "" : [scene.secondaryText, scene.subtitle].filter(Boolean).join(" · ");
  const fit = fitStackScale({
    slots: [{text: scene.text, basePx: mainSize}, ...(supporting ? [{text: supporting, basePx: 36 * unit}] : [])],
    fontScale: 1, widthPx: inner, availablePx: available - 146 * unit - (compression ? 270 * unit : 0),
    lineHeight: FONT_METRICS[headlineFont].lineHeight, gapPx: 28 * unit,
  });
  const typeStyle = (font: FontFamilyName, size: number): React.CSSProperties => ({
    fontFamily: getFontFamily(font), fontWeight: FONT_METRICS[font].displayWeight,
    fontSize: size, lineHeight: FONT_METRICS[font].lineHeight,
    letterSpacing: `${FONT_METRICS[font].trackTitleEm}em`,
    overflowWrap: "normal", wordBreak: "keep-all", whiteSpace: "normal",
  });
  // Whole-block masks preserve normal word wrapping. Text finishes arriving
  // by landEnd, then holds until the voice-timed kinetic window.
  const arrival: React.CSSProperties = {
    clipPath: `inset(0 0 ${(1 - enter) * 100}% 0)`,
    transform: `translateY(${(1 - enter) * 46 * unit}px)`,
  };
  const labelStyle: React.CSSProperties = {
    fontFamily: BRAND_MONO.family, fontWeight: BRAND_MONO.weight,
    fontSize: 24 * unit, lineHeight: 1.3, letterSpacing: "0.05em",
    overflowWrap: "normal", wordBreak: "keep-all",
  };
  const metricSize = fitStoryFont(scene.text, mainSize * fit, inner);
  const dockSize = 28 * unit;
  const metricY = top + pad + 100 * unit;
  const chipY = height * 0.16;

  return <AbsoluteFill data-story-kind={beat.kind} style={{background: palette.ink, overflow: "hidden"}}>
    {beat.kind === "statement" && scene.imageUrl && <div style={{position: "absolute", top: "12%", right: "6%",
      width: "64%", height: "40%", overflow: "hidden", opacity: 0.8,
      clipPath: `inset(0 ${(1 - reveal) * 28}% 0 0)`}}>
      <Img src={scene.imageUrl} style={{width: "100%", height: "100%", objectFit: "cover",
        transform: `scale(${1.12 - reveal * 0.12})`}} />
    </div>}
    <div style={{position: "absolute", left, top: "10.5%", width: column, display: "flex",
      justifyContent: "space-between", alignItems: "center", color: paper,
      fontFamily: BRAND.family, fontWeight: BRAND.strongWeight, fontSize: 23 * unit, letterSpacing: "0.08em"}}>
      <span>NEON NODE</span><span style={{color}}>THE BUILDER BRIEF</span>
    </div>
    {incomingMetric && !outgoingMetric && <div style={{position: "absolute", left: left + pad, top: chipY,
      ...typeStyle("Geist", dockSize), color: paper, background: palette.ink, fontVariantNumeric: "tabular-nums"}}>{incomingMetric}</div>}

    <div style={{position: "absolute", left, top, width: column, height: available,
      background: compression ? "#17212a" : paper, color: compression ? paper : ink,
      boxShadow: `${16 * unit}px ${20 * unit}px 0 ${withAlpha(color, 0.12)}`}}>
      <div style={{position: "absolute", left: pad, top: pad, right: pad, ...labelStyle,
        fontSize: fitStoryFont(scene.title || subject || "THE DETAIL", 24 * unit, inner),
        color: compression ? color : ink}}>{scene.title || subject || "THE DETAIL"}</div>

      {comparison ? <div style={{position: "absolute", left: pad, right: pad, top: 110 * unit, bottom: pad,
        display: "flex", flexDirection: "column", gap: 22 * unit}}>
        {[{label: scene.leftLabel, value: scene.text}, {label: scene.rightLabel, value: scene.secondaryText || scene.subtitle || ""}].map((side, i) => {
          const sideFit = fitStackScale({slots: [{text: side.value, basePx: mainSize}, ...(side.label ? [{text: side.label, basePx: 26 * unit}] : [])],
            fontScale: 1, widthPx: inner - 48 * unit, availablePx: (available - 210 * unit) / 2,
            lineHeight: 1.08, gapPx: 16 * unit});
          return <div key={i} style={{flex: 1, padding: 24 * unit, minHeight: 0,
            background: i ? ink : "#e5e2da", color: i ? paper : ink,
            transform: i ? `translateX(${(1 - reveal) * 48 * unit}px)` : "none",
            borderLeft: i ? `${6 * unit}px solid ${color}` : `${6 * unit}px solid transparent`}}>
            {side.label && <div style={{...labelStyle, fontSize: fitStoryFont(side.label, 26 * unit, inner - 48 * unit), marginBottom: 16 * unit}}>{side.label}</div>}
            <div style={{...typeStyle("Geist", fitStoryFont(side.value, mainSize * sideFit, inner - 48 * unit)), ...arrival}}>{side.value}</div>
          </div>;
        })}
      </div> : <div style={{position: "absolute", left: pad, right: pad, top: 112 * unit, bottom: pad,
        display: "flex", flexDirection: "column", justifyContent: metric ? "flex-end" : "center", gap: 28 * unit}}>
        {!metric && <div style={{...typeStyle(headlineFont, fitStoryFont(scene.text, mainSize * fit, inner)), ...arrival}}>{scene.text}</div>}
        {compression && <div style={{height: 270 * unit, flexShrink: 0}}>
          <svg viewBox="0 0 820 225" width="100%" height={225 * unit} aria-label="Compression schematic, not to scale">
            <rect x="4" y="4" width="812" height="212" rx="12" fill="none" stroke={withAlpha(color, 0.3)} strokeWidth="2" />
            {Array.from({length: 8}, (_, i) => {
              const x = 25 + (i % 4) * 196;
              const y = 24 + Math.floor(i / 4) * 92;
              // Every source block survives. This is a labelled schematic,
              // not a numerical savings chart or invented benchmark.
              const tx = x + (252 + (i % 4) * 78 - x) * reveal;
              const ty = y + (47 + Math.floor(i / 4) * 64 - y) * reveal;
              return <g key={i} transform={`translate(${tx} ${ty})`}>
                <rect x="6" y="7" width={174 - reveal * 112} height={70 - reveal * 22} rx="5" fill={withAlpha(color, 0.15)} />
                <rect width={174 - reveal * 112} height={70 - reveal * 22} rx="5" fill={withAlpha(color, 0.32)} stroke={color} strokeWidth="2" />
              </g>;
            })}
          </svg>
          <div style={{...labelStyle, color: "#d5dae2", fontSize: 20 * unit}}>COMPRESSION SCHEMATIC · NOT TO SCALE</div>
        </div>}
        {supporting && <div style={{...typeStyle("Geist", fitStoryFont(supporting, 36 * unit * fit, inner)),
          fontWeight: FONT_METRICS.Geist.bodyWeight, lineHeight: 1.3}}>{supporting}</div>}
      </div>}
      {!compression && <div style={{position: "absolute", left: 0, right: 0, bottom: 0, height: 6 * unit,
        background: ink, transform: `scaleX(${0.06 + reveal * 0.94})`, transformOrigin: "left"}} />}
    </div>

    {metric && <div style={{position: "absolute", left: left + pad,
      top: metricY + (outgoingMetric ? (chipY - metricY) * dock : 0),
      ...typeStyle("Geist", metricSize), fontVariantNumeric: "tabular-nums",
      color: outgoingMetric && dock > 0 ? paper : ink,
      background: outgoingMetric && dock > 0 ? palette.ink : "transparent",
      transformOrigin: "top left", maxWidth: inner, clipPath: arrival.clipPath,
      transform: `translateY(${(1 - enter) * 46 * unit}px) scale(${outgoingMetric ? 1 + (dockSize / metricSize - 1) * dock : 1 + Math.sin(reveal * Math.PI) * 0.10})`}}>
      {outgoingMetric || scene.text}
    </div>}
    <div style={{position: "absolute", left, top: "68%", width: column, height: 1, background: withAlpha(color, 0.25)}} />
    <div style={{position: "absolute", left, top: "69%", ...labelStyle, fontSize: 19 * unit, color: "#d5dae2"}}>
      TECHNOLOGY, EXPLAINED
    </div>
  </AbsoluteFill>;
};

// ============================================================================
// PrismLayers.tsx — Render components for the "Prism" look family
// ----------------------------------------------------------------------------
// The kaleidoscope / blend-layer / giant-type treatment selected by prism.ts.
// PrismMedia replaces ONLY the media block of BackgroundLayer (the base
// gradient, duotone/spotlight washes, vignette and bottom scrim around it are
// untouched, so text contrast is never diluted).
//
// EVERYTHING here is a pure function of the current frame. Only cheap CSS is
// used: transforms, clip-path insets, static gradient masks and screen/lighten
// blends — no canvas, no per-frame feTurbulence, no filter:blur (the
// PolishLayers perf rules). The twirl is a rotational smear (masked rotated
// copies), not a per-pixel displacement filter.
// ============================================================================

import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { tint, withAlpha, type Palette } from "./looks";
import type { PrismConfig, PrismMode } from "./prism";
import { FONT_METRICS, getFontFamily, pickEmphasisIndices } from "./AnimatedText";

// ---------------------------------------------------------------------------
// One copy of the scene media, replicating BackgroundLayer's exact styling
// contract (115% still under the camera transform; the hook clip at a fixed
// gentle zoom) so the untreated and treated paths photograph identically.
// ---------------------------------------------------------------------------
const MediaCopy: React.FC<{
  imageUrl: string;
  videoSrc?: string;
  cameraTransform: string;
  filter: string;
  opacity: number;
  /** Extra rotation appended to both media transforms (kaleido sweep). */
  srcRotation?: number;
  /** Skip the video element (smear/blend/inset copies stay image-only). */
  imageOnly?: boolean;
}> = ({ imageUrl, videoSrc, cameraTransform, filter, opacity, srcRotation = 0, imageOnly }) => {
  const rot = srcRotation ? ` rotate(${srcRotation.toFixed(3)}deg)` : "";
  return (
    <>
      <img
        src={imageUrl}
        style={{
          width: "115%",
          height: "115%",
          objectFit: "cover",
          transform: `${cameraTransform}${rot}`,
          filter,
          opacity,
        }}
        alt=""
      />
      {videoSrc && !imageOnly && (
        <OffthreadVideo
          muted
          src={videoSrc}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            transform: `scale(1.06)${rot}`,
            filter,
            opacity,
          }}
        />
      )}
    </>
  );
};

// Mirror overlays per mode: each clips a source region of the base copy and
// flips it onto the region it covers. clip-path applies in the element's own
// coordinate space BEFORE its transform, so "clip left half + scaleX(-1)"
// lands the mirrored left half exactly on the right half.
const mirrorOverlays = (
  mode: PrismMode,
  bandSeam: number,
): { clip: string; transform: string; origin: string }[] => {
  switch (mode) {
    case "mirror-2":
      return [{ clip: "inset(0 50% 0 0)", transform: "scaleX(-1)", origin: "50% 50%" }];
    case "mirror-4":
      return [
        { clip: "inset(0 50% 50% 0)", transform: "scaleX(-1)", origin: "50% 50%" },
        { clip: "inset(0 50% 50% 0)", transform: "scaleY(-1)", origin: "50% 50%" },
        { clip: "inset(0 50% 50% 0)", transform: "scale(-1, -1)", origin: "50% 50%" },
      ];
    case "split-band":
      // Keep the TOP region [0..seam] and reflect it downward about the seam;
      // seam >= 50% so the reflection always reaches the bottom edge.
      return [
        {
          clip: `inset(0 0 ${(100 - bandSeam).toFixed(2)}% 0)`,
          transform: "scaleY(-1)",
          origin: `50% ${bandSeam.toFixed(2)}%`,
        },
      ];
    default:
      return [];
  }
};

export const PrismMedia: React.FC<{
  imageUrl: string;
  videoSrc?: string;
  cameraTransform: string;
  imgFilter: string;
  mediaOpacity: number;
  prism: PrismConfig;
  /** Per-scene base strength from prismSceneStrength (1 poster / 0.45 body). */
  baseStrength: number;
  flareIn?: boolean;
  flareOut?: boolean;
  durationInFrames: number;
  palette: Palette;
  neon: boolean;
}> = ({
  imageUrl,
  videoSrc,
  cameraTransform,
  imgFilter,
  mediaOpacity,
  prism,
  baseStrength,
  flareIn,
  flareOut,
  durationInFrames,
  palette,
  neon,
}) => {
  const frame = useCurrentFrame();
  const phase = prism.driftPhase;

  // Dressed cuts flare the treatment for ~8 frames on each side of the
  // boundary — scenes butt together, so the peak lands exactly on the cut.
  const flare =
    (flareIn
      ? interpolate(frame, [0, 8], [0.5, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
      : 0) +
    (flareOut
      ? interpolate(frame, [durationInFrames - 8, durationInFrames], [0, 0.5], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 0);
  const strength = Math.min(1, baseStrength + flare);

  // Mode is fixed per scene (mid-scene mode switches pop); flares only scale
  // amplitudes/opacities, which ramp smoothly. Body scenes carry the video's
  // FULL mode at reduced overlay opacity — the reference edit never parks its
  // treatment — and only very mild bodies fall back to blend-drift.
  let mode: PrismMode =
    baseStrength >= 0.6
      ? prism.mode
      : prism.bodyMode === "mirror-2-soft"
        ? "mirror-2"
        : "blend-drift";
  // Video guardrail: at most 2 OffthreadVideo copies per scene.
  if (videoSrc && mode === "mirror-4") mode = "mirror-2";
  const isMirror = mode !== "blend-drift";
  const overlayOpacity = baseStrength >= 0.8 ? 1 : 0.75;

  // Whole-group breathing + the slow source sweep that pushes content through
  // the kaleidoscope. Both are bounded oscillations so the 115% media never
  // reveals its edges (the mirror group also scales up 18% as cover).
  const groupRot = Math.sin(frame * 0.006 + phase) * 3.2 * strength;
  const groupScale = (1 + Math.sin(frame * 0.004 + phase) * 0.015) * (isMirror ? 1.18 : 1);
  const srcRotation = isMirror
    ? Math.sin(frame * 0.008 + phase) * 9 * prism.twirlDir * (0.5 + 0.5 * strength)
    : 0;

  // Luminous lift — the reference is bright and light-washed, while the grade
  // filters crush brightness (~0.6-0.76) for text contrast. Treated scenes
  // win some of it back INSIDE the media wrapper; the vignette + bottom scrim
  // above are untouched, so the caption band keeps its guaranteed darkness.
  const liftedFilter = `${imgFilter} brightness(${(1 + 0.28 * strength).toFixed(3)}) saturate(${(1 + 0.12 * strength).toFixed(3)})`;

  const overlays = mirrorOverlays(mode, prism.bandSeam);

  const seamColor = withAlpha(palette.primary, prism.seamAlpha * strength);
  const seamGlow = neon ? `0 0 12px ${withAlpha(palette.primary, 0.5 * strength)}` : "none";
  const seamStyle: React.CSSProperties = {
    position: "absolute",
    background: seamColor,
    boxShadow: seamGlow,
    pointerEvents: "none",
  };

  const showInsets = baseStrength >= 0.8 && prism.insetWindows > 0;

  const groupTransform = `rotate(${groupRot.toFixed(3)}deg) scale(${groupScale.toFixed(4)})`;

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      {/* Graded media stack — the color grade is applied ONCE to the whole
          composited stack instead of per copy (rasterizing the filter for
          every mirror/smear/blend copy nearly doubled render time). */}
      <div style={{ position: "absolute", inset: 0, filter: liftedFilter }}>
        {/* ── Kaleidoscope group (base + mirror overlays + twirl smear) ── */}
        <div style={{ position: "absolute", inset: 0, transform: groupTransform }}>
          <div style={{ position: "absolute", inset: 0 }}>
            <MediaCopy
              imageUrl={imageUrl}
              videoSrc={videoSrc}
              cameraTransform={cameraTransform}
              filter="none"
              opacity={mediaOpacity}
              srcRotation={srcRotation}
            />
          </div>
          {overlays.map((o, i) => (
            <div
              key={`mirror-${i}`}
              style={{
                position: "absolute",
                inset: 0,
                clipPath: o.clip,
                transform: o.transform,
                transformOrigin: o.origin,
                opacity: overlayOpacity,
              }}
            >
              <MediaCopy
                imageUrl={imageUrl}
                videoSrc={videoSrc}
                cameraTransform={cameraTransform}
                filter="none"
                opacity={mediaOpacity}
                srcRotation={srcRotation}
              />
            </div>
          ))}
          {/* Twirl — rotational smear concentrated at the vortex core by a
              static radial mask; reads as the reference's swirl without any
              per-pixel displacement work. */}
          {isMirror &&
            prism.twirl &&
            [
              { rot: 4, op: 0.2 },
              { rot: -7, op: 0.14 },
            ].map((s, i) => (
              <div
                key={`smear-${i}`}
                style={{
                  position: "absolute",
                  inset: 0,
                  transform: `rotate(${s.rot * prism.twirlDir}deg)`,
                  mixBlendMode: "screen",
                  opacity: s.op * strength,
                  WebkitMaskImage:
                    "radial-gradient(circle at 50% 46%, #000 0%, rgba(0,0,0,0.6) 40%, transparent 62%)",
                  maskImage:
                    "radial-gradient(circle at 50% 46%, #000 0%, rgba(0,0,0,0.6) 40%, transparent 62%)",
                }}
              >
                <MediaCopy
                  imageUrl={imageUrl}
                  cameraTransform={cameraTransform}
                  filter="none"
                  opacity={1}
                  srcRotation={srcRotation}
                  imageOnly
                />
              </div>
            ))}
        </div>

        {/* ── Blend-layered footage: drifting screen/lighten copies. The
            screen-blend duplicate at a slight scale offset IS the cheap bloom
            (halation) — no blur filter involved. Image-only by design. ── */}
        {prism.blendCopies >= 1 && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              mixBlendMode: "screen",
              opacity: (0.3 + 0.12 * prism.bloom) * strength,
              transform: `scale(1.07) translate(${(Math.sin(frame * 0.005 + phase) * 14).toFixed(2)}px, ${(Math.cos(frame * 0.004 + phase) * 10).toFixed(2)}px)`,
            }}
          >
            <MediaCopy
              imageUrl={imageUrl}
              cameraTransform={cameraTransform}
              filter="brightness(1.35) saturate(1.25)"
              opacity={1}
              imageOnly
            />
          </div>
        )}
        {prism.blendCopies >= 2 && (
          <div
            style={{
              position: "absolute",
              inset: 0,
              mixBlendMode: "lighten",
              opacity: 0.2 * strength,
              transform: `scale(1.11) translate(${(Math.sin(frame * 0.005 + phase + Math.PI) * 12).toFixed(2)}px, ${(Math.cos(frame * 0.004 + phase + Math.PI) * 9).toFixed(2)}px)`,
            }}
          >
            <MediaCopy
              imageUrl={imageUrl}
              cameraTransform={cameraTransform}
              filter="brightness(1.2) contrast(1.05)"
              opacity={1}
              imageOnly
            />
          </div>
        )}
      </div>

      {/* ── Mirror seams — share the kaleido group's drift transform so the
          hairlines track the mirror axes; ungraded so neon seams stay lit. ── */}
      <div style={{ position: "absolute", inset: 0, transform: groupTransform, pointerEvents: "none" }}>
        {(mode === "mirror-2" || mode === "mirror-4") && (
          <div
            style={{
              ...seamStyle,
              left: "50%",
              top: 0,
              bottom: 0,
              width: 2,
              transform: "translateX(-1px)",
            }}
          />
        )}
        {mode === "mirror-4" && (
          <div
            style={{
              ...seamStyle,
              top: "50%",
              left: 0,
              right: 0,
              height: 2,
              transform: "translateY(-1px)",
            }}
          />
        )}
        {mode === "split-band" && (
          <div
            style={{
              ...seamStyle,
              top: `${prism.bandSeam.toFixed(2)}%`,
              left: 0,
              right: 0,
              height: 2,
              transform: "translateY(-1px)",
            }}
          />
        )}
      </div>

      {/* ── Bloom veils — the cyber cyan/magenta toning (LightLeaks idiom),
          plus a white top-glow for the reference's overexposed haze. ── */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          mixBlendMode: "screen",
          background: `radial-gradient(75% 55% at 50% 24%, rgba(255,255,255,${((0.09 + 0.06 * prism.bloom) * strength).toFixed(3)}) 0%, transparent 65%)`,
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          mixBlendMode: "screen",
          background: `radial-gradient(90% 70% at 50% 30%, ${withAlpha(palette.primarySoft, (0.1 + 0.08 * prism.bloom) * strength)} 0%, transparent 60%)`,
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          mixBlendMode: "screen",
          background: `radial-gradient(80% 60% at 50% 78%, ${withAlpha(palette.secondary, (0.08 + 0.06 * prism.bloom) * strength)} 0%, transparent 60%)`,
          pointerEvents: "none",
        }}
      />

      {/* ── Frame-in-frame inset windows (poster scenes only) ── */}
      {showInsets &&
        prism.insetSpecs.slice(0, prism.insetWindows).map((w, i) => {
          const entrance = interpolate(frame, [8 + i * 6, 20 + i * 6], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <div
              key={`inset-${i}`}
              style={{
                position: "absolute",
                left: `${w.x.toFixed(2)}%`,
                top: `${w.y.toFixed(2)}%`,
                width: `${w.w.toFixed(2)}%`,
                height: `${w.h.toFixed(2)}%`,
                overflow: "hidden",
                border: `1px solid ${palette.edge}`,
                opacity: entrance * strength,
              }}
            >
              <img
                src={imageUrl}
                style={{
                  position: "absolute",
                  inset: 0,
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                  transform: `scale(${w.zoom.toFixed(3)}) translate(${(Math.sin(frame * 0.004 + phase + i) * 6).toFixed(2)}px, ${(Math.cos(frame * 0.003 + phase + i) * 4).toFixed(2)}px)`,
                  filter: `${imgFilter} brightness(${w.exposure.toFixed(3)})`,
                }}
                alt=""
              />
            </div>
          );
        })}
    </div>
  );
};

// ---------------------------------------------------------------------------
// GiantWord — one oversized display word bleeding past the frame edges with
// the scene footage masked through the letterforms (background-clip: text).
// A SINGLE non-wrapping token by construction (whiteSpace: nowrap, no
// maxWidth, no flex) — Pain Point 6's word-splitting rule cannot trigger.
// Same background-clip precedent as AnimatedText's gradient-fill treatment:
// one text node, no descendant transformed spans.
// ---------------------------------------------------------------------------
const chooseGiantWord = (title: string): string => {
  const words = title.split(/\s+/).filter(Boolean);
  if (words.length === 0) return "";
  const emphasized = pickEmphasisIndices(words);
  let word = emphasized.size > 0 ? words[Math.min(...emphasized)] : "";
  if (!word) {
    word = words.reduce((a, b) => (b.length > a.length ? b : a), words[0]);
  }
  const clean = word.replace(/[^A-Za-z0-9%$#&+.'-]/g, "");
  return (clean || words[0]).toUpperCase();
};

export const GiantWord: React.FC<{
  title: string;
  imageUrl: string;
  fontFamilyName: string;
  palette: Palette;
  durationInFrames: number;
}> = ({ title, imageUrl, fontFamilyName, palette, durationInFrames }) => {
  const frame = useCurrentFrame();
  const { width } = useVideoConfig();

  const word = chooseGiantWord(title);
  if (!word) return null;

  // A giant masked serif fights the cyber identity — Playfair falls back to
  // Inter. Weights come from FONT_METRICS (real loaded weights only).
  const familyKey = (
    fontFamilyName === "Playfair Display" || !(fontFamilyName in FONT_METRICS)
      ? "Inter"
      : fontFamilyName
  ) as keyof typeof FONT_METRICS;
  const metrics = FONT_METRICS[familyKey];

  // Deliberately ~125% of the frame width so the word bleeds both edges; the
  // scene's AbsoluteFill clips the overflow. Cap keeps 2-3 letter words sane.
  const fontSize = Math.max(90, Math.min(460, Math.round((width * 1.25) / (word.length * 0.68))));

  const entrance = interpolate(frame, [0, 10], [0, 0.92], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const drift = 1 + (frame / Math.max(1, durationInFrames)) * 0.05;
  const bgY = 48 + Math.sin(frame * 0.01) * 4;

  return (
    <div
      style={{
        position: "absolute",
        left: "50%",
        top: "40%",
        transform: `translate(-50%, -50%) scale(${drift.toFixed(4)})`,
        zIndex: 12,
        pointerEvents: "none",
        whiteSpace: "nowrap",
        fontFamily: getFontFamily(familyKey),
        fontWeight: metrics.displayWeight,
        fontSize,
        lineHeight: 1,
        letterSpacing: "-0.01em",
        opacity: entrance,
        backgroundImage: `linear-gradient(160deg, ${withAlpha(palette.primarySoft, 0.9)} 0%, ${withAlpha(palette.secondary, 0.75)} 100%), url("${imageUrl}")`,
        backgroundBlendMode: "screen",
        backgroundSize: "cover",
        backgroundPosition: `50% ${bgY.toFixed(2)}%`,
        WebkitBackgroundClip: "text",
        backgroundClip: "text",
        color: "transparent",
        WebkitTextStroke: `1px ${withAlpha(palette.primarySoft, 0.35)}`,
      }}
    >
      {word}
    </div>
  );
};

// ---------------------------------------------------------------------------
// PrismFrame — the thin border frame from the reference. Static (always-on
// cheap class). Sits just above PolishStack (45) and below CutCover (55);
// at inset 14px it never crosses the subtitle text.
// ---------------------------------------------------------------------------
export const PrismFrame: React.FC<{
  primaryColor: string;
  secondaryColor: string;
  neon: boolean;
}> = ({ primaryColor, secondaryColor, neon }) => {
  const edge = withAlpha(tint(primaryColor, 0.35), 0.35);
  const tick = withAlpha(secondaryColor, 0.55);
  const tickStyle: React.CSSProperties = { position: "absolute", width: 18, height: 18 };
  return (
    <AbsoluteFill style={{ zIndex: 46, pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          inset: 14,
          border: `1px solid ${edge}`,
          boxShadow: neon
            ? `0 0 14px ${withAlpha(primaryColor, 0.18)}, inset 0 0 14px ${withAlpha(primaryColor, 0.12)}`
            : "none",
        }}
      />
      <div style={{ ...tickStyle, top: 10, left: 10, borderTop: `2px solid ${tick}`, borderLeft: `2px solid ${tick}` }} />
      <div style={{ ...tickStyle, top: 10, right: 10, borderTop: `2px solid ${tick}`, borderRight: `2px solid ${tick}` }} />
      <div style={{ ...tickStyle, bottom: 10, left: 10, borderBottom: `2px solid ${tick}`, borderLeft: `2px solid ${tick}` }} />
      <div style={{ ...tickStyle, bottom: 10, right: 10, borderBottom: `2px solid ${tick}`, borderRight: `2px solid ${tick}` }} />
    </AbsoluteFill>
  );
};

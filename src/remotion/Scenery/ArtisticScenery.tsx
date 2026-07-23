// ============================================================================
// ArtisticScenery — 10-20s calm scenery film ("artistic scenery exploration"
// branch). Renders the MontagePlan from cutEngine.ts: real stock footage +
// AI stills as long, slowly drifting takes joined by soft dissolves, then a
// settling hold where the single overlay line reveals.
//
// Everything visual is seed-derived here in React (same contract as MyComp):
// the Python side only supplies clips, text, mood, music and the seed.
// ============================================================================
import React, { useMemo } from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  Easing,
} from "remotion";
import { z } from "zod";
import { loadFont as loadPlayfair } from "@remotion/google-fonts/PlayfairDisplay";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";
import { SceneryProps } from "../../../types/constants";
import { deriveMontage, type MontageSegment, type SceneryMood } from "./cutEngine";
import { makeRng } from "../MyComp/looks";

// Only the weights/subsets actually used below (Playfair 400 overlay line,
// Inter 500 place name). Unrestricted loadFont() fetches EVERY variant from
// fonts.gstatic.com mid-render (~172 requests) — each one a chance for a CDN
// flake to abort the render after all upstream costs are paid. These calls
// run on news renders too (the bundle evaluates every composition).
const { fontFamily: playfair } = loadPlayfair("normal", {
  subsets: ["latin", "latin-ext"],
  weights: ["400"],
});
const { fontFamily: inter } = loadInter("normal", {
  subsets: ["latin", "latin-ext"],
  weights: ["500"],
});

// Calm tracks only (downloaded by generate_scenery.py). The news pipeline's
// energetic SoundHelix tracks are deliberately NOT offered here.
const MUSIC_FILES: Record<string, string> = {
  "calm-piano": "calm-piano.mp3",
  "floating-cities": "floating-cities.mp3",
  "healing-ambient": "healing-ambient.mp3",
  "dreamy-flashback": "dreamy-flashback.mp3",
  none: "",
};

// Mood -> base color grade for every clip. Scenery is the star: unlike MyComp
// (which darkens backgrounds so text can sit on them), these stay bright.
// All four grades are gentle now — no crunchy contrast/saturation pushes.
const MOOD_GRADE: Record<SceneryMood, string> = {
  ethereal: "brightness(1.04) contrast(1.02) saturate(1.08) hue-rotate(6deg)",
  serene: "brightness(1.03) contrast(1.0) saturate(1.04) sepia(0.08)",
  epic: "brightness(0.99) contrast(1.08) saturate(1.14)",
  electric: "brightness(1.0) contrast(1.08) saturate(1.18)",
};

// Inline SVG film grain — no external asset, deterministic, cheap.
const GRAIN_URI = `data:image/svg+xml,${encodeURIComponent(
  `<svg xmlns='http://www.w3.org/2000/svg' width='280' height='280'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/></filter><rect width='280' height='280' filter='url(#n)' opacity='0.55'/></svg>`,
)}`;

const resolveSrc = (src: string): string =>
  src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")
    ? src
    : staticFile(src);

/** Overlay line must NEVER wrap or split words: size to fit one line. */
const fitFontSize = (text: string, maxWidth = 940, max = 88, min = 34): number => {
  const len = Math.max(6, text.length);
  return Math.max(min, Math.min(max, Math.floor(maxWidth / (0.58 * len))));
};

const SegmentLayer: React.FC<{
  seg: MontageSegment;
  clip: { src: string; kind: "video" | "image" };
  mood: SceneryMood;
  fps: number;
}> = ({ seg, clip, mood, fps }) => {
  const frame = useCurrentFrame(); // local to the parent <Sequence>

  // Linear drift — constant, unhurried motion across the whole take. Easing
  // here would make the frame speed up and slow down, which reads as restless.
  const t = interpolate(frame, [0, seg.dur], [0, 1], { extrapolateRight: "clamp" });
  const zoom = seg.zoomFrom + (seg.zoomTo - seg.zoomFrom) * t;
  const panX = seg.panX * t;
  const panY = seg.panY * t;

  // The only two entrances that exist: the opening fade from black, and the
  // slow dissolve that overlaps the previous take (which stays mounted
  // beneath this layer until the dissolve completes).
  const opacity =
    seg.enter === "fade-in"
      ? interpolate(frame, [0, Math.min(24, seg.dur)], [0, 1], {
          extrapolateRight: "clamp",
          easing: Easing.inOut(Easing.sin),
        })
      : interpolate(frame, [0, Math.max(1, seg.xfade)], [0, 1], {
          extrapolateRight: "clamp",
          easing: Easing.inOut(Easing.sin),
        });

  const mediaStyle: React.CSSProperties = {
    position: "absolute",
    inset: 0,
    width: "100%",
    height: "100%",
    objectFit: "cover",
    opacity,
    transform: [
      seg.mirror ? "scaleX(-1)" : "",
      `translate(${panX.toFixed(1)}px, ${panY.toFixed(1)}px)`,
      `scale(${zoom.toFixed(4)})`,
    ]
      .filter(Boolean)
      .join(" "),
    filter: MOOD_GRADE[mood],
  };

  // Transparent fill: during a dissolve the outgoing take must stay visible
  // underneath — an opaque background would turn every dissolve into a dip.
  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      {clip.kind === "video" ? (
        <OffthreadVideo
          muted
          src={resolveSrc(clip.src)}
          startFrom={Math.round(seg.startFromSec * fps)}
          style={mediaStyle}
        />
      ) : (
        <Img src={resolveSrc(clip.src)} style={mediaStyle} />
      )}
    </AbsoluteFill>
  );
};

export const ArtisticScenery: React.FC<z.infer<typeof SceneryProps>> = ({
  clips,
  overlayLine = "",
  placeName = "",
  musicTrack = "calm-piano",
  mood = "epic",
  seed = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const plan = useMemo(
    () => deriveMontage(seed, clips, durationInFrames, mood, fps),
    [seed, clips, durationInFrames, mood, fps],
  );

  // Seeded music trim so two videos sharing a track never open on the same bar.
  const musicStartFrom = useMemo(() => {
    const rng = makeRng(((seed ^ 0x33aa771) >>> 0) || 1);
    return Math.floor(rng() * 40) * fps; // 0-40s into the track
  }, [seed, fps]);

  // --- Text reveal timing (inside the final hold) — slow and unhurried. ---
  const lineAt = plan.holdStart + 14;
  const lineIn = interpolate(frame, [lineAt, lineAt + 30], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });
  const placeIn = interpolate(frame, [lineAt + 18, lineAt + 44], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const letterSpacing = interpolate(lineIn, [0, 1], [0.3, 0.1]);
  const fontSize = fitFontSize(overlayLine || placeName || " ");

  // Ending exhale — long fade to black over the last ~0.75s.
  const endFade = interpolate(frame, [durationInFrames - 22, durationInFrames - 2], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const musicFile = MUSIC_FILES[musicTrack] || "";
  // Quiet bed, never a lead: slow 1.5s fade in, ~1.8s fade out to silence.
  const musicVolume = (f: number): number => {
    const fadeIn = interpolate(f, [0, 45], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const fadeOut = interpolate(f, [durationInFrames - 55, durationInFrames - 2], [1, 0], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
    return 0.55 * fadeIn * fadeOut;
  };

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <AbsoluteFill>
        {plan.segments.map((seg, i) => {
          const clip = clips[seg.clipIndex % Math.max(1, clips.length)];
          if (!clip) return null;
          return (
            <Sequence key={i} from={seg.start} durationInFrames={seg.dur} layout="absolute-fill">
              <SegmentLayer seg={seg} clip={clip} mood={mood} fps={fps} />
            </Sequence>
          );
        })}
      </AbsoluteFill>

      {/* Cinematic letterbox — structural frame that also hides pan edges. */}
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 84, background: "#000" }} />
      <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 84, background: "#000" }} />

      {/* Legibility gradient under the text zone, only during the hold. */}
      <AbsoluteFill
        style={{
          background: "linear-gradient(to top, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 38%)",
          opacity: lineIn,
          pointerEvents: "none",
        }}
      />

      {/* Film grain, drifting gently so it reads as film, never as static. */}
      <AbsoluteFill
        style={{
          backgroundImage: `url("${GRAIN_URI}")`,
          backgroundPosition: `${(frame * 2.1) % 280}px ${(frame * 3.3) % 280}px`,
          opacity: 0.05,
          mixBlendMode: "overlay",
          pointerEvents: "none",
        }}
      />

      {/* The single overlay line + real place name — never wrapped, never split. */}
      {overlayLine ? (
        <AbsoluteFill
          style={{
            justifyContent: "flex-end",
            alignItems: "center",
            paddingBottom: 260,
            opacity: lineIn,
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              fontFamily: playfair,
              fontSize,
              color: "#fff",
              whiteSpace: "nowrap",
              letterSpacing: `${letterSpacing}em`,
              textShadow: "0 2px 24px rgba(0,0,0,0.7)",
              transform: `translateY(${(1 - lineIn) * 10}px)`,
            }}
          >
            {overlayLine}
          </div>
          {placeName ? (
            <div
              style={{
                fontFamily: inter,
                fontSize: 26,
                fontWeight: 500,
                color: "rgba(255,255,255,0.82)",
                whiteSpace: "nowrap",
                letterSpacing: "0.34em",
                textTransform: "uppercase",
                marginTop: 22,
                opacity: placeIn,
                textShadow: "0 1px 12px rgba(0,0,0,0.7)",
              }}
            >
              {placeName}
            </div>
          ) : null}
        </AbsoluteFill>
      ) : null}

      {endFade > 0 && <AbsoluteFill style={{ backgroundColor: "#000", opacity: endFade }} />}

      {musicFile ? (
        // loop: calm tracks vary in length; the bed must never run out early.
        <Audio loop src={staticFile(musicFile)} startFrom={musicStartFrom} volume={musicVolume} />
      ) : null}
    </AbsoluteFill>
  );
};

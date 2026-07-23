import React from "react";
import { AbsoluteFill, useCurrentFrame, interpolate, Easing } from "remotion";
import type { CutSpec } from "./transitions";
import { EASE } from "./motion";

type TransitionStyle =
  | "crossfade"
  | "slide-left"
  | "zoom-through"
  | "glitch-cut"
  | "wipe-down"
  | "iris-open"
  | "blur-dissolve"
  | "scale-rotate"
  | "push-up"
  | "spin-blur"
  | "none";

// One visually-compatible companion per primary style. A video uses its
// chosen transition for most cuts and the companion for the rest — motion
// identity instead of a 10-style grab bag (the strongest "template" tell).
// (Legacy fallback path only; the cut-plan path gets this from transitions.ts.)
const COMPANION: Record<TransitionStyle, TransitionStyle> = {
  crossfade: "blur-dissolve",
  "slide-left": "push-up",
  "zoom-through": "crossfade",
  "glitch-cut": "slide-left",
  "wipe-down": "push-up",
  "iris-open": "crossfade",
  "blur-dissolve": "crossfade",
  "scale-rotate": "zoom-through",
  "push-up": "slide-left",
  "spin-blur": "zoom-through",
  none: "none",
};

// Enters decelerate in, exits accelerate out — asymmetric easing is what makes
// a cut feel edited rather than mechanically ramped. The canonical curves live
// in motion.ts so every component exits/enters on the cut engine's vocabulary.
const EASE_OUT = EASE.swiftOut;
const EASE_IN = EASE.swiftIn;

interface SceneTransitionProps {
  /** Total duration of this scene in frames */
  durationInFrames: number;
  /** Transition style applied at enter/exit edges (legacy fallback path) */
  transitionStyle: TransitionStyle;
  /** Number of frames used for the transition effect at each edge */
  transitionDuration?: number;
  /** Scene index — used to alternate between the primary style and its companion */
  sceneIndex?: number;
  /** Per-video seed — combined with sceneIndex so each video gets a unique transition sequence */
  seed?: number;
  /**
   * Boundary-coordinated cut specs from deriveCutPlan. When BOTH are present
   * the component renders each edge from its spec (enter = the boundary
   * behind this scene, exit = the boundary ahead), so both sides of a cut
   * agree on style and direction. When absent, the legacy per-scene
   * companion-roll path runs unchanged.
   */
  enterCut?: CutSpec;
  exitCut?: CutSpec;
  /** Theme primary color — tints film-burn / sweep overlays. */
  accentColor?: string;
  children: React.ReactNode;
}

// ---------------------------------------------------------------------------
// Per-edge visual computation for the cut-plan path. Each style expresses its
// enter and exit halves separately so a boundary can pair scene N's exit with
// scene N+1's enter of the SAME spec. All recipes are cheap CSS transforms /
// filters / clip-paths — no canvas, no per-pixel work.
// ---------------------------------------------------------------------------

interface GhostSpec {
  transform: string;
  filter?: string;
  opacity: number;
}

interface EdgeVisual {
  opacity: number;
  transforms: string[];
  filters: string[];
  clipPath?: string;
  maskImage?: string;
  transformOrigin?: string;
  ghosts?: GhostSpec[];
  overlay?: React.ReactNode;
}

const NEUTRAL: EdgeVisual = { opacity: 1, transforms: [], filters: [] };

interface EdgeCtx {
  frame: number;
  durationInFrames: number;
  accent: string;
}

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

// Film-burn anchors — flavor picks a corner so consecutive burns differ.
const BURN_CORNERS = ["14% 10%", "86% 10%", "84% 88%", "16% 86%"] as const;

function computeEdge(
  spec: CutSpec,
  t: number,
  phase: "enter" | "exit",
  ctx: EdgeCtx,
): EdgeVisual {
  const { style, dir, axis, flavor } = spec;
  const E = spec.intensity;
  const entering = phase === "enter";
  // Fully entered / not yet exiting → nothing to draw.
  if ((entering && t >= 1) || (!entering && t <= 0)) {
    // stutter-zoom holds discrete steps slightly past the eased window, so
    // let it through; everything else is neutral.
    if (style !== "stutter-zoom") return NEUTRAL;
  }

  switch (style) {
    case "none":
      return NEUTRAL;

    // The connector cut: a hard cut where the incoming frame lands ~7%
    // punched-in and settles. No opacity ramp — any fade is exactly what
    // makes punch cuts read mushy instead of confident.
    case "punch-in": {
      if (!entering) return NEUTRAL;
      // `t` arrives already EASE_OUT-eased, which is exactly the settle shape
      // a punch wants: fast decay early, ~90% settled by frame 5 of the
      // 10-frame enter. Do NOT compress it further — an extra multiplier on
      // the eased value collapses the whole settle into ~2 frames and the
      // punch reads as a one-frame twitch.
      if (t >= 1) return NEUTRAL;
      return {
        opacity: 1,
        transforms: [`scale(${1 + 0.08 * E * (1 - t)})`],
        filters: [],
        // Off-center focal point per boundary so back-to-back punches don't
        // pump the exact same pixel.
        transformOrigin: `${50 + (flavor - 0.5) * 12}% ${46 + (flavor - 0.5) * 10}%`,
      };
    }

    // ── Legacy styles, decomposed per phase (recipes match the fallback path) ──
    case "crossfade":
      return entering
        ? { opacity: t, transforms: [`scale(${1 + 0.03 * (1 - t)})`], filters: [] }
        : { opacity: 1 - t, transforms: [`scale(${1 - 0.015 * t})`], filters: [] };

    case "slide-left": {
      if (entering) {
        return {
          opacity: interpolate(t, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
          transforms: [`translateX(${(1 - t) * 100}%)`, `skewX(${-2.5 * (1 - t)}deg)`],
          filters: [],
        };
      }
      return {
        opacity: 1 - interpolate(t, [0.5, 1], [0, 1], { extrapolateLeft: "clamp" }),
        transforms: [`translateX(${-t * 100}%)`, `skewX(${2.5 * t}deg)`],
        filters: [],
      };
    }

    case "zoom-through": {
      if (entering) {
        return {
          opacity: interpolate(t, [0, 0.55], [0, 1], { extrapolateRight: "clamp" }),
          transforms: [`scale(${0.75 + 0.25 * t})`],
          filters: [`brightness(${1 + 0.3 * (1 - t)})`],
        };
      }
      return {
        opacity: 1 - interpolate(t, [0.45, 1], [0, 1], { extrapolateLeft: "clamp" }),
        transforms: [`scale(${1 + 0.5 * t})`],
        filters: [`brightness(${1 + 0.35 * t})`],
      };
    }

    case "wipe-down": {
      if (entering) {
        const p = Math.min(t * 200, 100);
        return {
          opacity: 1,
          transforms: [],
          filters: [],
          clipPath: t >= 1 ? undefined : `polygon(0 0, ${p}% 0, ${p}% ${p}%, 0 ${p}%)`,
          overlay:
            t >= 1 ? undefined : (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  background: `linear-gradient(135deg, transparent ${Math.max(0, t * 100 - 5)}%, rgba(255,255,255,0.3) ${t * 100}%, transparent ${t * 100 + 2}%)`,
                  pointerEvents: "none",
                }}
              />
            ),
        };
      }
      return { opacity: 1 - t, transforms: [], filters: [] };
    }

    case "iris-open": {
      if (entering) {
        const radius = t * 100;
        return {
          opacity: 1,
          transforms: [],
          filters: [],
          clipPath: radius >= 100 ? undefined : `circle(${radius}% at 50% 50%)`,
        };
      }
      return { opacity: 1 - t, transforms: [], filters: [] };
    }

    case "blur-dissolve": {
      if (entering) {
        return {
          opacity: interpolate(t, [0, 0.8], [0, 1], { extrapolateRight: "clamp" }),
          transforms: [],
          filters: [`blur(${10 * (1 - t)}px)`],
        };
      }
      return {
        opacity: 1 - interpolate(t, [0.3, 1], [0, 1], { extrapolateLeft: "clamp" }),
        transforms: [],
        filters: [`blur(${10 * t}px)`],
      };
    }

    case "scale-rotate": {
      if (entering) {
        return {
          opacity: interpolate(t, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
          transforms: [`scale(${0.7 + 0.3 * t})`, `rotate(${-6 * (1 - t)}deg)`],
          filters: [],
        };
      }
      return {
        opacity: 1 - interpolate(t, [0.5, 1], [0, 1], { extrapolateLeft: "clamp" }),
        transforms: [`scale(${1 - 0.1 * t})`, `rotate(${6 * t}deg)`],
        filters: [],
      };
    }

    case "push-up": {
      if (entering) {
        return {
          opacity: interpolate(t, [0, 0.5], [0.3, 1], { extrapolateRight: "clamp" }),
          transforms: [`translateY(${(1 - t) * 100}%)`],
          filters: [],
        };
      }
      return {
        opacity: 1 - interpolate(t, [0.4, 1], [0, 0.7], { extrapolateLeft: "clamp" }),
        transforms: [`translateY(${-t * 100}%)`],
        filters: [],
      };
    }

    case "spin-blur": {
      if (entering) {
        return {
          opacity: interpolate(t, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }),
          transforms: [`rotate(${-10 * (1 - t)}deg)`, `scale(${1.2 - 0.2 * t})`],
          filters: [`blur(${8 * (1 - t)}px)`],
        };
      }
      return {
        opacity: 1 - interpolate(t, [0.5, 1], [0, 1], { extrapolateLeft: "clamp" }),
        transforms: [`rotate(${10 * t}deg)`, `scale(${1 + 0.2 * t})`],
        filters: [`blur(${8 * t}px)`],
      };
    }

    // glitch-cut is handled by the burst wrapper in the component (its
    // multi-copy displacement logic doesn't decompose into an EdgeVisual).
    case "glitch-cut":
      return NEUTRAL;

    // ── New render-side styles ──────────────────────────────────────────────

    case "whip-pan": {
      // Both halves share `dir`, so old content flies off exactly where new
      // content flies in from — the motion continues across the cut.
      const move = entering ? dir * 65 * E * (1 - t) : -dir * 65 * E * t;
      const skew = entering ? dir * -6 * (1 - t) : dir * -6 * t;
      const stretch = entering ? 1 + 0.12 * (1 - t) : 1 + 0.12 * t;
      const blur = entering ? 10 * (1 - t) : 10 * t;
      const translate = axis === "x" ? `translateX(${move}%)` : `translateY(${move}%)`;
      const skewT = axis === "x" ? `skewX(${skew}deg)` : `skewY(${skew}deg)`;
      const scaleT = axis === "x" ? `scaleX(${stretch})` : `scaleY(${stretch})`;
      // Velocity streaks along the motion axis while the whip is fast — the
      // detail that sells a whip as motion blur instead of a slide. Streaks
      // ride at half the content's speed (parallax) and screen-blend so they
      // read as light smear, not a texture.
      const k = entering ? 1 - t : t;
      const streakShift = move * 0.5;
      return {
        opacity: entering
          ? interpolate(t, [0, 0.35], [0, 1], { extrapolateRight: "clamp" })
          : 1 - interpolate(t, [0.55, 1], [0, 1], { extrapolateLeft: "clamp" }),
        transforms: [translate, skewT, scaleT],
        filters: blur > 0.5 ? [`blur(${blur}px)`] : [],
        overlay:
          k <= 0.08 ? undefined : (
            <div
              style={{
                position: "absolute",
                inset: "-12%",
                background: `repeating-linear-gradient(${axis === "x" ? 0 : 90}deg, transparent 0px, transparent 34px, rgba(255,255,255,${0.09 * E * k}) 38px, transparent 44px)`,
                transform:
                  axis === "x"
                    ? `translateX(${streakShift}%)`
                    : `translateY(${streakShift}%)`,
                mixBlendMode: "screen",
                pointerEvents: "none",
              }}
            />
          ),
      };
    }

    case "film-burn": {
      // The burn brightens INTO the cut and decays OUT of it — with both
      // sides anchored at the same flavor-picked corner it reads as one
      // continuous burn spanning the cut (CutCover carries the peak frame).
      const k = entering ? 1 - t : t;
      const corner = BURN_CORNERS[Math.floor(flavor * 4) % 4];
      return {
        opacity: entering ? interpolate(t, [0, 0.3], [0.4, 1], { extrapolateRight: "clamp" }) : 1,
        transforms: [],
        filters: [`brightness(${1 + 0.8 * E * k})`, `sepia(${0.25 * k})`],
        overlay:
          k <= 0.01 ? undefined : (
            <div
              style={{
                position: "absolute",
                inset: 0,
                background: `radial-gradient(circle at ${corner}, rgba(255,179,107,0.95), ${ctx.accent} 35%, transparent 70%)`,
                opacity: 0.85 * E * k,
                mixBlendMode: "screen",
                pointerEvents: "none",
              }}
            />
          ),
      };
    }

    case "venetian-blinds": {
      // Pure reveal illusion: children stay untransformed; dark slats shrink
      // open on enter and grow closed ahead of the cut. Plain divs +
      // transform only.
      const nBars = 6 + (Math.floor(flavor * 4) % 4);
      const bars = Array.from({ length: nBars }, (_, i) => {
        // Normalized stagger: every slat's window ends by t=1, so the frame is
        // FULLY covered exactly at the cut (no last-slat pop).
        const stagger = (i / nBars) * 0.4;
        const bp = clamp01(interpolate(t, [stagger, stagger + 0.6], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }));
        const coverage = entering ? 1 - bp : bp;
        const horizontal = axis === "x";
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              ...(horizontal
                ? {
                    left: 0,
                    right: 0,
                    top: `${(i / nBars) * 100}%`,
                    height: `${100 / nBars + 0.5}%`,
                    transform: `scaleY(${coverage})`,
                    transformOrigin: i % 2 === 0 ? "top" : "bottom",
                  }
                : {
                    top: 0,
                    bottom: 0,
                    left: `${(i / nBars) * 100}%`,
                    width: `${100 / nBars + 0.5}%`,
                    transform: `scaleX(${coverage})`,
                    transformOrigin: i % 2 === 0 ? "left" : "right",
                  }),
              backgroundColor: "rgba(2,2,6,0.92)",
              pointerEvents: "none",
            }}
          />
        );
      });
      return { opacity: 1, transforms: [], filters: [], overlay: <>{bars}</> };
    }

    case "luma-radial": {
      if (entering) {
        // Clock wipe: a conic mask sweeps the new scene in from a
        // flavor-picked start angle. Removed entirely once open.
        if (t >= 1) return NEUTRAL;
        const p = t * 376 - 16;
        const from = Math.floor(flavor * 360);
        return {
          opacity: 1,
          transforms: [],
          filters: [],
          maskImage: `conic-gradient(from ${from}deg at 50% 45%, black 0deg, black ${p}deg, rgba(0,0,0,0.35) ${p + 8}deg, transparent ${p + 16}deg)`,
        };
      }
      // The next scene's radial enter is the star; this side just settles.
      return {
        opacity: 1 - interpolate(t, [0.4, 1], [0, 1], { extrapolateLeft: "clamp" }),
        transforms: [`rotate(${1.2 * t}deg)`],
        filters: [],
      };
    }

    case "chromatic-punch": {
      // Ghost copies live only in a ≤5-frame window per edge (same budget as
      // glitch-cut's burst), so the extra children renders stay cheap.
      const gT = entering
        ? clamp01(ctx.frame / 5)
        : clamp01((ctx.durationInFrames - ctx.frame) / 5);
      const ghostK = 1 - gT;
      const ghosts: GhostSpec[] =
        ghostK <= 0.01
          ? []
          : [
              {
                transform: `translateX(${ghostK * 10 * E}px)`,
                filter: "hue-rotate(120deg) saturate(2)",
                opacity: 0.35 * ghostK,
              },
              {
                transform: `translateX(${-ghostK * 10 * E}px)`,
                filter: "hue-rotate(-120deg) saturate(2)",
                opacity: 0.35 * ghostK,
              },
            ];
      return {
        opacity: 1,
        transforms: [entering ? `scale(${0.88 + 0.12 * t})` : `scale(${1 + 0.1 * E * t})`],
        filters: [],
        ghosts,
      };
    }

    case "skew-peel": {
      if (entering) {
        return {
          opacity: interpolate(t, [0, 0.4], [0, 1], { extrapolateRight: "clamp" }),
          transforms: [
            `rotate(${dir * -7 * (1 - t)}deg)`,
            `translateY(${-6 * (1 - t)}%)`,
            `skewY(${dir * -3 * (1 - t)}deg)`,
          ],
          filters: [],
          transformOrigin: dir > 0 ? "top left" : "top right",
          overlay:
            t >= 1 ? undefined : (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  background: `linear-gradient(${dir > 0 ? 115 : 65}deg, rgba(0,0,0,0.5), transparent 40%)`,
                  opacity: 1 - t,
                  pointerEvents: "none",
                }}
              />
            ),
        };
      }
      return {
        opacity: 1 - interpolate(t, [0.5, 1], [0, 1], { extrapolateLeft: "clamp" }),
        transforms: [
          `rotate(${dir * 5 * t}deg)`,
          `translateY(${4 * t}%)`,
          `skewY(${dir * 2 * t}deg)`,
        ],
        filters: [],
        transformOrigin: dir > 0 ? "bottom right" : "bottom left",
      };
    }

    case "stutter-zoom": {
      // A deliberate ~9-frame quantized zoom-settle at the edge (NOT the
      // full-scene time-warp strobe the header comment warns about — the
      // stutter is the effect here, and it's confined to the edge window).
      if (entering) {
        const f = ctx.frame;
        let scale: number;
        let pop = false;
        if (f < 3) {
          scale = 1 + 0.22 * E;
          pop = f === 0;
        } else if (f < 6) {
          scale = 1 + 0.1 * E;
          pop = f === 3;
        } else if (f < 9) {
          scale = 1 + 0.03 * E;
          pop = f === 6;
        } else if (f < 13) {
          scale = 1 + 0.03 * E * (1 - (f - 9) / 4);
        } else {
          return NEUTRAL;
        }
        return {
          opacity: 1,
          transforms: [`scale(${scale})`],
          filters: pop ? ["brightness(1.15)"] : [],
        };
      }
      const rem = ctx.durationInFrames - ctx.frame;
      if (rem > 6) return NEUTRAL;
      const scale = rem <= 3 ? 1 + 0.14 * E : 1 + 0.06 * E;
      const pop = rem === 3 || rem === 6;
      return {
        opacity: 1,
        transforms: [`scale(${scale})`],
        filters: pop ? ["brightness(1.15)"] : [],
      };
    }

    case "diamond-iris": {
      if (entering) {
        const r = t * 115;
        if (r >= 115) return NEUTRAL;
        return {
          opacity: 1,
          transforms: [],
          filters: [],
          clipPath: `polygon(50% ${50 - r}%, ${50 + r}% 50%, 50% ${50 + r}%, ${50 - r}% 50%)`,
        };
      }
      return {
        opacity: 1 - interpolate(t, [0.5, 1], [0, 1], { extrapolateLeft: "clamp" }),
        transforms: [`scale(${1 + 0.04 * t})`],
        filters: [],
      };
    }

    default:
      return NEUTRAL;
  }
}

// Legacy glitch burst — used by BOTH paths so glitch cuts look identical
// whether they come from the old companion roll or a CutSpec.
const GlitchBurst: React.FC<{
  frame: number;
  durationInFrames: number;
  seed: number;
  entering: boolean;
  children: React.ReactNode;
}> = ({ frame, durationInFrames, seed, entering, children }) => {
  const glitchFrames = 5;
  // Amplitude decays across the burst; offsets hold 2 frames per roll so
  // the glitch reads as designed displacement, not dropped frames.
  const k = entering
    ? 1 - frame / glitchFrames
    : (frame - (durationInFrames - glitchFrames)) / glitchFrames;
  const roll = ((seed + Math.floor(frame / 2) * 7919) >>> 0) || 1;
  const offsetX = ((roll % 20) - 10) * k;
  const offsetY = (((roll * 3) % 14) - 7) * k;
  const shakeX = (((roll * 17) % 10) - 5) * k;
  const shakeY = (((roll * 23) % 8) - 4) * k;

  return (
    <AbsoluteFill style={{ transform: `translate(${shakeX}px, ${shakeY}px)` }}>
      <AbsoluteFill
        style={{
          transform: `translate(${offsetX}px, ${offsetY}px)`,
          mixBlendMode: "screen",
          opacity: 0.4 * Math.max(0.2, k),
          filter: "saturate(3) hue-rotate(-30deg)",
        }}
      >
        {children}
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          transform: `translate(${-offsetX}px, ${-offsetY}px)`,
          mixBlendMode: "screen",
          opacity: 0.4 * Math.max(0.2, k),
          filter: "saturate(3) hue-rotate(150deg)",
        }}
      >
        {children}
      </AbsoluteFill>
      <AbsoluteFill style={{ opacity: 0.85 }}>{children}</AbsoluteFill>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: `${30 + (roll % 40)}%`,
          height: "3px",
          backgroundColor: `rgba(255,255,255,${0.9 * k})`,
          boxShadow: `0 0 20px rgba(255,255,255,${0.5 * k})`,
        }}
      />
    </AbsoluteFill>
  );
};

/**
 * SceneTransition wraps a scene's content and applies enter/exit transitions.
 *
 * With `enterCut`/`exitCut` (the cut-plan path): each edge renders its own
 * boundary spec, so both sides of every cut agree on style and direction.
 * Without them (legacy path): the video's transitionStyle stays dominant
 * (~2/3 of cuts) with its curated companion on the rest, seed-picked.
 * Enter edges are the star; exit edges are short and get out of the way, so
 * butted sequences never mush through a long double-fade.
 */
export const SceneTransition: React.FC<SceneTransitionProps> = ({
  durationInFrames,
  transitionStyle,
  transitionDuration = 15,
  sceneIndex,
  seed = 0,
  enterCut,
  exitCut,
  accentColor = "#00f0ff",
  children,
}) => {
  const frame = useCurrentFrame();
  const td = Math.min(transitionDuration, Math.floor(durationInFrames / 3));
  // The OPENING scene must be readable almost immediately — viewers judge a
  // Reel in its first frames. Scene 0 gets a 4-frame enter; no time-warping
  // (multiplying the clock renders only every 5th pose — a visible strobe).
  const enterDur = sceneIndex === 0 ? 4 : Math.min(10, td);
  const exitDur = Math.min(6, td);

  // 0..1 eased edge progress shared by every style.
  const enterT = interpolate(frame, [0, enterDur], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: EASE_OUT,
  });
  const exitT = interpolate(
    frame,
    [durationInFrames - exitDur, durationInFrames],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: EASE_IN }
  );

  // ── Cut-plan path ────────────────────────────────────────────────────────
  if (enterCut && exitCut) {
    if (enterCut.style === "none" && exitCut.style === "none") {
      return <AbsoluteFill>{children}</AbsoluteFill>;
    }

    // Glitch bursts keep their dedicated multi-copy wrapper.
    const glitchFrames = 5;
    if (enterCut.style === "glitch-cut" && frame < glitchFrames) {
      return (
        <GlitchBurst frame={frame} durationInFrames={durationInFrames} seed={seed} entering>
          {children}
        </GlitchBurst>
      );
    }
    if (exitCut.style === "glitch-cut" && frame > durationInFrames - glitchFrames) {
      return (
        <GlitchBurst frame={frame} durationInFrames={durationInFrames} seed={seed} entering={false}>
          {children}
        </GlitchBurst>
      );
    }

    const ctx: EdgeCtx = { frame, durationInFrames, accent: accentColor };
    const enterVis =
      enterCut.style === "glitch-cut" ? NEUTRAL : computeEdge(enterCut, enterT, "enter", ctx);
    const exitVis =
      exitCut.style === "glitch-cut" ? NEUTRAL : computeEdge(exitCut, exitT, "exit", ctx);

    // Glitch enter settles its brightness for 3 frames after the burst.
    const glitchSettle =
      enterCut.style === "glitch-cut"
        ? interpolate(frame, [glitchFrames, glitchFrames + 3], [1.12, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.out(Easing.quad),
          })
        : 1;

    const opacity = enterVis.opacity * exitVis.opacity;
    const transforms = [...enterVis.transforms, ...exitVis.transforms].join(" ");
    const filters = [
      ...enterVis.filters,
      ...exitVis.filters,
      ...(glitchSettle !== 1 ? [`brightness(${glitchSettle})`] : []),
    ].join(" ");
    const clipPath = enterVis.clipPath ?? exitVis.clipPath;
    const maskImage = enterVis.maskImage ?? exitVis.maskImage;
    const transformOrigin = enterVis.transformOrigin ?? exitVis.transformOrigin;
    const ghosts = [...(enterVis.ghosts ?? []), ...(exitVis.ghosts ?? [])];

    return (
      <AbsoluteFill
        style={{
          opacity,
          transform: transforms || undefined,
          transformOrigin,
          filter: filters || undefined,
          clipPath,
          maskImage,
          WebkitMaskImage: maskImage,
        }}
      >
        {children}
        {ghosts.map((g, i) => (
          <AbsoluteFill
            key={i}
            style={{
              transform: g.transform,
              filter: g.filter,
              opacity: g.opacity,
              mixBlendMode: "screen",
              pointerEvents: "none",
            }}
          >
            {children}
          </AbsoluteFill>
        ))}
        {enterVis.overlay}
        {exitVis.overlay}
      </AbsoluteFill>
    );
  }

  // ── Legacy path (unchanged behavior) ─────────────────────────────────────
  let activeStyle = transitionStyle;
  if (sceneIndex !== undefined && transitionStyle !== "none") {
    const roll = ((seed * 2654435761 + sceneIndex * 7 + 3) >>> 0) % 3;
    activeStyle = roll === 2 ? COMPANION[transitionStyle] : transitionStyle;
  }

  if (activeStyle === "none") {
    return <AbsoluteFill>{children}</AbsoluteFill>;
  }

  // ── CROSSFADE (with a gentle settle-in) ──────────────────────────────
  if (activeStyle === "crossfade") {
    const opacity = enterT * (1 - exitT);
    const scale = (1 + 0.03 * (1 - enterT)) * (1 - 0.015 * exitT);
    return (
      <AbsoluteFill style={{ opacity, transform: `scale(${scale})` }}>
        {children}
      </AbsoluteFill>
    );
  }

  // ── SLIDE-LEFT (motion carries the cut; opacity resolves early) ──────
  if (activeStyle === "slide-left") {
    const translateX = (1 - enterT) * 100 - exitT * 100;
    const skewX = -2.5 * (1 - enterT) + 2.5 * exitT;
    const opacity =
      interpolate(enterT, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }) *
      (1 - interpolate(exitT, [0.5, 1], [0, 1], { extrapolateLeft: "clamp" }));
    return (
      <AbsoluteFill
        style={{ transform: `translateX(${translateX}%) skewX(${skewX}deg)`, opacity }}
      >
        {children}
      </AbsoluteFill>
    );
  }

  // ── ZOOM-THROUGH (brightness pulse sells the punch-in) ───────────────
  if (activeStyle === "zoom-through") {
    const scale = (0.75 + 0.25 * enterT) * (1 + 0.5 * exitT);
    const brightness = 1 + 0.3 * (1 - enterT) + 0.35 * exitT;
    const opacity =
      interpolate(enterT, [0, 0.55], [0, 1], { extrapolateRight: "clamp" }) *
      (1 - interpolate(exitT, [0.45, 1], [0, 1], { extrapolateLeft: "clamp" }));
    return (
      <AbsoluteFill
        style={{
          transform: `scale(${scale})`,
          opacity,
          filter: `brightness(${brightness})`,
        }}
      >
        {children}
      </AbsoluteFill>
    );
  }

  // ── GLITCH-CUT (burst decays instead of re-rolling at full amplitude) ─
  if (activeStyle === "glitch-cut") {
    const glitchFrames = 5;
    const enterBurst = frame < glitchFrames;
    const exitBurst = frame > durationInFrames - glitchFrames;

    if (enterBurst || exitBurst) {
      return (
        <GlitchBurst
          frame={frame}
          durationInFrames={durationInFrames}
          seed={seed}
          entering={enterBurst}
        >
          {children}
        </GlitchBurst>
      );
    }

    // Ramp brightness back over 3 frames after the burst instead of an
    // unramped hard snap to clean.
    const settle = interpolate(
      frame,
      [glitchFrames, glitchFrames + 3],
      [1.12, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.quad) }
    );
    return (
      <AbsoluteFill style={{ filter: settle !== 1 ? `brightness(${settle})` : undefined }}>
        {children}
      </AbsoluteFill>
    );
  }

  // ── WIPE-DOWN (diagonal clip reveal in; quick fade out) ──────────────
  if (activeStyle === "wipe-down") {
    const p = enterT * 200;
    const isFullyRevealed = enterT >= 1;
    const clipPath = isFullyRevealed
      ? "none"
      : `polygon(0 0, ${Math.min(p, 100)}% 0, ${Math.min(p, 100)}% ${Math.min(p, 100)}%, 0 ${Math.min(p, 100)}%)`;
    const opacity = 1 - exitT;

    return (
      <AbsoluteFill style={{ clipPath, opacity }}>
        {children}
        {!isFullyRevealed && (
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: `linear-gradient(135deg, transparent ${Math.max(0, enterT * 100 - 5)}%, rgba(255,255,255,0.3) ${enterT * 100}%, transparent ${enterT * 100 + 2}%)`,
              pointerEvents: "none",
            }}
          />
        )}
      </AbsoluteFill>
    );
  }

  // ── IRIS-OPEN (circular reveal in; quick fade out) ───────────────────
  if (activeStyle === "iris-open") {
    const radius = enterT * 100;
    const clip = radius >= 100 ? "none" : `circle(${radius}% at 50% 50%)`;
    const opacity = 1 - exitT;
    return (
      <AbsoluteFill style={{ clipPath: clip, opacity }}>{children}</AbsoluteFill>
    );
  }

  // ── BLUR-DISSOLVE (focus pull) ───────────────────────────────────────
  if (activeStyle === "blur-dissolve") {
    const blur = 10 * (1 - enterT) + 10 * exitT;
    const opacity =
      interpolate(enterT, [0, 0.8], [0, 1], { extrapolateRight: "clamp" }) *
      (1 - interpolate(exitT, [0.3, 1], [0, 1], { extrapolateLeft: "clamp" }));
    return (
      <AbsoluteFill style={{ filter: `blur(${blur}px)`, opacity }}>
        {children}
      </AbsoluteFill>
    );
  }

  // ── SCALE-ROTATE (cinematic spin entrance) ───────────────────────────
  if (activeStyle === "scale-rotate") {
    const scale = (0.7 + 0.3 * enterT) * (1 - 0.1 * exitT);
    const rotate = -6 * (1 - enterT) + 6 * exitT;
    const opacity =
      interpolate(enterT, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }) *
      (1 - interpolate(exitT, [0.5, 1], [0, 1], { extrapolateLeft: "clamp" }));
    return (
      <AbsoluteFill
        style={{ transform: `scale(${scale}) rotate(${rotate}deg)`, opacity }}
      >
        {children}
      </AbsoluteFill>
    );
  }

  // ── PUSH-UP (scene pushes up from below, exits upward) ───────────────
  if (activeStyle === "push-up") {
    const translateY = (1 - enterT) * 100 - exitT * 100;
    const opacity =
      interpolate(enterT, [0, 0.5], [0.3, 1], { extrapolateRight: "clamp" }) *
      (1 - interpolate(exitT, [0.4, 1], [0, 0.7], { extrapolateLeft: "clamp" }));
    return (
      <AbsoluteFill style={{ transform: `translateY(${translateY}%)`, opacity }}>
        {children}
      </AbsoluteFill>
    );
  }

  // ── SPIN-BLUR (motion-blurred rotation entrance) ─────────────────────
  if (activeStyle === "spin-blur") {
    const rotate = -10 * (1 - enterT) + 10 * exitT;
    const scale = (1.2 - 0.2 * enterT) * (1 + 0.2 * exitT);
    const blur = 8 * (1 - enterT) + 8 * exitT;
    const opacity =
      interpolate(enterT, [0, 0.5], [0, 1], { extrapolateRight: "clamp" }) *
      (1 - interpolate(exitT, [0.5, 1], [0, 1], { extrapolateLeft: "clamp" }));
    return (
      <AbsoluteFill
        style={{
          transform: `rotate(${rotate}deg) scale(${scale})`,
          filter: `blur(${blur}px)`,
          opacity,
        }}
      >
        {children}
      </AbsoluteFill>
    );
  }

  // Fallback: just render children
  return <AbsoluteFill>{children}</AbsoluteFill>;
};

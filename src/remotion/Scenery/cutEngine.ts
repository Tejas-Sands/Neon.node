// ============================================================================
// cutEngine.ts — Seeded long-take planner for the Artistic Scenery branch
// (10-20s calm, contemplative scenery films).
// ----------------------------------------------------------------------------
// The whole edit is planned here as pure data so the component just renders
// segments. Structure of every film (the "settle in and breathe" arc):
//
//   OPEN    one long establishing take, fading in from black
//   WANDER  a handful of long takes joined by slow dissolves
//   HOLD    the final take settles while the overlay line reveals
//
// Every take drifts slowly in ONE direction (gentle Ken Burns) — no whips,
// no strobe bursts, no beat grid, no back-and-forth. Cuts are always slow
// dissolves, never hard.
//
// Pure function of (seed, clips, duration, mood) — mulberry32 PRNG, no
// Math.random / Date.now — safe under Remotion's frame-parallel renderer.
// Same seed -> same edit, forever (same contract as MyComp/looks.ts).
// ============================================================================

import { makeRng } from "../MyComp/looks";

export type SceneryMood = "ethereal" | "epic" | "serene" | "electric";

export type CutStyle = "fade-in" | "dissolve";

export interface MontageClip {
  kind: "video" | "image";
  durationSec?: number;
}

export interface MontageSegment {
  clipIndex: number;
  /** Composition frame the segment starts at (dissolve overlap included). */
  start: number;
  dur: number;
  /** How this segment ENTERS. */
  enter: CutStyle;
  /** Dissolve length in frames (0 for the opening take). */
  xfade: number;
  zoomFrom: number;
  zoomTo: number;
  panX: number;
  panY: number;
  mirror: boolean;
  /** Trim offset (seconds) into the source clip; 0 for images/unknown length. */
  startFromSec: number;
  /** True for the final long take that carries the text reveal. */
  isHold: boolean;
}

export interface MontagePlan {
  segments: MontageSegment[];
  /** Frame where the final hold is fully on screen (text reveal timing). */
  holdStart: number;
}

// Average take length (seconds) per mood. EVERY mood is calm now — mood only
// nudges the pace: serene lingers longest, electric wanders a little quicker.
const MOOD_SHOT_SEC: Record<SceneryMood, number> = {
  serene: 4.4,
  ethereal: 4.0,
  epic: 3.6,
  electric: 3.2,
};

export function deriveMontage(
  seed: number,
  clips: MontageClip[],
  totalFrames: number,
  mood: SceneryMood,
  fps: number,
): MontagePlan {
  const rng = makeRng(((seed ^ 0x5ce7e12b) >>> 0) || 1);
  const clipCount = Math.max(1, clips.length);

  // Slow dissolve joining every pair of takes.
  const xfade = Math.round(0.8 * fps);
  const minShot = Math.round(2.2 * fps);

  // --- Final hold: ~30% of the film, clamped 3.2-4.5s — room to read the line.
  const hold = Math.min(
    Math.max(Math.round(totalFrames * 0.3), Math.round(3.2 * fps)),
    Math.round(4.5 * fps),
  );

  // --- Pre-hold takes: near-equal long shots around the mood's pace, with a
  // touch of seeded give-and-take between neighbours so the rhythm feels
  // breathed rather than metronomic. Lengths always sum EXACTLY to totalFrames.
  const rest = totalFrames - hold;
  const target = Math.round(MOOD_SHOT_SEC[mood] * fps * (0.94 + rng() * 0.12));
  const takes = Math.max(1, Math.round(rest / target));
  const base = Math.floor(rest / takes);
  const lengths = Array.from({ length: takes }, (_, i) => base + (i < rest - base * takes ? 1 : 0));
  for (let i = 0; i + 1 < takes; i++) {
    const delta = Math.round((rng() - 0.5) * 0.5 * fps);
    if (lengths[i] - delta >= minShot && lengths[i + 1] + delta >= minShot) {
      lengths[i] -= delta;
      lengths[i + 1] += delta;
    }
  }

  // --- Clip order: seeded shuffle, cycled. The hold prefers a VIDEO clip —
  // real motion under the settling text beats a frozen still.
  const order = clips.map((_, i) => i);
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  // Prefer a video that can actually COVER the hold; a clip that runs out
  // freeze-frames under the settling text.
  const holdSecNeeded = (hold + xfade) / fps + 0.3;
  const longVideo = order.find(
    (i) => clips[i].kind === "video" && (clips[i].durationSec ?? 0) >= holdSecNeeded,
  );
  const firstVideo = order.find((i) => clips[i].kind === "video");
  const holdClip = longVideo ?? firstVideo ?? order[0];

  const takenSoFar: Record<number, number> = {}; // per-clip trim cursor (sec)
  const trimFor = (clipIndex: number, durFrames: number): number => {
    const clip = clips[clipIndex];
    if (clip.kind !== "video" || !clip.durationSec) return 0;
    const segSec = durFrames / fps;
    const maxStart = Math.max(0, clip.durationSec - segSec - 0.3);
    if (maxStart <= 0) return 0;
    // Walk forward through the clip on re-use so repeated appearances show
    // DIFFERENT frames — a re-used clip must never read as a repeated shot.
    const cursor = takenSoFar[clipIndex] ?? rng() * maxStart * 0.5;
    const start = Math.min(cursor, maxStart);
    takenSoFar[clipIndex] = start + segSec + 0.2;
    return Math.round(start * 100) / 100;
  };

  let orderPos = 0;
  const nextClip = (): number => {
    let idx = order[orderPos % order.length];
    orderPos++;
    // Don't burn the hold's clip mid-film when we have enough others.
    if (clipCount > 2 && idx === holdClip) {
      idx = order[orderPos % order.length];
      orderPos++;
    }
    return idx;
  };

  const segments: MontageSegment[] = [];
  let cut = 0;
  const allTakes = [...lengths, hold];
  allTakes.forEach((len, i) => {
    const isFirst = i === 0;
    const isHold = i === allTakes.length - 1;
    const clipIndex = isHold ? holdClip : nextClip();
    // Dissolving takes start xfade frames early and sit ON TOP of the previous
    // take while they fade in, reaching full opacity exactly as it unmounts.
    const start = isFirst ? 0 : cut - xfade;
    const dur = isFirst ? len : len + xfade;

    // One slow drift per take: push in OR ease out, pan one direction only.
    // Zoom never dips below 1.05 so pans can never expose a frame edge.
    const pushIn = rng() > 0.4;
    const zNear = 1.05 + rng() * 0.03;
    const zFar = zNear + 0.04 + rng() * 0.03;
    segments.push({
      clipIndex,
      start,
      dur,
      enter: isFirst ? "fade-in" : "dissolve",
      xfade: isFirst ? 0 : xfade,
      zoomFrom: isHold ? 1.08 : pushIn ? zNear : zFar,
      zoomTo: isHold ? 1.03 : pushIn ? zFar : zNear,
      panX: isHold ? 0 : Math.round((rng() - 0.5) * 40),
      panY: isHold ? 0 : Math.round((rng() - 0.5) * 52),
      mirror: isHold ? false : rng() < 0.12,
      startFromSec: trimFor(clipIndex, dur),
      isHold,
    });
    cut += len;
  });

  return { segments, holdStart: totalFrames - hold };
}

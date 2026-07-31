// ============================================================================
// energy.ts — the per-scene ENERGY SCHEDULE (comprehension-first kinetics)
// ----------------------------------------------------------------------------
// The design brief's organizing principle: "energy is a schedule, not a level."
// look.motion gives every video ONE personality; this module turns it into a
// per-scene, per-beat schedule — kinetic between reading moments, calm while a
// headline lands, dead still on the final scene — so motion buys attention
// without ever competing with reading.
//
// Consumers (Main.tsx): camera-transform intensity, spring stiffness, hero
// title drift / text parallax gates, ShapeAccents freeze on the still scene,
// mid-scene b-roll cut placement (BackgroundLayer), micro-detail timing, and
// the PolishStack grain/pulse freeze.
//
// Determinism: independent RNG stream `seed ^ 0x6d1b9f37` (mulberry32 — the
// other streams are raw seed / 0x7f4a7c15 finish / 0x9e3779b9 polish /
// 0x3d9f2b6e prism / 0x51ed270b cutplan). polish.ts draw discipline: a FIXED
// number of draws per scene, all consumed unconditionally BEFORE any gate, so
// adding future gates can never reshuffle existing seeds' schedules.
// ============================================================================

import { makeRng } from "./looks";

export interface SceneEnergy {
  /** 0..1 scene energy — micro-details and accents key off this. */
  level: number;
  /** Multiplier on the camera-transform deltas (0 = locked-off frame). */
  camera: number;
  /** Scene-local frame where the text-landing (reading) beat ends. */
  landEnd: number;
  /** Scene-local frame from which mid-scene events (cuts, sweeps) may fire. */
  kineticStart: number;
  /** May this scene take a mid-scene b-roll switch (needs a 2nd clip too). */
  allowMidCut: boolean;
  /** Scene-local frame of the b-roll switch, inside the kinetic window.
   *  Always >= 50% of the scene — Part A guarantees clip B covers that. */
  midCutFrame: number;
  /** 0.85..1.15 multiplier composed onto look.springMul per scene. */
  springScale: number;
  /** Dead-still scene (final only): camera locked, decoration frozen. */
  still: boolean;
}

export interface EnergyPlan {
  scenes: SceneEnergy[];
  /** Convenience copy of scenes[].level for cross-scene consumers. */
  levels: number[];
}

/**
 * Derive the video's energy schedule.
 *
 * Shape: scene 0 is distinct but CALMER than the body (the hook type must land
 * clean — Q19b); body scenes alternate medium/high with at least one high scene
 * per three (Q8c "medium-high, layered"); the final scene is dead still (Q9b) —
 * a held frame is the strongest close a kinetic feed can make.
 */
export function deriveEnergy(
  seed: number,
  sceneCount: number,
  sceneDurations: number[],
): EnergyPlan {
  const rng = makeRng(((seed ^ 0x6d1b9f37) >>> 0) || 1);

  const scenes: SceneEnergy[] = [];
  for (let i = 0; i < sceneCount; i++) {
    // Fixed draws per scene — consumed even where a role overrides the value.
    const levelRoll = rng();
    const cutRoll = rng();

    const D = Math.max(1, Math.round(sceneDurations[i] ?? 150));
    const isHook = i === 0;
    const isStill = sceneCount > 1 && i === sceneCount - 1;

    let level: number;
    if (isStill) level = 0;
    else if (isHook) level = 0.45 + levelRoll * 0.1;
    else level = 0.55 + levelRoll * 0.35;

    // Reading beats. landEnd covers the entrance springs (READ_LOCK is 18
    // frames; +8 of settle); the kinetic window opens at half the scene so
    // Part A's "clip B covers >= 50%" contract holds by construction.
    const landEnd = Math.min(26, Math.round(D * 0.25));
    const kineticStart = Math.max(landEnd + 12, Math.round(D * 0.5));
    const cutSlack = Math.max(1, D - 12 - kineticStart - 12);
    const midCutFrame = Math.max(40, kineticStart + Math.floor(cutRoll * cutSlack));

    scenes.push({
      level,
      camera: isStill ? 0 : isHook ? 0.8 : 0.7 + 0.5 * level,
      landEnd,
      kineticStart,
      allowMidCut: !isHook && !isStill && level >= 0.55 && D >= 100,
      midCutFrame: Math.min(midCutFrame, Math.max(kineticStart, D - 12)),
      // Hook stays at 1 so frame-2 readability is bit-comparable to before.
      springScale: isHook ? 1 : isStill ? 0.9 : 0.85 + 0.3 * level,
      still: isStill,
    });
  }

  // Guarantee at least one HIGH scene per body triple — a video whose rolls
  // all land mid gets one deliberate spike instead of a flat medium hum.
  const bodyIdx = scenes
    .map((_, i) => i)
    .filter((i) => !scenes[i].still && i > 0);
  for (let g = 0; g < bodyIdx.length; g += 3) {
    const triple = bodyIdx.slice(g, g + 3);
    if (triple.length === 0 || triple.some((i) => scenes[i].level >= 0.8)) continue;
    const top = triple.reduce((a, b) => (scenes[b].level > scenes[a].level ? b : a));
    const s = scenes[top];
    s.level = 0.82;
    s.camera = 0.7 + 0.5 * s.level;
    s.springScale = 0.85 + 0.3 * s.level;
    s.allowMidCut = s.allowMidCut || (Math.round(sceneDurations[top] ?? 150) >= 100);
  }

  return { scenes, levels: scenes.map((s) => s.level) };
}

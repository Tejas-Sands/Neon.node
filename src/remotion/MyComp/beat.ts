// ============================================================================
// beat.ts — music beat grid for accent quantization (brief Q34: answer b —
// "accents pulse to the beat, cuts stay free")
// ----------------------------------------------------------------------------
// Scene BOUNDARIES are never moved (they belong to narration timing); what
// snaps to the grid are the ACCENT moments inside a scene — energy.ts's
// kineticStart / midCutFrame and PolishStack's pulse period — so sweeps,
// b-roll switches and glow pulses land on the music instead of beside it.
//
// BPM values are measured, not guessed: full-length spectral-flux
// autocorrelation over the exact files main.py downloads (SoundHelix songs
// 1/2/4 → public/<track>.mp3), measured 2026-08-02: 68.0 / 73.8 / 71.8.
// The tracks are 300-430s — far longer than any ≤60s video and the <Audio>
// loop never restarts mid-video, so ONE grid anchored at frame 0 is valid
// for the whole composition.
//
// No RNG, no draws — pure arithmetic, so composing this into energy.ts
// cannot reshuffle any seed's schedule (absent beatFrames ⇒ bit-identical).
// ============================================================================

export const MUSIC_BPM: Record<string, number> = {
  "ambient-tech": 68,
  "lofi-chill": 74,
  "cosmic-synth": 72,
};

/** Frames per beat for a track, or undefined when there is no grid
 * ("none", unknown track). */
export const framesPerBeat = (
  musicTrack: string | undefined,
  fps: number,
): number | undefined => {
  const bpm = musicTrack ? MUSIC_BPM[musicTrack] : undefined;
  return bpm ? (fps * 60) / bpm : undefined;
};

/** Snap an ABSOLUTE frame to the nearest beat of a frame-0-anchored grid. */
export const quantizeToBeat = (absFrame: number, fpb: number): number =>
  Math.round(absFrame / fpb) * fpb;

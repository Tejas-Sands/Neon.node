import { loadFont as loadSpaceGrotesk } from "@remotion/google-fonts/SpaceGrotesk";
import { loadFont as loadJetBrains } from "@remotion/google-fonts/JetBrainsMono";

// ---------------------------------------------------------------------------
// Persistent-chrome typography — the account's cross-video signature.
//
// Display faces vary per video (STYLE_PACKS pick fontFamilyName), but
// everything that repeats on every post — watermark, FollowChip, source
// chip, HUD micro-text, outro handle — is set in ONE fixed family so the
// account is recognizable at a glance regardless of the video's look.
//
// Weight lists are the ONLY real weights available at render time; asking
// for any other weight makes Chrome synthesize it (fuzzy strokes at 1080px
// — see the faux-bold rule in AnimatedText.tsx). Never hardcode weights in
// chrome components; read them from here.
// ---------------------------------------------------------------------------
const spaceGrotesk = loadSpaceGrotesk("normal", {
  subsets: ["latin"],
  weights: ["500", "700"],
});
const jetBrains = loadJetBrains("normal", {
  subsets: ["latin"],
  weights: ["500", "700"],
});

/** Brand chrome face: quiet UI text at 500, emphasis (kickers, CTAs) at 700. */
export const BRAND = {
  family: spaceGrotesk.fontFamily,
  chromeWeight: 500,
  strongWeight: 700,
} as const;

/** Diegetic UI / timecode / telemetry chrome (HUD readouts, URL bars). */
export const BRAND_MONO = {
  family: jetBrains.fontFamily,
  weight: 500,
  strongWeight: 700,
} as const;

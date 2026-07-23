import { z } from "zod";

export const COMP_NAME = "MyComp";

export const SceneSchema = z.object({
  imageUrl: z.string(),
  /**
   * Optional stock video clip (relative public/ path or absolute URL) used as
   * the scene background instead of imageUrl. Set by the backend for the
   * opening hook scene — motion in the first frame protects the Instagram
   * 3-second-hold ranking signal. imageUrl remains the fallback.
   */
  videoUrl: z.string().optional(),
  text: z.string(),
  durationInFrames: z.number(),
  type: z
    .enum([
      "hero",
      "testimonial",
      "metric",
      "split",
      "countdown",
      "comparison",
      "list",
      "cta",
      "outro",
      // Data-driven scene types (article: animated charts / ratings / UI demos).
      // All degrade gracefully to a plain scene when their data is absent, so
      // adding them never breaks an existing render path.
      "bar-chart",
      "chart",
      "line-chart",
      "rating",
      "ui-demo",
    ])
    .optional(),
  title: z.string().optional(),
  subtitle: z.string().optional(),
  secondaryText: z.string().optional(),
  extraImages: z.array(z.string()).optional(),
  extraItems: z.array(z.string()).optional(),
  numberVal: z.number().optional(),
  urlVal: z.string().optional(),
  textAnimation: z
    .enum([
      "typewriter",
      "glitch-decode",
      "fade-up",
      "slide-in",
      "word-by-word",
      "scale-pop",
      "blur-in",
      "wave",
      "none",
    ])
    .optional(),
  // Comparison scene fields
  leftLabel: z.string().optional(),
  rightLabel: z.string().optional(),
  // List scene fields
  listItems: z.array(z.string()).optional(),
  // Countdown scene fields
  countFrom: z.number().optional(),
  countTo: z.number().optional(),
  countSuffix: z.string().optional(),
  // CTA scene fields
  ctaText: z.string().optional(),
  // Data-driven scene fields (bar-chart / chart / line-chart / rating).
  // Optional so every existing scene stays valid without them.
  chartData: z
    .array(z.object({ label: z.string(), value: z.number() }))
    .optional(),
  ratingValue: z.number().optional(),
  ratingMax: z.number().optional(),
});

export const ThemeSchema = z.object({
  primaryColor: z.string(),
  secondaryColor: z.string(),
  overlayType: z.enum([
    "grid-hud",
    "particles",
    "clean",
    "vhs-glitch",
    "fantasy-sparks",
    "aurora",
  ]),
  fontFamilyName: z.enum([
    "Share Tech Mono",
    "Orbitron",
    "Inter",
    "Playfair Display",
    "Courier New",
  ]),
  musicTrack: z
    .enum(["ambient-tech", "lofi-chill", "cosmic-synth", "none"])
    .default("none"),
  cameraMotion: z
    .enum([
      "ken-burns",
      "pan-horizontal",
      "zoom-slow",
      "static",
      "dynamic-zoom-rotate",
      "pan-tilt",
      "pulse-zoom",
      "glitch-shift",
      "orbit-drift",
      "vertigo",
    ])
    .default("ken-burns"),
  subtitlePosition: z.enum(["top", "center", "bottom"]).default("bottom"),
  overlayOpacity: z.number().min(0).max(1).default(1),
  transitionStyle: z
    .enum([
      "crossfade",
      "slide-left",
      "zoom-through",
      "glitch-cut",
      "wipe-down",
      "iris-open",
      "blur-dissolve",
      "scale-rotate",
      "push-up",
      "spin-blur",
      "none",
    ])
    .default("crossfade"),
  aspectRatio: z.enum(["9:16", "16:9", "1:1", "4:5"]).default("9:16"),
  gradientOverlay: z
    .enum(["none", "top-to-bottom", "radial-center", "diagonal"])
    .default("none"),
  /**
   * Per-video randomness seed. Propagated from the Python backend
   * (derived from session_id) so every video gets a unique — but fully
   * deterministic and render-safe — sequence of transitions, camera
   * moves, shape motion and text animations. Optional for backwards
   * compatibility; falls back to 0 when absent.
   */
  seed: z.number().optional(),
});

export const PipelineSchema = z
  .object({
    outputFormat: z.enum(["mp4", "webm", "gif"]).default("mp4"),
    quality: z.enum(["draft", "standard", "high"]).default("standard"),
    watermark: z.string().optional(),
    webhookUrl: z.string().url().optional(),
    callbackId: z.string().optional(),
    priority: z.enum(["low", "normal", "urgent"]).default("normal"),
  })
  .optional();

export const SubtitleWordSchema = z.object({
  text: z.string(),
  start: z.number(), // in seconds
  end: z.number(),   // in seconds
});

export const CompositionProps = z.object({
  scenes: z.array(SceneSchema),
  theme: ThemeSchema.optional(),
  pipeline: PipelineSchema.optional(),
  voiceoverUrl: z.string().optional(),
  subtitles: z.array(SubtitleWordSchema).optional(),
});

// ============================================================================
// Artistic Scenery branch — 10-20s fast-cut montage of breathtaking scenery.
// Separate schema on purpose: the montage is clip-driven and beat-timed, not
// narration-driven, so forcing it through SceneSchema (whose durations get
// overwritten by TTS) would fight the format. Rendered by the ArtisticScenery
// composition; props are produced by generate_scenery.py.
// ============================================================================
export const SCENERY_COMP_NAME = "ArtisticScenery";

export const SceneryClipSchema = z.object({
  /** Relative public/ path (resolved via staticFile) or absolute URL. */
  src: z.string(),
  kind: z.enum(["video", "image"]),
  /**
   * Source clip length in seconds (from the stock API), video only. Lets the
   * cut engine trim into a clip (startFrom) without ever running off its end.
   */
  durationSec: z.number().optional(),
});

export const SceneryMoodSchema = z.enum(["ethereal", "epic", "serene", "electric"]);

export const SceneryProps = z.object({
  clips: z.array(SceneryClipSchema),
  /** The single poetic overlay line shown on the final hold. Never word-split. */
  overlayLine: z.string().default(""),
  /** Small label under the overlay line — the real, named place. */
  placeName: z.string().default(""),
  musicTrack: z
    .enum(["calm-piano", "floating-cities", "healing-ambient", "dreamy-flashback", "none"])
    .default("calm-piano"),
  mood: SceneryMoodSchema.default("epic"),
  /** Total montage length, decided by the backend (10-20s → 300-600 @ 30fps). */
  durationInFrames: z.number().default(450),
  /** Per-video seed (from session_id) driving the whole cut plan. */
  seed: z.number().default(0),
});

export const defaultSceneryProps: z.infer<typeof SceneryProps> = {
  clips: [
    { src: "https://images.unsplash.com/photo-1519681393784-d120267933ba?q=80&w=1080&auto=format&fit=crop", kind: "image" },
    { src: "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?q=80&w=1080&auto=format&fit=crop", kind: "image" },
    { src: "https://images.unsplash.com/photo-1441974231531-c6227db76b6e?q=80&w=1080&auto=format&fit=crop", kind: "image" },
    { src: "https://images.unsplash.com/photo-1470071459604-3b5ec3a7fe05?q=80&w=1080&auto=format&fit=crop", kind: "image" },
    { src: "https://images.unsplash.com/photo-1472214103451-9374bd1c798e?q=80&w=1080&auto=format&fit=crop", kind: "image" },
  ],
  overlayLine: "Earth, unedited",
  placeName: "Lofoten, Norway",
  musicTrack: "calm-piano",
  mood: "epic",
  durationInFrames: 450,
  seed: 0,
};

// Aspect ratio → pixel dimension mapping
export const ASPECT_RATIO_MAP: Record<string, { width: number; height: number }> = {
  "9:16": { width: 1080, height: 1920 },
  "16:9": { width: 1920, height: 1080 },
  "1:1": { width: 1080, height: 1080 },
  "4:5": { width: 1080, height: 1350 },
};

export const defaultMyCompProps: z.infer<typeof CompositionProps> = {
  scenes: [
    {
      imageUrl:
        "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?q=80&w=600&auto=format&fit=crop",
      text: "BOOTING NEURAL NET...",
      durationInFrames: 175,
    },
    {
      imageUrl:
        "https://images.unsplash.com/photo-1508739773434-c26b3d09e071?q=80&w=600&auto=format&fit=crop",
      text: "SCANNING SECTOR 04...",
      durationInFrames: 175,
    },
    {
      imageUrl:
        "https://images.unsplash.com/photo-1515621061946-eff1c2a352bd?q=80&w=600&auto=format&fit=crop",
      text: "CONNECTION SECURE",
      durationInFrames: 175,
    },
    {
      imageUrl:
        "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?q=80&w=600&auto=format&fit=crop",
      text: "ACCESS GRANTED",
      durationInFrames: 175,
    },
    {
      imageUrl:
        "https://images.unsplash.com/photo-1478760329108-5c3ed9d495a0?q=80&w=600&auto=format&fit=crop",
      text: "DOWNLOADING DATA...",
      durationInFrames: 175,
    },
    {
      imageUrl:
        "https://images.unsplash.com/photo-1518770660439-4636190af475?q=80&w=600&auto=format&fit=crop",
      text: "SYSTEM ONLINE",
      durationInFrames: 175,
    },
  ],
  theme: {
    primaryColor: "#00f0ff",
    secondaryColor: "#ff007f",
    overlayType: "grid-hud",
    fontFamilyName: "Share Tech Mono",
    musicTrack: "none",
    cameraMotion: "ken-burns",
    subtitlePosition: "bottom",
    overlayOpacity: 1,
    transitionStyle: "crossfade",
    aspectRatio: "9:16",
    gradientOverlay: "none",
  },
};

export const DURATION_IN_FRAMES = 1050;
export const VIDEO_WIDTH = 1080;
export const VIDEO_HEIGHT = 1920;
export const VIDEO_FPS = 30;

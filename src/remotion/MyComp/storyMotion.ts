/** Render-only story direction. No new props, assets, clocks or RNG draws. */
export interface StoryScene {
  type?: string;
  text: string;
  title?: string;
  subtitle?: string;
  secondaryText?: string;
  leftLabel?: string;
  rightLabel?: string;
  durationInFrames?: number;
}
export interface StoryBeat {
  kind: "legacy" | "statement" | "metric" | "comparison" | "compression";
  revealFrame: number;
  synced: boolean;
}
export const storyCutStyle = <T extends string>(style: T, a: StoryScene, b: StoryScene, before: StoryBeat, after: StoryBeat): T | "none" =>
  before.kind !== "legacy" && after.kind !== "legacy" && (sharedSubject(a, b) || sharedMetric(a, b)) ? "none" : style;
export const storyMusicVolume = (frame: number, revealFrame: number): number => {
  const distance = frame - revealFrame;
  const dip = distance < 0 ? Math.max(0, 1 + distance / 12) : Math.max(0, 1 - distance / 18);
  return 0.09 + 0.11 * (1 - dip);
};
export function deriveStoryMotion(
  scenes: StoryScene[],
  words: {text: string; start: number; end: number}[] | undefined,
  energy: {kineticStart: number; landEnd: number; still: boolean}[],
  fps: number,
  pack?: string,
  enabled = true,
): StoryBeat[] {
  let sceneStart = 0;
  return scenes.map((scene, i) => {
    const duration = Math.max(1, scene.durationInFrames ?? 150);
    const start = sceneStart;
    sceneStart += duration;
    const lastReveal = Math.max(0, duration - 25);
    const earliest = Math.max(energy[i]?.landEnd ?? 26, energy[i]?.kineticStart ?? duration / 2);
    const fallback = Math.min(lastReveal, Math.round(earliest));
    const beat: StoryBeat = {kind: "legacy", revealFrame: fallback, synced: false};
    const copy = [scene.title, scene.text, scene.subtitle, scene.secondaryText, scene.leftLabel, scene.rightLabel].filter(Boolean).join(" ");
    // Long/unsupported layouts and formats keep their tested renderers. In
    // particular: no quiz answer leak, no ranking reveal early, no new outro.
    if (!enabled || i === 0 || i === scenes.length - 1 || energy[i]?.still ||
        pack === "quiz-reveal" || pack === "data-rankings" ||
        copy.length > 220 || copy.split(/\s+/).some(word => word.length > 30) ||
        (scene.title?.length ?? 0) > 54 || (scene.leftLabel?.length ?? 0) > 40 || (scene.rightLabel?.length ?? 0) > 40 ||
        !scene.text.trim() || earliest > lastReveal) return beat;
    if (scene.type === "metric") beat.kind = "metric";
    else if (scene.type === "comparison" && (scene.secondaryText || scene.subtitle)) beat.kind = "comparison";
    else if (!scene.type || scene.type === "split") {
      beat.kind = "statement";
      // ponytail: precision-first English heuristic, not a mechanism parser.
      // Only illustrate an explicit compression claim; everything else stays
      // typographic. A future grounded storyboard can cover other mechanisms.
      if (/\b(compress(?:es|ed|ion|ing)?|quantiz(?:ation|ed|ing))\b/i.test(copy) &&
          /\b(memory|weights|model|storage|data)\b/i.test(copy) &&
          !/\b(no|not|never|without|cannot|\w+n['’]t|uncompressed)\b/i.test(copy)) {
        beat.kind = "compression";
      }
    }
    if (beat.kind === "legacy") return beat;

    const localWords = (words ?? []).filter(w => Number.isFinite(w.start) && Number.isFinite(w.end) &&
      w.end >= w.start && w.start * fps >= start && w.start * fps < start + duration);
    const targets = tokens(beat.kind === "comparison" ? (scene.secondaryText || scene.subtitle || "") : copy);
    const number = scene.text.match(/(?:^|\s|[$€£])(-?\d[\d,]*(?:\.\d+)?)/)?.[1].replace(/,/g, "");
    const spokenNumber = number === undefined ? undefined : numberPhrase(Number(number));
    for (let n = 0; n < localWords.length; n++) {
      const word = localWords[n];
      const localFrame = Math.round(word.start * fps - start);
      if (localFrame < earliest || localFrame > lastReveal) continue;
      const token = normalize(word.text);
      const phrase = localWords.slice(n, n + 6).map(w => normalize(w.text)).join(" ");
      const spokenMatch = spokenNumber !== undefined && (phrase === spokenNumber ||
        (phrase.startsWith(spokenNumber + " ") &&
          !/^(zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|point|and)\b/.test(phrase.slice(spokenNumber.length + 1))));
      const numericMatch = number !== undefined && (token === number || spokenMatch);
      const match = beat.kind === "metric" ? numericMatch : beat.kind === "compression"
        ? /^(compress(?:es|ed|ion|ing)?|quantiz(?:ation|ed|ing))$/.test(token)
        : targets.includes(token) && token.length >= 5;
      if (match) return {...beat, revealFrame: localFrame, synced: true};
    }
    return beat;
  });
}

const normalize = (text: string): string => text.toLowerCase().replace(/[,]/g, "").replace(/[^a-z0-9.\s-]/g, "").replace(/-/g, " ").trim().replace(/^\.+|\.+$/g, "");
export const fitStoryFont = (text: string, requested: number, width: number): number =>
  Math.max(28, Math.min(requested, Math.floor(width / (Math.max(1, ...text.split(/\s+/).map(w => w.length)) * 0.75))));
const STOP = new Set("this that these those with from your have into more less only than they their there what when which will just here uses using change changes everything before after modelled".split(" "));
const tokens = (text: string): string[] => normalize(text).split(/\s+/).filter(w => w.length >= 4 && !STOP.has(w));

/** Exact literal subject continuity, never an inferred entity or relationship. */
export const sharedSubject = (a: StoryScene, b: StoryScene): string | undefined => {
  const first = tokens(a.title || a.text)[0];
  const next = tokens(b.title || b.text)[0];
  return first && first === next && first.length <= 18 && !/\d/.test(first) ? first.toUpperCase() : undefined;
};

/** The transform settles exactly, so out-of-order frames and still holds agree. */
export const storyProgress = (frame: number, revealFrame: number, still: boolean): number => {
  if (still) return 1;
  const t = Math.min(1, Math.max(0, (frame - revealFrame) / 24));
  return 1 - (1 - t) ** 3;
};

/** Arrive, read, transform, then dock a repeated fact at the cut. No idle drift. */
export const storyStage = (frame: number, duration: number, cue: number,
  energy: {landEnd: number; kineticStart: number; still: boolean}) => {
  if (energy.still) return {enter: 1, reveal: 1, dock: 0};
  const ease = (start: number, length: number) => {
    const t = Math.min(1, Math.max(0, (frame - start) / Math.max(1, length)));
    return 1 - (1 - t) ** 3;
  };
  const revealAt = Math.max(energy.landEnd, energy.kineticStart, cue);
  // The last legal cue is duration-25. Docking then has its own 18-frame
  // window; waiting another 24 frames would strand the metric at the cut.
  const dockAt = Math.max(revealAt, duration - 19);
  return {enter: ease(0, Math.min(22, energy.landEnd)),
    reveal: ease(revealAt, 24), dock: ease(dockAt, duration - 1 - dockAt)};
};

/** Only carry an entire, literal metric, including its unit/sign. No inferred
 * equivalence (40% is not 40ms), and no arbitrary number pulled from prose. */
export const sharedMetric = (a: StoryScene, b: StoryScene): string | undefined => {
  if (b.type === "metric") return undefined;
  const value = a.text.trim();
  if (!/^[$€£]?[+-]?\d[\d,.]*(?:%|x|×|ms|GB|MB|TB|-bit)?$/.test(value)) return undefined;
  const next = [b.title, b.text, b.secondaryText, b.subtitle, b.leftLabel, b.rightLabel]
    .filter(Boolean).join(" ").split(/\s+/);
  return next.includes(value) ? value : undefined;
};

// Small exact speech matcher; unsupported decimals/large values use the safe
// kinetic-window fallback rather than guessing a word timestamp.
function numberPhrase(n: number): string | undefined {
  if (!Number.isInteger(n) || n < 0 || n >= 1000) return undefined;
  const small = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(" ");
  if (n < 20) return small[n];
  if (n < 100) return "zero ten twenty thirty forty fifty sixty seventy eighty ninety".split(" ")[Math.floor(n / 10)] + (n % 10 ? " " + small[n % 10] : "");
  return small[Math.floor(n / 100)] + " hundred" + (n % 100 ? " " + numberPhrase(n % 100) : "");
}

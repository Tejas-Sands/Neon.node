/** Run: tsc --module commonjs --target es2020 --esModuleInterop --skipLibCheck
 * --outDir /tmp/story-motion-check scripts/check-story-motion.ts &&
 * node /tmp/story-motion-check/scripts/check-story-motion.js */
import assert from "node:assert/strict";
import { deriveStoryMotion, storyProgress, sharedSubject, storyCutStyle, storyMusicVolume, fitStoryFont } from "../src/remotion/MyComp/storyMotion";

const scenes = [
  {type: "hero", text: "Memory has a price", durationInFrames: 120},
  {type: "split", title: "MODEL MEMORY", text: "Quantization compresses model weights", durationInFrames: 150},
  {type: "metric", title: "MODEL MEMORY", text: "40%", secondaryText: "Memory reduction", durationInFrames: 150},
  {type: "cta", text: "Read the benchmark", durationInFrames: 90},
];
const energy = scenes.map((_, i) => ({kineticStart: 75, landEnd: 26, still: i === 3}));
const words = [
  {text: "Quantization", start: 4.1, end: 4.5},
  {text: "compresses", start: 6.8, end: 7.2},
  {text: "forty", start: 12.2, end: 12.4},
  {text: "percent", start: 12.4, end: 12.7},
];
const plan = deriveStoryMotion(scenes, words, energy, 30);
assert.equal(plan[0].kind, "legacy", "the hook is never replaced");
assert.equal(plan[1].kind, "compression");
assert.equal(plan[1].revealFrame, 84, "global word timestamp becomes a scene-local cue");
assert.equal(plan[1].synced, true);
assert.equal(plan[2].kind, "metric");
assert.equal(plan[2].revealFrame, 96, "spelled-out numbers match numeric overlays");
assert.equal(plan[3].kind, "legacy", "the ending keeps its existing contract");
assert.deepEqual(deriveStoryMotion(scenes, words, energy, 30), plan);
assert.equal(sharedSubject(scenes[1], scenes[2]), "MODEL", "carry only a literal shared subject");
assert.equal(sharedSubject({text: "This changes everything"}, {text: "This changes your work"}), undefined);

const kind = (text: string, type = "split") => deriveStoryMotion(
  [scenes[0], {text, type, durationInFrames: 150}, scenes[3]], [], energy, 30,
)[1].kind;
assert.equal(kind("Memory security update"), "statement", "memory alone doesn't prove compression");
assert.equal(kind("Compression isn't supported"), "statement", "negated claims must not become diagrams");
assert.equal(kind("Quantization does not compress model memory"), "statement");
assert.equal(kind("40%", "countdown"), "legacy", "quiz countdowns are not metrics");
assert.equal(deriveStoryMotion(scenes, words, energy, 30, "quiz-reveal")[1].kind, "legacy");
assert.equal(deriveStoryMotion(scenes, words, energy, 30, "data-rankings")[1].kind, "legacy");
assert.equal(kind("A ".repeat(300)), "legacy", "oversized copy uses the existing layout");

const early = deriveStoryMotion(scenes, [{text: "compresses", start: 4.2, end: 4.5}], energy, 30);
assert.equal(early[1].synced, false, "an early word must not be falsely labelled synced");
assert.equal(early[1].revealFrame, 75, "reading window wins over an early cue");
assert.equal(deriveStoryMotion(scenes, [{text: "40", start: NaN, end: Infinity}], energy, 30)[2].synced, false);
assert.equal(deriveStoryMotion(scenes, [
  {text: "forty", start: 12.2, end: 12.4}, {text: "two", start: 12.4, end: 12.6},
], energy, 30)[2].synced, false, "40 must not match the start of forty two");
assert.equal(kind("The model doesn't compress memory"), "statement");
assert.equal(kind("The model doesn’t compress memory"), "statement");
assert.equal(kind("Model weights aren’t compressed"), "statement");
assert.equal(kind("We don't compress data"), "statement");
assert.equal(sharedSubject({title: "Model memory", text: ""}, {title: "Memory prices", text: "model"}), undefined,
  "only a stable leading subject gets a match cut; incidental shared words don't");
assert.equal(storyProgress(30, 75, false), 0);
assert.equal(storyProgress(99, 75, false), 1);
assert.equal(storyProgress(0, 75, true), 1, "still scenes hold a completed visual");
assert.equal(storyProgress(99, 75, true), 1);
assert.equal(storyCutStyle("whip-pan", scenes[1], scenes[2], plan[1], plan[2]), "none", "shared object remains locked across the cut");
assert.equal(storyCutStyle("film-burn", scenes[2], scenes[3], plan[2], plan[3]), "film-burn", "final cut is untouched");
assert.equal(storyMusicVolume(10, 75), 0.2);
assert.equal(storyMusicVolume(75, 75), 0.09, "make space for the narrated payoff");
assert.equal(storyMusicVolume(100, 75), 0.2);
assert.ok(fitStoryFont("OpenTelemetryCollector", 110, 710) * 22 * 0.75 <= 710,
  "long technical words fit the actual column, not a full-frame estimate");
assert.equal(fitStoryFont("40%", 148, 710), 148);
assert.equal(kind("a".repeat(50)), "legacy", "a word too long at the readability floor must use the fallback");
assert.ok(deriveStoryMotion(scenes, words, energy, 30, undefined, false).every(s => s.kind === "legacy"),
  "non-portrait layouts keep their existing safe zones");
console.log("story-motion: all assertions passed");

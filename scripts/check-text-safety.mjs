#!/usr/bin/env node
/**
 * check-text-safety.mjs — machine-checks the no-word-splitting invariant.
 *
 *     node scripts/check-text-safety.mjs
 *
 * Plain Node, zero dependencies, so it can run anywhere without touching
 * package.json (adding a dev dependency would make `npm ci` install it on every
 * production render).
 *
 * WHY THIS EXISTS
 * Subtitles and headlines splitting mid-word has shipped before. It is a
 * one-line regression — a stray `wordBreak: "break-word"`, or a per-letter
 * span dropped straight into a wrapping flex container — and it is invisible
 * in code review because both look like ordinary styling.
 *
 * The rule the renderer relies on: text may wrap only BETWEEN words. Letters
 * may be animated individually, but only inside a per-word group that is itself
 * the atom the flex container wraps on.
 *
 * This is a static check, not a property test — the repo has no test runner
 * (package.json has no `scripts` field), and a grep-level invariant that
 * actually runs beats a thorough one that never does.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { fileURLToPath } from "node:url";

// fileURLToPath, not .pathname — the repo path contains spaces, which .pathname
// hands back percent-encoded and fs then cannot open.
const ROOT = fileURLToPath(new URL("..", import.meta.url));
const SRC = join(ROOT, "src", "remotion");

let failures = 0;
const fail = (file, line, msg, snippet) => {
  failures++;
  console.log(`FAIL  ${relative(ROOT, file)}:${line}  ${msg}`);
  if (snippet) console.log(`      ${snippet.trim().slice(0, 140)}`);
};

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (/\.(tsx?|jsx?)$/.test(entry)) out.push(p);
  }
  return out;
}

const files = walk(SRC);
console.log(`Scanning ${files.length} files under src/remotion\n`);

// --- Rule 1: CSS that permits breaking inside a word -------------------------
// `break-word`/`break-all`/`hyphens:auto` all license a mid-word break. There
// is no legitimate use in this renderer: the auto-fit in AnimatedText already
// guarantees the longest single word fits its line.
const BANNED = [
  { re: /\bwordBreak\s*:\s*["'](break-all|break-word)["']/, name: 'wordBreak: "break-all"/"break-word"' },
  { re: /\boverflowWrap\s*:\s*["'](break-word|anywhere)["']/, name: 'overflowWrap: "break-word"/"anywhere"' },
  { re: /\bword-break\s*:\s*(break-all|break-word)/, name: "word-break in a CSS string" },
  { re: /\boverflow-wrap\s*:\s*(break-word|anywhere)/, name: "overflow-wrap in a CSS string" },
  { re: /\bhyphens\s*:\s*["']?auto["']?/, name: "hyphens: auto" },
  { re: /\blineBreak\s*:\s*["']anywhere["']/, name: 'lineBreak: "anywhere"' },
];

for (const file of files) {
  const lines = readFileSync(file, "utf8").split("\n");
  lines.forEach((text, i) => {
    for (const rule of BANNED) {
      if (rule.re.test(text)) fail(file, i + 1, `${rule.name} allows a break INSIDE a word`, text);
    }
  });
}

// --- Rule 2: per-letter splits must be grouped per word ----------------------
// A `.split("")` that is not accompanied by a `.split(" ")` in the same
// function means letters become the flex container's wrap atoms, so a line can
// break between any two characters. useWave is the reference-correct shape:
// split on spaces first, then map letters inside each word group.
for (const file of files) {
  const src = readFileSync(file, "utf8");
  const lines = src.split("\n");
  lines.forEach((text, i) => {
    if (!/\.split\(\s*""\s*\)/.test(text)) return;
    // String surgery, not rendering: a split that is re-joined in the same
    // expression produces a string, never DOM atoms. This is how the hex-colour
    // helpers expand #abc -> #aabbcc, and it is unrelated to text layout.
    if (/\.split\(\s*""\s*\)[\s\S]{0,120}?\.join\(/.test(text)) return;
    // Walk back to the nearest function/hook declaration and scan its body.
    let start = i;
    while (start > 0 && !/^(const|function|export)\s/.test(lines[start])) start--;
    let depth = 0;
    let end = start;
    for (let j = start; j < lines.length; j++) {
      depth += (lines[j].match(/\{/g) || []).length;
      depth -= (lines[j].match(/\}/g) || []).length;
      end = j;
      if (j > start && depth <= 0) break;
    }
    const body = lines.slice(start, end + 1).join("\n");
    if (!/\.split\(\s*["'] ["']\s*\)/.test(body)) {
      fail(
        file,
        i + 1,
        'per-letter .split("") with no enclosing .split(" ") — letters would become wrap atoms',
        text,
      );
    }
  });
}

// --- Rule 3: word atoms must not be breakable --------------------------------
// Any span that receives a whole word should be inline-block (so it is an
// unbreakable box) or explicitly nowrap. This is advisory — it reports the
// count rather than failing, because the styles are spread from several
// builders and a hard rule here produces false positives.
let atomCount = 0;
for (const file of files) {
  const src = readFileSync(file, "utf8");
  atomCount += (src.match(/display:\s*["']inline-block["']/g) || []).length;
  atomCount += (src.match(/whiteSpace:\s*["']nowrap["']/g) || []).length;
}

// --- Rule 4: the auto-fit word cap must survive ------------------------------
// AnimatedText shrinks the font until the LONGEST word fits one line. If that
// computation is removed, every other guarantee here becomes decorative.
// Each guard is checked by DECLARATION AND USE, not by substring: renaming a
// constant to `FOO_DISABLED` leaves the old substring intact and would slip
// past a bare /FOO/ test. (It did, the first time this script was run.)
const animated = join(SRC, "MyComp", "AnimatedText.tsx");
const animatedSrc = readFileSync(animated, "utf8");
const countOf = (re) => (animatedSrc.match(re) || []).length;

if (!/const\s+longestWordLen\s*=/.test(animatedSrc) || !/const\s+maxSizeForWord\s*=/.test(animatedSrc)) {
  fail(animated, 1, "the longest-word auto-fit cap is gone — words can overflow their line");
} else if (!/Math\.min\(\s*requestedSize\s*,\s*maxSizeForWord\s*\)/.test(animatedSrc)) {
  fail(animated, 1, "maxSizeForWord is computed but no longer clamps the font size");
}

if (!/const\s+READ_LOCK_FRAMES\s*=/.test(animatedSrc)) {
  fail(animated, 1, "the read-lock stagger cap is gone — long lines will crawl in");
} else if (!/const\s+readLocked\s*=/.test(animatedSrc)) {
  fail(animated, 1, "readLocked() helper is gone — the stagger cap has no implementation");
} else {
  // word-by-word, rise-mask, flip-in, clip-wipe and wave must all route through
  // it. The declaration reads `readLocked = (`, so it does not match this
  // pattern and must NOT be subtracted — doing so made the check fail on a
  // correct tree.
  const uses = countOf(/\breadLocked\(/g);
  if (uses < 5) {
    fail(animated, 1, `only ${uses} of 5 staggered modes use readLocked() — one is uncapped`);
  }
}

console.log(`\n${atomCount} unbreakable-atom style declarations found (informational)`);
console.log(failures === 0 ? "\nALL PASS — no word-splitting hazards found" : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);

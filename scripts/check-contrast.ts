/**
 * check-contrast.ts — exercises the legibility solver in contrast.ts.
 *
 * Run WITHOUT installing anything into the project:
 *     npx tsx@latest scripts/check-contrast.ts
 *
 * Deliberately NOT wired into package.json or the render workflow. Adding tsx
 * to devDependencies would make `npm ci` install it on every production render
 * (.github/workflows/generate_video.yml) for a script CI never runs.
 *
 * What it proves:
 *  1. scrimAlphaAt models the 45%-tall bottom-anchored container, not the raw
 *     gradient stops — i.e. it reports ZERO protection above 55% frame height.
 *  2. solvePlateAlpha's closed form actually hits its target ratio.
 *  3. The alphas the caption band and headline need across all 6 grades are
 *     plausible rather than pinned at the ceiling.
 */

import { deriveLook, derivePalette, deriveFinish, FINISH_TOKENS, withAlpha } from "../src/remotion/MyComp/looks";
import {
  CR_BODY,
  CR_DISPLAY,
  PLATE_CEILING,
  busynessFor,
  deriveContrastBudget,
  scrimAlphaAt,
  solvePlateAlpha,
  zoneLuminance,
  zonePasses,
} from "../src/remotion/MyComp/contrast";

let failures = 0;
const check = (name: string, cond: boolean, detail = "") => {
  if (!cond) failures++;
  console.log(`${cond ? "PASS" : "FAIL"}  ${name}${detail ? `  — ${detail}` : ""}`);
};

// --- 1. Scrim geometry ------------------------------------------------------
console.log("\n=== scrim alpha by FRAME height ===");
for (const y of [10, 30, 50, 55, 60, 68.5, 74, 76, 79.75, 90, 100]) {
  console.log(`  y=${String(y).padStart(6)}%  alpha=${scrimAlphaAt(y).toFixed(3)}`);
}
check("no scrim above 55% (headlines are unprotected)", scrimAlphaAt(54.9) === 0);
check("scrim starts exactly at 55%", scrimAlphaAt(55) === 0);
check("scrim bottoms out at 0.88", Math.abs(scrimAlphaAt(100) - 0.88) < 1e-9);
check(
  "caption band (~74%) gets only partial scrim",
  scrimAlphaAt(74) > 0.2 && scrimAlphaAt(74) < 0.35,
  `alpha=${scrimAlphaAt(74).toFixed(3)}`,
);
let mono = true;
for (let y = 55; y <= 100; y += 0.5) if (scrimAlphaAt(y) < scrimAlphaAt(y - 0.5) - 1e-12) mono = false;
check("scrim alpha is monotonic", mono);

// --- 2. The closed form actually solves -------------------------------------
console.log("\n=== solvePlateAlpha round-trip ===");
let solveOk = true;
for (const Lbg of [0.05, 0.2, 0.4, 0.6, 0.85, 1.0]) {
  for (const plate of ["#000000", "#0a0c12", "#07080d"]) {
    for (const [text, cr] of [["#f8fafc", CR_BODY], ["#ffffff", CR_DISPLAY]] as const) {
      const a = solvePlateAlpha(Lbg, plate, text, cr);
      const passes = zonePasses(Lbg, plate, text, cr, a);
      // Either it passes at the solved alpha, or it is genuinely unsatisfiable
      // within the ceiling — never "solved but still failing" below the cap.
      if (!passes && a < PLATE_CEILING - 1e-9) solveOk = false;
      // And the solve must be MINIMAL: a hair less must fail (when a > 0).
      if (a > 1e-6 && a < PLATE_CEILING - 1e-6 && zonePasses(Lbg, plate, text, cr, a - 0.02)) {
        solveOk = false;
      }
    }
  }
}
check("solved alpha is sufficient and minimal across the grid", solveOk);
check("already-passing zone needs no plate", solvePlateAlpha(0.01, "#000000", "#ffffff", CR_BODY) === 0);

// --- 3. Real looks ----------------------------------------------------------
// Two style-pack colourways drawn from production props.
const PACKS: Array<[string, string, string]> = [
  ["clean-cobalt", "#3b82f6", "#22d3ee"],
  ["warm-editorial", "#f59e0b", "#ef4444"],
];

console.log("\n=== required plate alpha, lift = 0 (today's grade) ===");
console.log("pack             grade    chrome     caption(4.5:1)   headline(3.0:1)  prism");
const seen = new Map<string, number>();
for (const [packName, primary, secondary] of PACKS) {
  const palette = derivePalette(primary, secondary);
  for (let seed = 1; seed <= 400; seed++) {
    const look = deriveLook(seed);
    const key = `${packName}|${look.grade}|${look.chrome}`;
    if (seen.has(key)) continue;
    seen.set(key, seed);

    const finish = deriveFinish(seed, look, "clean");
    const ft = FINISH_TOKENS[finish];
    const plateHex = ft.panelBgBase(palette);

    for (const prismStrength of [0, 1]) {
      const media = {
        look,
        palette,
        lift: 0,
        prismStrength,
        prismBloom: 1, // worst case
        busyness: busynessFor(look, "clean", prismStrength > 0 ? 2 : 0),
      };
      const budget = deriveContrastBudget(media, [
        { name: "caption", yPct: 74, textHex: "#ffffff", targetCR: CR_BODY, plateHex },
        { name: "headline", yPct: look.heroAnchor, textHex: "#f8fafc", targetCR: CR_DISPLAY, plateHex },
      ]);
      const cap = budget.zones[0];
      const head = budget.zones[1];
      if (prismStrength === 0) {
        console.log(
          `${packName.padEnd(16)} ${look.grade.padEnd(8)} ${look.chrome.padEnd(10)} ` +
            `a=${cap.requiredAlpha.toFixed(2)} cr=${cap.achievedCR.toFixed(1).padStart(5)}   ` +
            `a=${head.requiredAlpha.toFixed(2)} cr=${head.achievedCR.toFixed(1).padStart(5)}   ` +
            `${budget.anyUnsatisfiable ? "UNSAT" : "ok"}`,
        );
      }
      if (budget.anyUnsatisfiable) {
        check(`satisfiable: ${key} prism=${prismStrength}`, false, `maxAlpha=${budget.maxAlpha.toFixed(3)}`);
      }
    }
  }
}
check(`covered ${seen.size} distinct pack x grade x chrome combinations`, seen.size >= 30);

// --- 4. The headline is the surface a lift would hurt first ------------------
console.log("\n=== what a brightness lift would cost (solver run at lift > 0) ===");
const palette = derivePalette("#3b82f6", "#22d3ee");
const look = deriveLook(7);
const ftGlass = FINISH_TOKENS.glass;
const plateHex = ftGlass.panelBgBase(palette);
for (const lift of [0, 0.1, 0.2, 0.3]) {
  const media = { look, palette, lift, prismStrength: 0, prismBloom: 0.5, busyness: 0.1 };
  const capL = zoneLuminance(media, 74);
  const headL = zoneLuminance(media, look.heroAnchor);
  const capA = solvePlateAlpha(capL, plateHex, "#ffffff", CR_BODY);
  const headA = solvePlateAlpha(headL, plateHex, "#f8fafc", CR_DISPLAY);
  console.log(
    `  lift=${lift.toFixed(2)}  caption L=${capL.toFixed(3)} a=${capA.toFixed(2)}   ` +
      `headline L=${headL.toFixed(3)} a=${headA.toFixed(2)}` +
      `${headA >= PLATE_CEILING ? "  <- headline hits the ceiling" : ""}`,
  );
}

// --- 5. FinishTokens invariant ---------------------------------------------
console.log("\n=== panelBgBase/panelBgAlpha match panelBg ===");
for (const [name, ft] of Object.entries(FINISH_TOKENS)) {
  const derived = withAlpha(ft.panelBgBase(palette), ft.panelBgAlpha);
  const actual = ft.panelBg(palette);
  const same = derived.toLowerCase() === actual.toLowerCase();
  // neon/soft paint rgba() literals on purpose; compare their alpha numerically.
  const rgba = /rgba\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([0-9.]+)\)/.exec(actual);
  const equivalent = same || (rgba !== null && Math.abs(Number(rgba[4]) - ft.panelBgAlpha) < 0.01);
  check(`${name}: base+alpha describes panelBg`, equivalent, `${actual} vs ${derived}`);
}

console.log(`\n${failures === 0 ? "ALL PASS" : `${failures} FAILURE(S)`}`);
process.exit(failures === 0 ? 0 : 1);

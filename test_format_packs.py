#!/usr/bin/env python3
"""
Format-Pack Scaffolding — Regression Tests
==========================================
Locks the M0 contract: with no FORMAT_PACK set (or the legacy pack named),
every pack-aware seam in the pipeline behaves BIT-FOR-BIT as before
format_packs.py existed. The legacy runtime-revision strings and the legacy
creative brief are byte-pinned here, because they are prompt surface for
small models — silent drift changes script behavior in production.

Usage:
  python test_format_packs.py          # run all, exit 0/1
  python test_format_packs.py -v       # verbose
"""

import sys

import format_packs
import main

VERBOSE = "-v" in sys.argv

FAILURES = []


def check(name, cond, detail=""):
    if cond:
        if VERBOSE:
            print(f"  PASS  {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


# --- 1. resolve_pack -----------------------------------------------------------
print("[resolve_pack]")
check("None -> legacy", format_packs.resolve_pack(None)["name"] == "legacy-news")
check("blank -> legacy", format_packs.resolve_pack("  ")["name"] == "legacy-news")
check("unknown -> legacy", format_packs.resolve_pack("no-such-pack")["name"] == "legacy-news")
check("case/space normalized", format_packs.resolve_pack(" QUIZ-Reveal ")["name"] == "quiz-reveal")
check("non-string -> legacy", format_packs.resolve_pack(123)["name"] == "legacy-news")

cfg = format_packs.resolve_pack("quiz-reveal")
cfg["band"] = (1, 2)
check("returns a copy (registry not mutated)",
      format_packs.FORMAT_PACKS["quiz-reveal"]["band"] == (15.0, 25.0))

REQUIRED_KEYS = {"band", "broll", "outro", "loop_ending", "hook", "brief", "scenes"}
for pname, pcfg in format_packs.FORMAT_PACKS.items():
    check(f"registry keys complete: {pname}", REQUIRED_KEYS.issubset(pcfg.keys()))
    if pcfg["band"] is not None:
        check(f"band sane: {pname}", pcfg["band"][0] < pcfg["band"][1])
check("legacy band defers to env globals", format_packs.FORMAT_PACKS["legacy-news"]["band"] is None)
check("legacy has outro, no loop", format_packs.FORMAT_PACKS["legacy-news"]["outro"] is True
      and format_packs.FORMAT_PACKS["legacy-news"]["loop_ending"] is False)

# --- 2. Legacy revision-note byte pins ------------------------------------------
# These literals are the EXACT strings the pre-pack retry loop appended
# (main.py, CRITICAL REVISION branches). Pinned against raw literals here —
# not against format_packs constants — so a drift in either place fails.
print("[runtime_revision_notes]")
LEGACY_EXPAND_PIN = (
    "when spoken — the video MUST run longer. Write 6-8 scenes and give EVERY scene a \"voiceover\" of "
    "20-35 words (two full sentences is ideal) so the summed narration lasts 40-55 seconds. Do NOT pad "
    "with repetition or filler — every added sentence must contribute a new concrete fact or detail."
)
LEGACY_TIGHTEN_PIN = (
    "spoken — too long for a Reel. Cut the weakest scenes and tighten every \"voiceover\" so the "
    "summed narration lasts 40-55 seconds, keeping only the strongest concrete facts."
)
legacy_cfg = format_packs.resolve_pack(None)
exp, tig = format_packs.runtime_revision_notes(legacy_cfg, main.MIN_SPOKEN_SEC, main.MAX_SPOKEN_SEC)
check("legacy expand note byte-identical", exp == LEGACY_EXPAND_PIN,
      f"got: {exp[:80]}...")
check("legacy tighten note byte-identical", tig == LEGACY_TIGHTEN_PIN,
      f"got: {tig[:80]}...")

quiz_cfg = format_packs.resolve_pack("quiz-reveal")
qexp, qtig = format_packs.runtime_revision_notes(quiz_cfg, *quiz_cfg["band"])
check("quiz expand names its own band", "15-25 seconds" in qexp and "40-55" not in qexp)
check("quiz tighten names its own band", "15-25 seconds" in qtig and "40-55" not in qtig)
check("quiz notes preserve structure", "scene structure" in qexp and "scene structure" in qtig)

# --- 3. build_variety_directive identity ----------------------------------------
# The legacy creative brief must be byte-identical whether format_pack is
# omitted, None, or "legacy-news" — across seeds and channel modes.
print("[build_variety_directive]")
for seed in (0, 1, 42, 1337, 987654321):
    for auto in (True, False):
        m0, m1, m2 = {}, {}, {}
        d0 = main.build_variety_directive(seed, auto, meta_out=m0)
        d1 = main.build_variety_directive(seed, auto, meta_out=m1, format_pack=None)
        d2 = main.build_variety_directive(seed, auto, meta_out=m2, format_pack="legacy-news")
        check(f"legacy directive identical (seed={seed}, auto={auto})",
              d0 == d1 == d2, "directive text drifted between call forms")
        check(f"legacy meta identical (seed={seed}, auto={auto})", m0 == m1 == m2)
        check(f"legacy directive is the full brief (seed={seed})",
              "CREATIVE BRIEF" in d0 and "TARGET LENGTH" in d0)

mq = {}
dq = main.build_variety_directive(42, True, meta_out=mq, format_pack="quiz-reveal")
check("pack directive is the slim brief", "HOOK QUALITY RULES" in dq)
check("pack directive drops structural lines",
      "TARGET LENGTH" not in dq and "CLOSER" not in dq and "PACING" not in dq)
check("pack directive keeps integrity rule", "INTEGRITY" in dq)
check("pack hook_type is the pack label", mq.get("hook_type") == "PACK-QUIZ-REVEAL")

# --- 4. RenderRequest field ------------------------------------------------------
print("[RenderRequest]")
check("format_pack defaults to None", main.RenderRequest(prompt="x").format_pack is None)
check("format_pack accepts a pack name",
      main.RenderRequest(prompt="x", format_pack="quiz-reveal").format_pack == "quiz-reveal")

# --- Result ---------------------------------------------------------------------
print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} check(s): " + "; ".join(FAILURES[:8]))
    sys.exit(1)
print("test_format_packs.py: ALL PASS")

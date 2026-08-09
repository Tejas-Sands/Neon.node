#!/usr/bin/env python3
"""
Experiment Tagging — Regression Tests
=====================================
Locks _assign_experiment, the instrumentation that makes a shipped change
attributable. Without it nothing is: four feature commits landed in three
hours on 2026-08-09 and every post carried all of them.

  1. FAIL OPEN. EXPERIMENT unset, blank, or malformed => None, and None must
     mean the post is generated and recorded exactly as it was before the
     mechanism existed. A typo'd repo Variable must never change what ships.
  2. Two modes: `era:<name>` (one arm, tag only) and `<name>:<a>|<b>` (split).
  3. DETERMINISM + MEMOIZATION. generate_now assigns pre-render to choose the
     format pack; ledger_meta records post-render. If those two calls could
     disagree, every row in the ledger would be a coin flip about which arm
     actually produced it.
  4. ROUND-ROBIN, not a coin flip. At n=12/arm a fair coin lands 8-4 or worse
     ~39% of the time; at 3 posts/day that imbalance is power we cannot
     afford. Seeded choice is the FALLBACK for when the ledger is unreadable,
     so assignment never depends on I/O succeeding.
  5. The arm never votes in the feedback loop (pinned in
     test_feedback_scoring.py too — if it became a bucket, the bandit and the
     arm assignment would fight over the same lever).

Usage:
  python test_experiment.py        # run all, exit 0/1
  python test_experiment.py -v
"""

import inspect
import os
import sys

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


def assign(session_id, spec, ledger_entries=None):
    """_assign_experiment under a given EXPERIMENT spec and fake ledger."""
    main._EXPERIMENT_CACHE.clear()
    prev = os.environ.get("EXPERIMENT")
    prev_loader = main.load_post_ledger
    if spec is None:
        os.environ.pop("EXPERIMENT", None)
    else:
        os.environ["EXPERIMENT"] = spec
    if ledger_entries is not None:
        main.load_post_ledger = lambda: {"version": 1, "entries": ledger_entries}
    try:
        return main._assign_experiment(session_id)
    finally:
        main.load_post_ledger = prev_loader
        if prev is None:
            os.environ.pop("EXPERIMENT", None)
        else:
            os.environ["EXPERIMENT"] = prev
        main._EXPERIMENT_CACHE.clear()


def tagged(name, arm):
    return {"experiment": {"name": name, "arm": arm}}


# --- 1. Fail open ----------------------------------------------------------------
print("[fail open]")
check("EXPERIMENT unset -> None", assign("gh-aaa", None) is None)
check("EXPERIMENT blank -> None", assign("gh-aaa", "") is None)
check("EXPERIMENT whitespace -> None", assign("gh-aaa", "   ") is None)
check("no colon -> None", assign("gh-aaa", "runtime") is None)
check("no arms -> None", assign("gh-aaa", "runtime:") is None)
check("empty arms -> None", assign("gh-aaa", "runtime:|") is None)
check("no name -> None", assign("gh-aaa", ":short|long") is None)

# --- 2. Modes --------------------------------------------------------------------
print("[modes]")
r = assign("gh-aaa", "era:cover-v2", [])
check("era: yields one arm",
      r == {"name": "era", "arm": "cover-v2", "assign": "single", "rev": 1}, f"got {r}")
check("era: is identical for every session",
      assign("gh-zzz", "era:cover-v2", [])["arm"] == "cover-v2")
r = assign("gh-aaa", "runtime:short|long", [])
check("split yields one of the arms", r["arm"] in ("short", "long"), f"got {r}")
check("split reports roundrobin assignment", r["assign"] == "roundrobin", f"got {r}")
check("split carries the name", r["name"] == "runtime")

# --- 3. Determinism + memoization ------------------------------------------------
print("[determinism]")
a = assign("gh-abc123", "runtime:short|long", [])
b = assign("gh-abc123", "runtime:short|long", [])
check("same session + same ledger -> same arm", a["arm"] == b["arm"], f"{a} vs {b}")

# Memoization: the SECOND call inside one session must not re-read the ledger.
# Simulate the real sequence — generate_now assigns, posts land, ledger_meta
# reads back — and assert the arm did not move underneath us.
main._EXPERIMENT_CACHE.clear()
prev_env, prev_loader = os.environ.get("EXPERIMENT"), main.load_post_ledger
os.environ["EXPERIMENT"] = "runtime:short|long"
try:
    main.load_post_ledger = lambda: {"version": 1, "entries": []}
    first = main._assign_experiment("gh-memo")
    # Ledger now shows the arm already used — a fresh assignment would flip.
    main.load_post_ledger = lambda: {"version": 1,
                                     "entries": [tagged("runtime", first["arm"])] * 5}
    second = main._assign_experiment("gh-memo")
    check("memoized across calls within a session", first["arm"] == second["arm"],
          f"{first} vs {second}")
finally:
    main.load_post_ledger = prev_loader
    main._EXPERIMENT_CACHE.clear()
    if prev_env is None:
        os.environ.pop("EXPERIMENT", None)
    else:
        os.environ["EXPERIMENT"] = prev_env

# --- 4. Round-robin balance ------------------------------------------------------
print("[balance]")
# Feed each assignment back into the ledger, exactly as production does.
entries = []
for i in range(20):
    r = assign(f"gh-s{i:03d}", "runtime:short|long", list(entries))
    entries.append(tagged("runtime", r["arm"]))
counts = {"short": 0, "long": 0}
for e in entries:
    counts[e["experiment"]["arm"]] += 1
check("round-robin gives an exact 10/10 split over 20 sessions",
      counts == {"short": 10, "long": 10}, f"counts={counts}")

# Three arms balance too.
entries = []
for i in range(9):
    r = assign(f"gh-t{i:03d}", "hook:a|b|c", list(entries))
    entries.append(tagged("hook", r["arm"]))
counts3 = {"a": 0, "b": 0, "c": 0}
for e in entries:
    counts3[e["experiment"]["arm"]] += 1
check("round-robin balances 3 arms", counts3 == {"a": 3, "b": 3, "c": 3}, f"{counts3}")

# Prior imbalance is corrected, not compounded.
skewed = [tagged("runtime", "short")] * 4
r = assign("gh-fix", "runtime:short|long", skewed)
check("an under-used arm is chosen when the ledger is skewed", r["arm"] == "long",
      f"got {r}")

# Other experiments' rows and backfilled rows must not count.
noise = [tagged("other", "short")] * 4 + [tagged("runtime", "long")] * 2
bf = tagged("runtime", "long")
bf["backfilled"] = True
r = assign("gh-noise", "runtime:short|long", noise + [bf] * 3)
check("foreign + backfilled rows excluded from the count", r["arm"] == "short",
      f"got {r}")

# --- 5. Ledger failure falls back, still deterministic ---------------------------
print("[fallback]")


def boom():
    raise IOError("ledger unreadable")


main._EXPERIMENT_CACHE.clear()
prev_env, prev_loader = os.environ.get("EXPERIMENT"), main.load_post_ledger
os.environ["EXPERIMENT"] = "runtime:short|long"
try:
    main.load_post_ledger = boom
    f1 = main._assign_experiment("gh-fallback")
    main._EXPERIMENT_CACHE.clear()
    f2 = main._assign_experiment("gh-fallback")
    check("ledger failure still returns an arm", f1 is not None and f1["arm"] in
          ("short", "long"), f"got {f1}")
    check("ledger failure reports seeded assignment", f1["assign"] == "seed", f"got {f1}")
    check("seeded fallback is deterministic", f1["arm"] == f2["arm"], f"{f1} vs {f2}")
finally:
    main.load_post_ledger = prev_loader
    main._EXPERIMENT_CACHE.clear()
    if prev_env is None:
        os.environ.pop("EXPERIMENT", None)
    else:
        os.environ["EXPERIMENT"] = prev_env

# --- 6. Wiring -------------------------------------------------------------------
print("[wiring]")
src_render = inspect.getsource(main._execute_render_unlocked)
check("ledger_meta records the arm", '"experiment": _assign_experiment(session_id)'
      in src_render)
check("ledger_rev stays 2 (duration semantics unchanged)",
      '"ledger_rev": 2,' in src_render)

import generate_now
check("applier table maps runtime arms to packs",
      generate_now.EXPERIMENT_APPLIERS["runtime"] ==
      {"short": "facts-explainer", "long": "legacy-news"})
src_main = inspect.getsource(generate_now.main)
check("the arm is applied after the bandit (override, not merge)",
      src_main.index("[PackRotation]") < src_main.index("_assign_experiment"))
check("an unmapped experiment name is tag-only",
      "EXPERIMENT_APPLIERS.get(experiment[\"name\"], {})" in src_main)

# The arm must never reach the feedback loop.
src_stats = inspect.getsource(main.compute_feedback_stats)
check("experiment never becomes a feedback bucket", "experiment" not in src_stats)

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} check(s): " + "; ".join(FAILURES[:8]))
    sys.exit(1)
print("test_experiment.py: ALL PASS")

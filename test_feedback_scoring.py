#!/usr/bin/env python3
"""
Feedback-Loop Scoring — Regression Tests (M1)
=============================================
Locks the rescored perf model in compute_feedback_stats:

  1. The er_med=0 divide-pathology is DEAD: on a zero-engagement ledger, one
     like must no longer explode into the 4.0 clamp (the loop used to be a
     binary "got >= 1 like" classifier over noise).
  2. Entries without watch-time score via the guarded LEGACY formula
     (0.6*v + 0.4*er when er has a real median; views-only when not).
  3. Watch-time completion (wtr) + sends-per-reach (spr) dominate when
     available, and wtr is derived ONLY for ledger_rev >= 2 entries (older
     entries recorded the pre-TTS planned duration — a fiction).
  4. The actual-publish-hour derivation prefers platforms.*.posted_at over
     the render-time posted_hour_utc stamp.
  5. The guardrail constants (epsilon floor, clamps, min-entries/bucket,
     cold-start None) are asserted UNCHANGED — they must never be weakened.
  6. The signal-quality gate: a ledger that clears FEEDBACK_MIN_ENTRIES but
     carries only delivery noise (flat views, no engagement, no watch-time)
     must NOT activate the bias — _feedback_signal_ok is False until either
     enough entries score through a quality branch or raw engagement volume
     clears the floor. Strengthening only: more ways to return None.

Usage:
  python test_feedback_scoring.py       # run all, exit 0/1
  python test_feedback_scoring.py -v
"""

import inspect
import sys
import time

import main

VERBOSE = "-v" in sys.argv
FAILURES = []
NOW = time.time()


def check(name, cond, detail=""):
    if cond:
        if VERBOSE:
            print(f"  PASS  {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


def entry(style="A", views=100, likes=0, comments=0, shares=0, saved=0, reach=None,
          awt_ms=None, video_seconds=30.0, ledger_rev=None, posted_at=None,
          posted_hour_utc=None, fmt=None, ts=None):
    snap = {"views": views, "likes": likes, "comments": comments,
            "shares": shares, "saved": saved, "reach": reach if reach is not None else views}
    if awt_ms is not None:
        snap["ig_reels_avg_watch_time"] = awt_ms
    e = {
        "ts": int(ts if ts is not None else NOW - 3 * 86400),
        "channel": "news",
        "style_pack": style,
        "hook_type": "H",
        "voice": "v1",
        "video_seconds": video_seconds,
        "topic": {"keywords": []},
        "platforms": {"instagram": {"posted_at": posted_at or (NOW - 3 * 86400)}},
        "metrics": {"instagram": {"snap72": snap}},
    }
    if ledger_rev is not None:
        e["ledger_rev"] = ledger_rev
    if posted_hour_utc is not None:
        e["posted_hour_utc"] = posted_hour_utc
    if fmt is not None:
        e["format_pack"] = fmt
    return e


def stats_for(entries):
    return main.compute_feedback_stats({"version": 1, "entries": entries})


# --- 1. er_med=0 pathology is dead ---------------------------------------------
print("[er_med=0 pathology]")
# 9 zero-engagement posts (style A) + 1 post with a single like (style B),
# identical views. Old formula: B -> er/1e-4 -> clamped 4.0, A -> 0.6.
# New: er median is 0 -> er dropped -> everyone scores views-only = 1.0.
led = [entry(style="A", views=100) for _ in range(9)] + [entry(style="B", views=100, likes=1)]
s = stats_for(led)
mA, mB = s["styles"]["A"]["m"], s["styles"]["B"]["m"]
check("one like no longer saturates the clamp", mB < 1.5, f"m_B={mB}")
check("zero-engagement posts not floored to 0.6-ish", abs(mA - 1.0) < 0.05, f"m_A={mA}")
check("like-vs-no-like difference is marginal, not 6.6x", abs(mB - mA) < 0.5,
      f"m_A={mA}, m_B={mB}")

# --- 2. Legacy formula intact when er has a real baseline ------------------------
print("[legacy formula fallback]")
# Everyone has some engagement (er median > 0), no watch time anywhere:
# guarded legacy formula 0.6*v + 0.4*er applies — better er => higher m.
led = ([entry(style="A", views=100, likes=2) for _ in range(5)]
       + [entry(style="B", views=100, likes=8) for _ in range(5)])
s = stats_for(led)
check("higher engagement ranks higher under legacy formula",
      s["styles"]["B"]["m"] > s["styles"]["A"]["m"],
      f"A={s['styles']['A']['m']} B={s['styles']['B']['m']}")
check("legacy perf stays clamped", s["styles"]["B"]["m"] <= 4.0)

# --- 3. Watch-time term: rev-gated and dominant ---------------------------------
print("[watch-time completion]")
# 6 rev2 entries with watch time: style B completes 2x style A. Shares all 0
# (spr median 0 -> dropped), likes 0 (er dropped) -> wtr drives everything.
led = ([entry(style="A", views=100, awt_ms=8000, video_seconds=20.0, ledger_rev=2)
        for _ in range(3)]
       + [entry(style="B", views=100, awt_ms=16000, video_seconds=20.0, ledger_rev=2)
          for _ in range(3)])
s = stats_for(led)
check("better completion ranks higher", s["styles"]["B"]["m"] > s["styles"]["A"]["m"],
      f"A={s['styles']['A']['m']} B={s['styles']['B']['m']}")

# A pre-M1 entry (no ledger_rev) with a watch-time value must NOT get a wtr
# term — its video_seconds is the planned-duration fiction. With er/spr also
# unusable it scores views-only = 1.0 even though its raw completion would
# have been extreme.
led2 = led + [entry(style="C", views=100, awt_ms=19000, video_seconds=20.0)]
s2 = stats_for(led2)
check("pre-rev2 entry never gets a wtr term", abs(s2["styles"]["C"]["m"] - 1.0) < 0.05,
      f"C={s2['styles']['C']['m']}")

# --- 4. Sends-per-reach term -----------------------------------------------------
print("[sends-per-reach]")
# 6 entries where shares exist and vary: spr median > 0 -> spr usable.
led = ([entry(style="A", views=200, reach=200, shares=2) for _ in range(3)]
       + [entry(style="B", views=200, reach=200, shares=8) for _ in range(3)])
s = stats_for(led)
check("more sends per reach ranks higher", s["styles"]["B"]["m"] > s["styles"]["A"]["m"],
      f"A={s['styles']['A']['m']} B={s['styles']['B']['m']}")

# --- 5. format_packs bucket ------------------------------------------------------
print("[format_packs bucket]")
led = [entry(style="A", views=100, fmt="quiz-reveal") for _ in range(3)] \
    + [entry(style="A", views=100) for _ in range(3)]
s = stats_for(led)
check("format_packs bucket exists and accumulates",
      s.get("format_packs", {}).get("quiz-reveal", {}).get("n") == 3,
      f"got {s.get('format_packs')}")
check("entries without format_pack don't pollute the bucket",
      len(s.get("format_packs", {})) == 1)

# --- 6. Actual publish hour ------------------------------------------------------
print("[publish hour]")
# posted_at at 17:00 UTC, render-time stamp says hour 5. hours4 must bucket
# on 17 (bucket 4), not 5 (bucket 1).
posted_17 = 3 * 86400 + 17 * 3600  # 1970-01-04 17:00 UTC
led = [entry(style="A", views=100, likes=1, posted_at=posted_17, posted_hour_utc=5,
             ts=NOW - 3 * 86400) for _ in range(3)]
s = stats_for(led)
check("hour derived from posted_at, not render stamp",
      4 in s["hours4"] and 1 not in s["hours4"], f"hours4={s['hours4']}")
led = [entry(style="A", views=100, likes=1, posted_hour_utc=5) for _ in range(3)]
for e in led:
    e["platforms"]["instagram"].pop("posted_at")
s = stats_for(led)
check("posted_hour_utc fallback still works", 1 in s["hours4"], f"hours4={s['hours4']}")

# --- 7. Guardrails unchanged -----------------------------------------------------
print("[guardrails]")
check("FEEDBACK_EPSILON = 0.2", main.FEEDBACK_EPSILON == 0.2)
check("FEEDBACK_MIN_ENTRIES = 8", main.FEEDBACK_MIN_ENTRIES == 8)
check("FEEDBACK_MIN_BUCKET = 3", main.FEEDBACK_MIN_BUCKET == 3)
check("FEEDBACK_HALF_LIFE_DAYS = 14", main.FEEDBACK_HALF_LIFE_DAYS == 14)
check("eng weights unchanged",
      main.FEEDBACK_ENG_WEIGHTS == {"comments": 2, "shares": 3, "saved": 3})
src = inspect.getsource(main._feedback_weighted_choice)
check("weight clamp [0.5, 2.0] still in the chooser", "0.5" in src and "2.0" in src)
src_stats = inspect.getsource(main.compute_feedback_stats)
check("perf clamp [0.25, 4.0] still applied", "max(0.25, min(4.0, perf))" in src_stats)
check("no floored-epsilon division anywhere", "1e-4" not in src_stats)
src_get = inspect.getsource(main.get_feedback_stats)
check("cold-start None gate intact", "FEEDBACK_MIN_ENTRIES" in src_get)

# --- 8. Backfilled entries still never vote --------------------------------------
print("[backfilled]")
led = [entry(style="A", views=100, likes=1) for _ in range(3)]
for e in led:
    e["backfilled"] = True
led += [entry(style="B", views=100, likes=1) for _ in range(3)]
s = stats_for(led)
check("backfilled entries shape medians but never vote",
      "A" not in s["styles"] and "B" in s["styles"], f"styles={list(s['styles'])}")

# --- 9. Signal-quality gate ------------------------------------------------------
print("[signal gate]")
check("FEEDBACK_MIN_SIGNAL = 30", main.FEEDBACK_MIN_SIGNAL == 30)
check("FEEDBACK_MIN_QUALITY = 5", main.FEEDBACK_MIN_QUALITY == 5)

# The live failure shape: 32 posts, flat 101-159 views, zero engagement.
# Clears FEEDBACK_MIN_ENTRIES (8) but every entry scores views-only ->
# quality_n=0, eng_total=0 -> gate must hold the loop neutral.
led = [entry(style="A", views=101 + (i % 58)) for i in range(32)]
s = stats_for(led)
check("noise ledger reports zero signal",
      s["signal"] == {"eng_total": 0.0, "quality_n": 0}, f"signal={s['signal']}")
check("noise ledger fails the gate", main._feedback_signal_ok(s) is False)

# Watch-time entries score through the quality branch — 5 of them clear
# FEEDBACK_MIN_QUALITY even with zero likes (wtr is dense signal).
led = [entry(style="A", views=100, awt_ms=8000 + 1000 * i, video_seconds=20.0,
             ledger_rev=2) for i in range(6)]
s = stats_for(led)
check("wtr entries count as quality signal",
      s["signal"]["quality_n"] >= main.FEEDBACK_MIN_QUALITY,
      f"signal={s['signal']}")
check("wtr ledger passes the gate", main._feedback_signal_ok(s) is True)

# Raw engagement volume alone can clear the gate: weighted eng
# (likes + 2c + 3sh + 3sv) summed over the voting population >= 30.
led = [entry(style="A", views=120, likes=2, shares=1, saved=1) for _ in range(4)]
s = stats_for(led)
check("engagement volume clears the floor",
      s["signal"]["eng_total"] >= main.FEEDBACK_MIN_SIGNAL, f"signal={s['signal']}")
check("engagement-rich ledger passes the gate", main._feedback_signal_ok(s) is True)

# Backfilled entries never vote — their engagement must not count toward
# the signal census either (census mirrors the voting population).
led = [entry(style="A", views=100, likes=50) for _ in range(3)]
for e in led:
    e["backfilled"] = True
led += [entry(style="B", views=100) for _ in range(3)]
s = stats_for(led)
check("backfilled engagement excluded from signal census",
      s["signal"]["eng_total"] == 0.0, f"signal={s['signal']}")

# Malformed/missing signal block reads as no-signal (the safe direction).
check("missing signal block fails closed", main._feedback_signal_ok({}) is False)
check("None stats fail closed", main._feedback_signal_ok(None) is False)
check("garbage signal fails closed",
      main._feedback_signal_ok({"signal": {"eng_total": "x", "quality_n": None}}) is False)

# The gate is wired into get_feedback_stats (strengthening the cold-start
# contract, never bypassing it).
src_get = inspect.getsource(main.get_feedback_stats)
check("gate wired into get_feedback_stats", "_feedback_signal_ok" in src_get)

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} check(s): " + "; ".join(FAILURES[:8]))
    sys.exit(1)
print("test_feedback_scoring.py: ALL PASS")

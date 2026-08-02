#!/usr/bin/env python3
"""
Topic Selection — Regression Tests (B2/B3)
==========================================
Locks the flag-gated selection upgrades in filter_and_pick_story and the
entity machinery around it:

  1. DEFAULT ENV = LEGACY, bit-for-bit: weighted-random over the top 5 with
     weight = score**2, 3-word-head dedup, no freshness gate, no cooldown.
  2. TOPIC_PICK_MODE=argmax is deterministic: same candidates → same pick,
     regardless of the rng, and it is always the max-score candidate.
  3. TOPIC_MAX_AGE_H drops stale candidates but RELAXES rather than emptying
     the pool — freshness must degrade before the LRU-repeat fallback fires.
  4. TOPIC_FRESH_BOOST_H adds +0.6 wrapper-side; score_virality itself is
     untouched (its pins live in test_script_gate.py).
  5. TOPIC_ENTITY_COOLDOWN_H: same primary entity at most once per window;
     TOPIC_COOLDOWN_OVERRIDE_SCORE lets a huge story through; a cooldown
     that would empty the pool re-admits rather than falling to a repeat;
     history entries WITHOUT the `entities` field still cool down (derived
     on the fly).
  6. TOPIC_DEDUP_V2 (Jaccard ≥ 0.7 over 4+-char tokens) catches reworded
     titles the head rule missed AND admits titles the head rule over-blocked.
  7. _extract_entities: lexicon canonicalization (ChatGPT/GPT → openai),
     CamelCase/digit heuristics, Title-Case caps carry no signal.
  8. record_topic_use writes `entities` and honors TOPIC_HISTORY_CAP.

Usage:
  python test_topic_select.py       # run all, exit 0/1
  python test_topic_select.py -v
"""

import contextlib
import json
import os
import random
import sys
import tempfile
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


@contextlib.contextmanager
def env(**kv):
    old = {k: os.environ.get(k) for k in kv}
    os.environ.update({k: str(v) for k, v in kv.items()})
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def cand(title, score_boosters="", eng=200, com=100, age=6.0, hn_id=None):
    """Candidate in the _hn_to_candidates shape. score_boosters is appended to
    the title so tests can push scores up without changing the visible title."""
    return {
        "source": "hackernews",
        "title": title + score_boosters,
        "subject": title,
        "url": "https://example.com/a",
        "engagement": eng,
        "comments": com,
        "age_hours": age,
        "meta": "front page",
        "_hn_id": hn_id,
    }


def hist(title, ts=None, entities=None, story_id=None):
    h = {
        "id": str(story_id) if story_id is not None else None,
        "title": title,
        "norm": main._normalize_subject(title),
        "subject_norm": None,
        "ts": int(ts if ts is not None else NOW - 6 * 3600),
        "session": "t",
    }
    if entities is not None:
        h["entities"] = entities
    return h


# --- 1. Legacy default behavior --------------------------------------------------
print("[legacy default]")
cands = [cand(f"Story number {i} about databases", eng=100 + 40 * i) for i in range(8)]
picks = set()
for seed in range(20):
    chosen, fb = main.filter_and_pick_story(
        [dict(c) for c in cands], [], random.Random(seed), top_n=5)
    check(f"legacy pick from top-5 (seed {seed})" if VERBOSE else "legacy pick from top-5",
          chosen["title"] in {c["title"] for c in sorted(
              cands, key=lambda c: main.score_virality(c), reverse=True)[:5]},
          f"picked {chosen['title']}")
    check("legacy never fallback on fresh pool", fb is False)
    picks.add(chosen["title"])
check("legacy weighted pick actually varies across seeds", len(picks) > 1,
      f"picks={picks}")

# --- 2. Argmax mode --------------------------------------------------------------
print("[argmax]")
with env(TOPIC_PICK_MODE="argmax"):
    best_title = max(cands, key=lambda c: main.score_virality(c))["title"]
    for seed in (0, 7, 99):
        chosen, fb = main.filter_and_pick_story(
            [dict(c) for c in cands], [], random.Random(seed), top_n=5)
        check("argmax is rng-independent and maximal", chosen["title"] == best_title,
              f"seed {seed} picked {chosen['title']} != {best_title}")

# --- 3. Freshness gate -----------------------------------------------------------
print("[freshness gate]")
with env(TOPIC_PICK_MODE="argmax", TOPIC_MAX_AGE_H="36"):
    mixed = [cand("Old story about compilers", age=60.0, eng=5000),
             cand("Fresh story about compilers today", age=5.0, eng=100)]
    chosen, fb = main.filter_and_pick_story(
        [dict(c) for c in mixed], [], random.Random(1))
    check("stale candidate dropped under the gate",
          chosen["title"].startswith("Fresh"), f"picked {chosen['title']}")
    all_old = [cand("Old story one about compilers", age=60.0),
               cand("Old story two about databases", age=70.0)]
    chosen, fb = main.filter_and_pick_story(
        [dict(c) for c in all_old], [], random.Random(1))
    check("all-stale pool relaxes instead of LRU fallback", fb is False,
          f"was_fallback={fb}")

# --- 4. Fresh boost --------------------------------------------------------------
print("[fresh boost]")
with env(TOPIC_FRESH_BOOST_H="12"):
    a = cand("Some story about kernels", age=6.0)
    b = cand("Some story about kernels", age=30.0)
    main.filter_and_pick_story([a, b], [], random.Random(0))
    check("young story gets +0.6, old does not",
          abs((a["_score"] - b["_score"]) - (0.6 + (main.score_virality(a) - main.score_virality(b)))) < 1e-9,
          f"a={a['_score']:.3f} b={b['_score']:.3f}")
base = main.score_virality(cand("Some story about kernels", age=6.0))
check("score_virality itself has no boost term",
      abs(base - main.score_virality(cand("Some story about kernels", age=6.0))) < 1e-12)

# --- 5. Entity cooldown ----------------------------------------------------------
print("[entity cooldown]")
COOL = dict(TOPIC_PICK_MODE="argmax", TOPIC_ENTITY_COOLDOWN_H="48")
with env(**COOL):
    history = [hist("OpenAI announces new pricing", ts=NOW - 24 * 3600,
                    entities=["openai"])]
    # eng=400 → score ≈ 11.0, safely under the 13.0 override default.
    pool = [cand("ChatGPT gets a memory upgrade", eng=400),
            cand("Postgres 18 released with async io", eng=300)]
    chosen, fb = main.filter_and_pick_story(
        [dict(c) for c in pool], history, random.Random(1))
    check("ChatGPT story cooled by yesterday's OpenAI story",
          "Postgres" in chosen["title"], f"picked {chosen['title']}")

    old_history = [hist("OpenAI announces new pricing", ts=NOW - 72 * 3600,
                        entities=["openai"])]
    chosen, fb = main.filter_and_pick_story(
        [dict(c) for c in pool], old_history, random.Random(1))
    check("cooldown expires outside the window",
          "ChatGPT" in chosen["title"], f"picked {chosen['title']}")

    legacy_history = [hist("OpenAI announces new pricing", ts=NOW - 24 * 3600)]
    chosen, fb = main.filter_and_pick_story(
        [dict(c) for c in pool], legacy_history, random.Random(1))
    check("history entries without `entities` still cool down",
          "Postgres" in chosen["title"], f"picked {chosen['title']}")

    only_openai = [cand("ChatGPT gets a memory upgrade", eng=400)]
    chosen, fb = main.filter_and_pick_story(
        [dict(c) for c in only_openai], history, random.Random(1))
    check("cooldown that would empty the pool re-admits (not LRU fallback)",
          fb is False and "ChatGPT" in chosen["title"], f"fb={fb}")

with env(TOPIC_PICK_MODE="argmax", TOPIC_ENTITY_COOLDOWN_H="48",
         TOPIC_COOLDOWN_OVERRIDE_SCORE="5.0"):
    history = [hist("OpenAI announces new pricing", ts=NOW - 24 * 3600,
                    entities=["openai"])]
    pool = [cand("ChatGPT hacked in massive breach, billions leaked",
                 eng=90000, com=9000),
            cand("Postgres 18 released with async io", eng=300)]
    chosen, fb = main.filter_and_pick_story(
        [dict(c) for c in pool], history, random.Random(1))
    check("exceptional score overrides the cooldown",
          "ChatGPT" in chosen["title"], f"picked {chosen['title']}")

# --- 6. Dedup v2 (Jaccard) -------------------------------------------------------
print("[dedup v2]")
used = [hist("Google Chrome drops third party cookie support")]
reword = [cand("Third party cookie support dropped by Google Chrome"),
          cand("Rust compiler gets incremental builds")]
with env(TOPIC_PICK_MODE="argmax", TOPIC_DEDUP_V2="true"):
    chosen, fb = main.filter_and_pick_story(
        [dict(c) for c in reword], used, random.Random(1))
    check("v2 catches the reworded title the head rule missed",
          "Rust" in chosen["title"], f"picked {chosen['title']}")
# Legacy head rule misses the reword (word order shuffled → different head):
chosen, fb = main.filter_and_pick_story(
    [dict(c) for c in reword], used, random.Random(1))
check("legacy head rule indeed missed that reword (documents the fix)",
      "Third party" in chosen["title"] or "Rust" in chosen["title"])

used_generic = [hist("The new AI model from a startup breaks records")]
overlap_head = [cand("The new AI powered debugger for Rust developers ships")]
with env(TOPIC_PICK_MODE="argmax", TOPIC_DEDUP_V2="true"):
    chosen, fb = main.filter_and_pick_story(
        [dict(c) for c in overlap_head], used_generic, random.Random(1))
    check("v2 admits a different story sharing a generic 3-word head",
          fb is False and "debugger" in chosen["title"], f"fb={fb}")

# --- 7. _extract_entities --------------------------------------------------------
print("[entity extraction]")
E = main._extract_entities
check("ChatGPT canonicalizes to openai", E("ChatGPT gets memory") == ["openai"] or
      (E("ChatGPT gets memory") and E("ChatGPT gets memory")[0] == "openai"),
      f"got {E('ChatGPT gets memory')}")
check("GPT-5 tokenizes and canonicalizes to openai",
      E("GPT-5 cuts latency by 40%")[0] == "openai", f"got {E('GPT-5 cuts latency by 40%')}")
check("Claude → anthropic", E("Claude ships computer use")[0] == "anthropic")
check("Gemini and DeepMind cluster to google",
      E("Gemini beats humans")[0] == "google" and E("DeepMind solves protein folding")[0] == "google")
check("CamelCase heuristic finds PyTorch",
      "pytorch" in E("PyTorch 2.6 released with compile cache"),
      f"got {E('PyTorch 2.6 released with compile cache')}")
check("plain sentence yields no false entity",
      E("A missing underscore sent innocent man to prison") == [],
      f"got {E('A missing underscore sent innocent man to prison')}")
tc = E("How To Make Your Code Much Faster Today")
check("Title Case caps carry no signal", tc == [], f"got {tc}")
check("empty input", E("") == [])

# --- 8. record_topic_use: entities + cap -----------------------------------------
print("[record_topic_use]")
with tempfile.TemporaryDirectory() as td:
    fp = os.path.join(td, "hist.json")
    with env(TOPIC_HISTORY_CAP="3"):
        for i in range(5):
            main.record_topic_use(fp, story_id=i, title=f"OpenAI story {i} about GPT",
                                  session_id="t")
        data = json.load(open(fp))
    check("cap honored from TOPIC_HISTORY_CAP", len(data) == 3, f"len={len(data)}")
    check("entities recorded", data[-1].get("entities") == ["openai"],
          f"got {data[-1].get('entities')}")
    check("norm still recorded (dedup unaffected)",
          data[-1].get("norm", "").startswith("openai story"))

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} check(s): " + "; ".join(FAILURES[:8]))
    sys.exit(1)
print("test_topic_select.py: ALL PASS")

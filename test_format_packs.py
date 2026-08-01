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

# --- 3b. build_hn_news_prompt "no-ask" ending (M3) -------------------------------
print("[no-ask ending]")
p_default = main.build_hn_news_prompt("T", "B", seed=7, outro_appended=True)
p_none = main.build_hn_news_prompt("T", "B", seed=7, outro_appended=True, ending=None)
check("ending=None is byte-identical to the legacy call", p_default == p_none)
p_noask = main.build_hn_news_prompt("T", "B", seed=7, outro_appended=True, ending="no-ask")
check("no-ask drops the outro-card clause", "branded outro card is appended" not in p_noask)
check("no-ask drops the closer follow CTA", "Follow Neon Node for more tech" not in p_noask)
check("no-ask lands the payoff-and-stop directive",
      "ENDS the instant" in p_noask and "no follow/subscribe ask" in p_noask)

# --- 4. RenderRequest field ------------------------------------------------------
print("[RenderRequest]")
check("format_pack defaults to None", main.RenderRequest(prompt="x").format_pack is None)
check("format_pack accepts a pack name",
      main.RenderRequest(prompt="x", format_pack="quiz-reveal").format_pack == "quiz-reveal")

# --- 5. plan_pack_brief grounding (monkeypatched LLM) ----------------------------
print("[plan_pack_brief]")
ARTICLE = ("Postgres 18 ships built-in sharding. The new release cuts p99 latency "
           "to 40 milliseconds across 12 shards, per the announcement.")


def _with_llm(reply_json):
    real = main.query_llm_with_failover

    def fake(**kw):
        return reply_json
    main.query_llm_with_failover = fake
    return real


GOOD_QUIZ = ('{"question": "How low did Postgres 18 sharded p99 latency go", '
             '"options": ["40 milliseconds", "400 milliseconds", "4 seconds"], '
             '"answer_index": 0, '
             '"answer_fact": "The new release cuts p99 latency to 40 milliseconds across 12 shards."}')
_real_llm = _with_llm(GOOD_QUIZ)
try:
    b = main.plan_pack_brief("quiz-reveal", "Postgres 18 ships built-in sharding", ARTICLE)
    check("grounded quiz brief accepted", b is not None and b["kind"] == "quiz", f"got {b}")
    check("question normalized to question-form", b["question"].endswith("?"))
    check("answer resolved", b["options"][b["answer_index"]] == "40 milliseconds")

    _with_llm(GOOD_QUIZ.replace("40 milliseconds across 12 shards",
                                "17 milliseconds across 99 shards"))
    b2 = main.plan_pack_brief("quiz-reveal", "Postgres 18", ARTICLE)
    check("ungrounded answer_fact degrades to None", b2 is None, f"got {b2}")

    _with_llm('{"question": "Is 40 milliseconds the new Postgres p99", '
              '"options": ["40 milliseconds", "400 milliseconds", "4 seconds"], '
              '"answer_index": 0, '
              '"answer_fact": "The new release cuts p99 latency to 40 milliseconds across 12 shards."}')
    b3 = main.plan_pack_brief("quiz-reveal", "Postgres 18", ARTICLE)
    check("question containing the answer degrades", b3 is None, f"got {b3}")

    _with_llm('{"question": "How fast is it", "options": ["a", "b", "c"], '
              '"answer_index": 9, "answer_fact": "cuts p99 latency to 40 milliseconds"}')
    b4 = main.plan_pack_brief("quiz-reveal", "Postgres 18", ARTICLE)
    check("bad answer_index degrades", b4 is None)

    _with_llm('{"metric_label": "p99 latency", "unit": "ms", "insight": "sharding pays off", '
              '"series": [{"label": "Postgres 18", "value": 40}, {"label": "Shards", "value": 12}, '
              '{"label": "Postgres 17", "value": 400}, {"label": "Invented", "value": 77}]}')
    s5 = main.plan_pack_brief("data-rankings", "Postgres 18", ARTICLE + " Postgres 17 sat at 400.")
    check("series keeps only corpus-grounded values",
          s5 is not None and len(s5["series"]) == 3
          and all(p["value"] != 77 for p in s5["series"]), f"got {s5}")

    _with_llm('{"metric_label": "x", "series": [{"label": "a", "value": 40}, {"label": "b", "value": 12}]}')
    s6 = main.plan_pack_brief("data-rankings", "Postgres 18", ARTICLE)
    check("fewer than 3 grounded points degrades", s6 is None)
finally:
    main.query_llm_with_failover = _real_llm

# --- 6. apply_pack_postprocess ----------------------------------------------------
print("[apply_pack_postprocess]")
QUIZ_BRIEF = {"kind": "quiz",
              "question": "How low did Postgres 18 p99 latency go?",
              "options": ["40 milliseconds", "400 milliseconds", "4 seconds"],
              "answer_index": 0,
              "answer_fact": "The release cuts p99 latency to 40 milliseconds across 12 shards."}


def quiz_script(shape_ok=True):
    if shape_ok:
        return {"scenes": [
            {"type": "hero", "text": "The answer is 40 milliseconds!", "voiceover": "Guess the latency?",
             "searchQuery": "database servers", "durationInFrames": 120},
            {"type": "list", "title": "OPTIONS", "text": "pick", "voiceover": "Read them.",
             "listItems": ["wrong", "items"], "searchQuery": "database", "durationInFrames": 120},
            {"type": "countdown", "voiceover": "Three. Two. One.", "text": "",
             "searchQuery": "clock", "durationInFrames": 100},
            {"type": "metric", "title": "ANSWER", "text": "something", "voiceover": "made up claim",
             "searchQuery": "database", "durationInFrames": 120},
        ]}
    return {"scenes": [
        {"type": "hero", "text": "Latency news", "voiceover": "Big news today.",
         "searchQuery": "servers", "durationInFrames": 120},
        {"type": "split", "text": "stuff", "voiceover": "More stuff.",
         "searchQuery": "servers", "durationInFrames": 120},
    ]}


sc = quiz_script(True)
main.apply_pack_postprocess(sc, format_packs.resolve_pack("quiz-reveal"), QUIZ_BRIEF, "t")
scn = sc["scenes"]
check("options injected verbatim", scn[1]["listItems"] == QUIZ_BRIEF["options"])
check("correctIndex injected", scn[1]["correctIndex"] == 0)
check("countdown voiceover forced empty", scn[2]["voiceover"] == "")
check("reveal text/voiceover = verified answer/fact",
      scn[3]["text"] == "40 milliseconds" and scn[3]["voiceover"] == QUIZ_BRIEF["answer_fact"])
check("hook spoiler scrubbed", "40 milliseconds" not in scn[0].get("text", ""),
      f"hook text: {scn[0].get('text')}")

sc = quiz_script(False)
main.apply_pack_postprocess(sc, format_packs.resolve_pack("quiz-reveal"), QUIZ_BRIEF, "t")
scn = sc["scenes"]
check("broken shape rebuilds to 4 scenes",
      [s["type"] for s in scn] == ["hero", "list", "countdown", "metric"], f"got {[s['type'] for s in scn]}")
check("rebuilt countdown is silent + 90 frames",
      scn[2]["voiceover"] == "" and scn[2]["durationInFrames"] == 90)
est = main._estimate_spoken_seconds(scn, "edge")
check("rebuilt quiz lands near its band", 10 <= est <= 28, f"est={est:.1f}s")

sc = quiz_script(True)
main.apply_pack_postprocess(sc, format_packs.resolve_pack("quiz-reveal"), QUIZ_BRIEF, "t",
                            force_rebuild=True)
check("force_rebuild rebuilds even a good shape",
      sc["scenes"][0]["text"] == QUIZ_BRIEF["question"])

SERIES_BRIEF = {"kind": "series", "metric_label": "p99 latency", "unit": "ms",
                "insight": "sharding pays off",
                "series": [{"label": "PG 18", "value": 40}, {"label": "PG 17", "value": 400},
                           {"label": "MySQL", "value": 120}]}
sc = {"scenes": [{"type": "hero", "text": "x", "voiceover": "y", "searchQuery": "db",
                  "durationInFrames": 120}]}
main.apply_pack_postprocess(sc, format_packs.resolve_pack("data-rankings"), SERIES_BRIEF, "t")
scn = sc["scenes"]
check("series rebuild: chart ascending, leader last",
      scn[1]["chartData"][-1]["label"] == "PG 17" and scn[1]["chartData"][0]["label"] == "PG 18")
check("series reveal names the leader", scn[2]["text"] == "PG 17")

# --- 7. Gate pack-awareness -------------------------------------------------------
print("[gate pack-awareness]")
qmeta = {"subject": "Postgres 18"}
quiz_ok = {"scenes": [
    {"type": "hero", "text": "How low did the latency go?", "voiceover": "Can you guess the number?",
     "searchQuery": "db", "durationInFrames": 120},
    {"type": "list", "title": "OPTIONS", "voiceover": "Pick one now. Lock in your answer.",
     "listItems": ["a", "b", "c"], "searchQuery": "db", "durationInFrames": 120},
    {"type": "countdown", "voiceover": "", "searchQuery": "db", "durationInFrames": 90},
    {"type": "metric", "text": "40 ms", "voiceover": "Postgres eighteen cuts p ninety-nine latency to forty milliseconds.",
     "searchQuery": "db", "durationInFrames": 120},
]}
h, s = main._script_vagueness_reasons(quiz_ok, "", qmeta, format_pack="quiz-reveal")
check("quiz with subject in reveal passes H2", not any("never named" in r for r in h), f"hard={h}")
check("quiz imperative middles not flagged", not any("advice" in r for r in h + s), f"{h+s}")
check("question hook passes H4", not any("question-form" in r for r in h))

quiz_bad_hook = {"scenes": [dict(quiz_ok["scenes"][0], text="The latency dropped a lot.",
                                 voiceover="Latency dropped hard this week.")] + quiz_ok["scenes"][1:]}
h2c, _ = main._script_vagueness_reasons(quiz_bad_hook, "", qmeta, format_pack="quiz-reveal")
check("statement hook fails H4 for quiz", any("question-form" in r for r in h2c), f"hard={h2c}")

# --- Result ---------------------------------------------------------------------
print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} check(s): " + "; ".join(FAILURES[:8]))
    sys.exit(1)
print("test_format_packs.py: ALL PASS")

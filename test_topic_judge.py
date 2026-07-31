#!/usr/bin/env python3
"""
CI Topic Judge — Regression Tests
=================================
Locks the behaviour of the single-story editorial judge (plan_story_angle),
the shared fact-grounding helper (_ground_facts), the plan-enriched
build_hn_news_prompt, and the vague-verdict re-pick composition used by
generate_now.py.

Contracts pinned here:
  * _ground_facts is the behaviour the old inline block in _llm_rank_and_angle
    had — the refactor must stay behavior-preserving.
  * plan_story_angle returns None ONLY on LLM/parse failure, {"subject": ""}
    on a vague-story verdict, and never raises.
  * build_hn_news_prompt(plan=None) is byte-identical to the plan-less call —
    the judge degrading must reproduce today's prompt exactly (including the
    outro_appended follow-ask contract).

Usage:
  python test_topic_judge.py          # run all, exit 0/1
  python test_topic_judge.py -v       # verbose
"""

import random
import sys

import main

VERBOSE = "-v" in sys.argv
FAILURES = []


def check(cond, msg):
    if VERBOSE:
        print(("  ok  " if cond else "  ✗   ") + msg)
    if not cond:
        FAILURES.append(msg)


def test_ground_facts():
    corpus = ("SaltCell announced a sodium-ion battery that retains 92.3 percent "
              "capacity after 3,000 charge cycles at a projected 87 dollars per kWh.")
    kept = main._ground_facts(["Retains 92.3 percent capacity after 3,000 cycles"], corpus)
    check(len(kept) == 1, "_ground_facts keeps a fact whose numbers and words appear in the corpus")
    kept = main._ground_facts(["It handles 12,400 requests per second"], corpus)
    check(kept == [], "_ground_facts drops a fact whose number is absent from the corpus")
    kept = main._ground_facts(["Quantum entanglement drives the flux capacitor mainframe"], corpus)
    check(kept == [], "_ground_facts drops a fact with <0.5 word overlap")
    kept = main._ground_facts([], corpus)
    check(kept == [], "_ground_facts on empty input returns empty")


def _with_fake_llm(fake, fn):
    """Run fn() with main.query_llm_with_failover monkeypatched."""
    orig = main.query_llm_with_failover
    main.query_llm_with_failover = fake
    try:
        return fn()
    finally:
        main.query_llm_with_failover = orig


def test_plan_story_angle():
    title = "SaltCell sodium-ion battery retains 92.3% after 3,000 cycles"
    body = ("SaltCell published peer-reviewed results showing 92.3 percent capacity "
            "retention after 3,000 charge cycles, at a projected pack cost of 87 "
            "dollars per kWh compared to 135 for lithium.")
    good_json = ('{"subject": "SaltCell battery", "angle": "Salt chemistry just beat lithium on endurance.", '
                 '"hook": "Salt just outlived lithium", '
                 '"insight": "Grid storage gets cheap cells that refuse to die.", '
                 '"facts": ["92.3 percent capacity retained after 3,000 charge cycles", '
                 '"Projected pack cost 87 dollars per kWh"], "format": "news"}')

    plan = _with_fake_llm(lambda **kw: good_json,
                          lambda: main.plan_story_angle(title, body, url="https://x", session_id="test"))
    check(isinstance(plan, dict) and plan.get("subject") == "SaltCell battery",
          "strict JSON reply yields a full plan")
    check(plan and len(plan.get("facts") or []) == 2,
          "facts copied from the article survive grounding")
    check(plan and plan.get("insight", "").startswith("Grid storage"),
          "insight field carried through")
    check(plan and plan.get("url") == "https://x", "url carried through")

    fenced = "```json\n" + good_json + "\n```"
    plan = _with_fake_llm(lambda **kw: fenced,
                          lambda: main.plan_story_angle(title, body, session_id="test"))
    check(isinstance(plan, dict) and plan.get("subject") == "SaltCell battery",
          "fenced JSON reply is recovered")

    thinky = "<think>let me judge this article</think>" + good_json
    plan = _with_fake_llm(lambda **kw: thinky,
                          lambda: main.plan_story_angle(title, body, session_id="test"))
    check(isinstance(plan, dict) and plan.get("subject") == "SaltCell battery",
          "<think>-wrapped JSON reply is recovered")

    plan = _with_fake_llm(lambda **kw: "sorry, I can't do JSON today",
                          lambda: main.plan_story_angle(title, body, session_id="test"))
    check(plan is None, "garbage reply returns None (parse failure)")

    def boom(**kw):
        raise RuntimeError("provider chain down")
    plan = _with_fake_llm(boom, lambda: main.plan_story_angle(title, body, session_id="test"))
    check(plan is None, "raising provider returns None, never raises")

    plan = _with_fake_llm(lambda **kw: '{"subject": ""}',
                          lambda: main.plan_story_angle(title, body, session_id="test"))
    check(plan == {"subject": ""}, "vague-story verdict returns {'subject': ''}")

    ungrounded = ('{"subject": "SaltCell battery", "angle": "a", "hook": "h", "insight": "i", '
                  '"facts": ["It ships with a 999 terawatt flux core"], "format": "news"}')
    plan = _with_fake_llm(lambda **kw: ungrounded,
                          lambda: main.plan_story_angle(title, body, session_id="test"))
    check(isinstance(plan, dict) and plan.get("facts") == [],
          "ungrounded facts are dropped, plan survives with facts=[]")


def test_build_hn_news_prompt_plan():
    t, b = "Postgres 18 ships 3x faster upserts", ("The release notes describe a new btree "
                                                   "fastpath that skips the second index descent.")
    for outro in (True, False):
        base = main.build_hn_news_prompt(t, b, seed=42, outro_appended=outro)
        with_none = main.build_hn_news_prompt(t, b, seed=42, outro_appended=outro, plan=None)
        check(base == with_none, f"plan=None output byte-identical (outro_appended={outro})")
        empty_subject = main.build_hn_news_prompt(t, b, seed=42, outro_appended=outro, plan={"subject": ""})
        check(base == empty_subject, f"plan with empty subject degrades identically (outro_appended={outro})")
        check("EDITORIAL PLAN" not in base, "no EDITORIAL PLAN block without a plan")

    plan = {"subject": "Postgres 18", "angle": "Upserts got 3x faster overnight.",
            "hook": "Your upserts just got faster",
            "insight": "Write-heavy apps get the win without changing a line.",
            "facts": ["3x faster upserts", "btree fastpath skips the second descent"]}
    full = main.build_hn_news_prompt(t, b, seed=42, outro_appended=True, plan=plan)
    for marker in ("EDITORIAL PLAN", "- SUBJECT: Postgres 18", "- ANGLE:", "- PAYOFF:",
                   "VERIFIED FACTS", "The takeaway to land:", 'Open with this energy: "Your upserts'):
        check(marker in full, f"plan-enriched prompt contains {marker!r}")
    for legacy in ("NEWS SOURCE DETAILS", "CONCRETENESS CONTRACT",
                   "branded outro card is appended automatically"):
        check(legacy in full, f"legacy marker survives plan enrichment: {legacy!r}")

    no_follow = main.build_hn_news_prompt(t, b, seed=42, outro_appended=False, plan=plan)
    check("Follow Neon Node for more tech" in no_follow,
          "outro_appended=False keeps the closer's own follow CTA")
    check("branded outro card" not in no_follow,
          "outro_appended=False has no outro-card clause")

    factless = dict(plan, facts=[])
    out = main.build_hn_news_prompt(t, b, seed=42, outro_appended=True, plan=factless)
    check("VERIFIED FACTS" not in out, "factless plan has no VERIFIED FACTS line")
    check("do NOT add numbers, people, or quotes beyond it" in out,
          "factless plan carries the invent-nothing bullet")


def test_repick_composition():
    """The synthetic history entry generate_now.py appends on a vague verdict
    must exclude the rejected pick from the next filter_and_pick_story call."""
    candidates = [
        {"source": "hackernews", "title": "SaltCell battery outlives lithium in new study",
         "subject": "SaltCell battery outlives lithium in new study", "url": "u1",
         "engagement": 300, "comments": 120, "age_hours": 4.0, "meta": "", "_hn_id": 111},
        {"source": "hackernews", "title": "Postgres 18 ships builtin sharding",
         "subject": "Postgres 18 ships builtin sharding", "url": "u2",
         "engagement": 250, "comments": 90, "age_hours": 6.0, "meta": "", "_hn_id": 222},
    ]
    rejected = candidates[0]
    history = [{
        "id": str(rejected["_hn_id"]),
        "title": rejected["title"],
        "norm": main._normalize_subject(rejected["title"]),
        "ts": 1,
    }]
    for trial in range(20):
        pick, was_fallback = main.filter_and_pick_story(
            list(candidates), history, random.Random(trial), top_n=5)
        if pick["_hn_id"] == 111 or was_fallback:
            check(False, f"re-pick returned the excluded story (trial {trial}, fallback={was_fallback})")
            return
    check(True, "re-pick never returns the excluded story while fresh candidates remain")


def main_():
    for fn in (test_ground_facts, test_plan_story_angle,
               test_build_hn_news_prompt_plan, test_repick_composition):
        if VERBOSE:
            print(f"{fn.__name__}:")
        fn()
    if FAILURES:
        print(f"\nFAIL — {len(FAILURES)} problem(s):")
        for f in FAILURES:
            print(f"  ✗ {f}")
        sys.exit(1)
    print("OK — topic judge, grounding, prompt enrichment and re-pick pins all green.")
    sys.exit(0)


if __name__ == "__main__":
    main_()

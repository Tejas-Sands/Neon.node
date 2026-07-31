#!/usr/bin/env python3
"""
Script Insight Gate — Regression Tests
======================================
Locks the behaviour of the deterministic script vagueness gate
(_script_vagueness_reasons), the breakthrough-vs-advice topic scoring
(score_virality / _ADVICE_TITLE_RE), and the insight-arc prompt contracts.

WHY THIS FILE EXISTS
--------------------
Auto videos shipped with vague topics and generic "do this, do that" advice
content. The fix has three legs — advice-penalized topic scoring, an insight
arc in every script prompt, and a hard/soft script gate that re-asks and (on
auto channels) aborts rather than posting a platitude video. Like the caption
gate before it (test_caption_gate.py), the failure mode returns the moment the
checks are verified ad hoc instead of pinned — this file is the pin.

HARD reasons abort auto channels after all retries; SOFT reasons only trigger
a corrective re-ask. Every ACCEPT case below must therefore stay hard-clean —
a false hard-positive costs one of the day's posting slots.

Usage:
  python test_script_gate.py          # run all, exit 0/1
  python test_script_gate.py -v       # verbose: print reasons per case
"""

import copy
import inspect
import sys

import main

VERBOSE = "-v" in sys.argv


def scene(type_="split", title="", text="", subtitle="", voiceover="", **kw):
    s = {"type": type_, "title": title, "text": text, "subtitle": subtitle,
         "voiceover": voiceover, "searchQuery": "tech abstract", "durationInFrames": 150}
    s.update(kw)
    return s


# --- Scripts that must trip a HARD reason ------------------------------------
# name -> (script, source_prompt, topic_meta)
REJECT_HARD = {
    # Two platitude phrases, zero numbers anywhere -> H1.
    "platitude video": (
        {"scenes": [
            scene("hero", "THE AI SHIFT", "everything is different",
                  voiceover="AI is changing everything about how we work."),
            scene("split", "NEW TOOLS", "smarter workflows",
                  voiceover="These tools make your life easier every single day."),
            scene("split", "THE FUTURE", "it is coming",
                  voiceover="The workplace of tomorrow will look nothing like today."),
            scene("cta", "GET READY", "adapt now",
                  voiceover="The ones who adapt early will win."),
        ]}, "", None),

    # >=50% imperative mid scenes + no subject + no numbers -> H3.
    "generic productivity advice": (
        {"scenes": [
            scene("hero", "DEEP WORK", "your focus is broken",
                  voiceover="Your workday is quietly falling apart."),
            scene("split", "BLOCK IT", "calendar first",
                  voiceover="Start time-blocking your calendar every single morning."),
            scene("split", "ONE THING", "no context switching",
                  voiceover="Stop multitasking — batch similar work together instead."),
            scene("split", "PROTECT IT", "guard the hours",
                  voiceover="Remember to guard your focus and take real breaks."),
            scene("cta", "OWN YOUR DAY", "focus wins",
                  voiceover="Win the morning and the day follows."),
        ]}, "", None),

    # Known subject never named in the hook -> H2.
    "subject never named in hook": (
        {"scenes": [
            scene("hero", "MODEL LEAK", "the weights are out",
                  voiceover="A huge AI model just leaked overnight."),
            scene("metric", "SIZE", "671B parameters",
                  voiceover="The leaked checkpoint weighs in at six hundred seventy one billion parameters."),
            scene("split", "WHY IT MATTERS", "open weights",
                  voiceover="Anyone can now fine-tune it locally without a license."),
        ]}, "", {"subject": "DeepSeek V4"}),

    # Single platitude hit in a numbers-free script -> H1 (single-hit rule).
    "one game-changer, zero numbers": (
        {"scenes": [
            scene("hero", "TINY COMPILER", "embedded first",
                  voiceover="This tiny compiler is a game changer for embedded work."),
            scene("split", "SMALL FOOTPRINT", "fits anywhere",
                  voiceover="It compiles straight to bare metal with no runtime attached."),
            scene("split", "WHO NEEDS IT", "firmware teams",
                  voiceover="Firmware teams get modern tooling on ancient chips."),
        ]}, "", None),
}

# --- Scripts that must stay HARD-clean ---------------------------------------
# name -> (script, source_prompt, topic_meta, allow_soft)
ACCEPT = {
    # Concrete tech story modeled on few-shot Example 1.
    "concrete tech script": (
        {"scenes": [
            scene("hero", "MEET HYPERAPI", "20ms, not 200ms", "your gateway is the bottleneck",
                  voiceover="Your API gateway is the slowest hop in your whole stack — HyperAPI just fixed that."),
            scene("comparison", "THE DIFFERENCE", "200ms", secondaryText="20ms",
                  voiceover="Where old gateways burn two hundred milliseconds per request, it answers in twenty."),
            scene("list", "ZERO SETUP TAX", "Auto-scaling|Edge cache|Zero-config SSL",
                  voiceover="None of it needs configuring — scaling, caching and certificates switch on at deploy."),
            scene("cta", "PUT IT IN FRONT", "free tier, no card",
                  voiceover="Drop it in front of your API today — the free tier needs no credit card."),
        ]}, "", {"subject": "HyperAPI"}, False),

    # Policy story with no stats: concrete and numberless must still ship.
    "no-stats policy story": (
        {"scenes": [
            scene("hero", "THE BAN IS LAW", "real-time face scans", "public spaces",
                  voiceover="The EU AI Act now bans real-time face scanning in public spaces."),
            scene("split", "WHAT CHANGED", "biometric surveillance",
                  voiceover="Live biometric surveillance by police now needs a court order per deployment."),
            scene("split", "WHO IT HITS", "vendors first",
                  voiceover="Vendors selling scanning systems in Europe must recertify under the act."),
            scene("split", "WHY IT MATTERS", "precedent set",
                  voiceover="It is the first outright ban of a deployed AI category anywhere."),
        ]}, "The EU AI Act entered into force with a ban on real-time biometric identification.",
        {"subject": "EU AI Act"}, False),

    # Spelled-out numbers count as numbers (few-shot voiceover convention).
    "spelled-numbers-only script": (
        {"scenes": [
            scene("hero", "THE SALT BATTERY", "no lithium inside",
                  voiceover="A battery built on table-salt chemistry just survived three thousand charges."),
            scene("split", "HOW IT SURVIVES", "sodium swaps in",
                  voiceover="Its electrode keeps sodium ions from cracking the structure as they cycle."),
            scene("split", "THE RETENTION", "capacity holds",
                  voiceover="It kept ninety two percent of its capacity across the whole endurance test."),
            scene("split", "WHY IT MATTERS", "grid storage first",
                  voiceover="Cheap cells that refuse to die are exactly what solar farms need at night."),
        ]}, "", None, False),

    # Imperative hook + imperative CTA are exempt from the advice check.
    "imperative hook and cta": (
        {"scenes": [
            scene("hero", "STOP SCROLLING", "agents shipped",
                  voiceover="Stop scrolling — Cursor just shipped background agents."),
            scene("metric", "PARALLEL RUNS", "8 at once",
                  voiceover="It runs eight isolated agents in parallel on one repository."),
            scene("split", "HOW IT WORKS", "worktree per agent",
                  voiceover="Each agent gets its own checkout, so edits never collide."),
            scene("cta", "TRY IT", "on your own repo",
                  voiceover="Try it on your own repo today and watch the queue drain."),
        ]}, "", {"subject": "Cursor"}, False),

    # A single stray platitude in an otherwise number-rich script downgrades
    # to SOFT — a re-ask, never an abort.
    "single platitude with numbers is soft": (
        {"scenes": [
            scene("hero", "POSTGRES 18", "3x faster upserts",
                  voiceover="Postgres eighteen makes upserts three times faster out of the box."),
            scene("split", "THE MECHANISM", "btree fastpath",
                  voiceover="A new btree fastpath skips the second index descent — a real game changer."),
            scene("metric", "THE NUMBER", "3x",
                  voiceover="Benchmarks show writes finishing in a third of the time."),
        ]}, "", {"subject": "Postgres 18"}, True),
}


def run_gate_cases():
    failures = []
    for name, (script, src, meta) in REJECT_HARD.items():
        before = copy.deepcopy(script)
        hard, soft = main._script_vagueness_reasons(script, src, meta)
        if VERBOSE:
            print(f"[REJECT] {name}: hard={hard} soft={soft}")
        if not hard:
            failures.append(f"REJECT '{name}': expected a HARD reason, got none (soft={soft})")
        if script != before:
            failures.append(f"REJECT '{name}': gate MUTATED the script")
    for name, (script, src, meta, allow_soft) in ACCEPT.items():
        before = copy.deepcopy(script)
        hard, soft = main._script_vagueness_reasons(script, src, meta)
        if VERBOSE:
            print(f"[ACCEPT] {name}: hard={hard} soft={soft}")
        if hard:
            failures.append(f"ACCEPT '{name}': unexpected HARD reason(s): {hard}")
        if not allow_soft and soft:
            failures.append(f"ACCEPT '{name}': unexpected SOFT reason(s): {soft}")
        if allow_soft and not soft:
            failures.append(f"ACCEPT '{name}': expected a SOFT reason, got none")
        if script != before:
            failures.append(f"ACCEPT '{name}': gate MUTATED the script")
    return failures


def run_scorer_cases():
    failures = []

    def cand(title):
        return {"title": title, "meta": "", "engagement": 100, "comments": 50, "age_hours": 5.0}

    news = main.score_virality(cand("OpenAI releases GPT-6 with 10x context window"))
    listicle = main.score_virality(cand("10 VS Code tips to boost your productivity"))
    if not news > listicle:
        failures.append(f"scorer: breakthrough title ({news:.2f}) must outrank listicle ({listicle:.2f})")

    # Regression pin for the ask-hn multiplier bug: 1.2 used to BOOST Ask HN.
    base = main.score_virality(cand("Is AI killing the developer job market?"))
    askhn = main.score_virality(cand("Ask HN: Is AI killing the developer job market?"))
    if not askhn < base:
        failures.append(f"scorer: 'Ask HN:' prefix must LOWER the score (base={base:.2f}, askhn={askhn:.2f})")

    # The flat advice penalty must catch kw==0 listicles VIRAL_NEGATIVES can't.
    for t in ("10 productivity tips for remote developers",
              "How to structure your Go project",
              "Why you should quit VS Code",
              "Ask HN: favorite hardware?",
              "Thoughts on microservices"):
        if not main._ADVICE_TITLE_RE.search(t):
            failures.append(f"_ADVICE_TITLE_RE must match advice title: {t!r}")
    for t in ("OpenAI releases 3 new tools for agents",
              "Zig 0.14 released",
              "How we cut S3 costs by 90%",
              "Postgres 17 ships builtin sharding"):
        if main._ADVICE_TITLE_RE.search(t):
            failures.append(f"_ADVICE_TITLE_RE must NOT match news title: {t!r}")

    for mult in main.VIRAL_NEGATIVES.values():
        if mult >= 1.0:
            failures.append("VIRAL_NEGATIVES must all be < 1.0 (multipliers; >=1.0 is a boost)")
            break
    return failures


def run_prompt_pins():
    failures = []
    if "INSIGHT, NOT INSTRUCTIONS" not in main.SYSTEM_PROMPT:
        failures.append("SYSTEM_PROMPT lost rule 14c (INSIGHT, NOT INSTRUCTIONS)")
    news_prompt = main.build_hn_news_prompt("t", "body", seed=1)
    if "HOW it actually works" not in news_prompt:
        failures.append("build_hn_news_prompt lost the insight-arc contract")
    if any("This changes everything" in p for p in main.HOOK_PATTERNS):
        failures.append("HOOK_PATTERNS teaches the banned 'This changes everything' template again")
    viral = main.build_viral_topic_prompt({
        "subject": "SaltCell", "angle": "a", "hook": "h",
        "insight": "grid storage gets cheaper", "facts": [], "format": "news"})
    if "WHY IT MATTERS" not in viral or "grid storage gets cheaper" not in viral:
        failures.append("build_viral_topic_prompt drops the insight payoff bullet")
    ranker_src = inspect.getsource(main._llm_rank_and_angle)
    if "explainer|hot-take|news|comparison" not in ranker_src or "news|listicle" in ranker_src:
        failures.append("_llm_rank_and_angle re-offers the 'listicle' format in its JSON schema")
    return failures


def main_():
    failures = run_gate_cases() + run_scorer_cases() + run_prompt_pins()
    total = len(REJECT_HARD) + len(ACCEPT)
    if failures:
        print(f"\nFAIL — {len(failures)} problem(s):")
        for f in failures:
            print(f"  ✗ {f}")
        sys.exit(1)
    print(f"OK — {total} gate cases + scorer + prompt pins all green.")
    sys.exit(0)


if __name__ == "__main__":
    main_()

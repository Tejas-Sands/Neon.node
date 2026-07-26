#!/usr/bin/env python3
"""
Caption Sanity Gate — Regression Tests
======================================
Locks the behaviour of the social-caption quality gate in main.py.

WHY THIS FILE EXISTS
--------------------
Three captions have reached production as raw LLM drafting output:

  2026-07-26  media 18091192478101049   caption was literally "->"
  2026-07-26  media 18106597351859978   '75 chars) * Value 2: "..." (81 chars) * Value'
  2026-07-26  media 18608323627060667   'Progress? * *Draft 2:* Will hardware bottlenecks
                                         ... * *Draft 3:* Can software optimization ...'

The first two produced _sanitize_caption (commit 66c31d2c). The third shipped the
NEXT DAY, straight through that new gate, because the fix was verified ad hoc and
never pinned by a test. This file is that pin.

Every string below is either a real shipped caption or a real failure shape. Do not
delete cases to make a change pass — a rejected caption costs one bland post, but a
caption like the ones above is publicly attached to the account.

Usage:
  python test_caption_gate.py          # run all, exit 0/1
  python test_caption_gate.py -v       # also print each caption under test
"""

import sys

import main

# --- Must be REJECTED (gate returns "") -------------------------------------
# name -> caption
REJECT = {
    # The incident this file was written for. Inline markdown bullets + "Draft N:"
    # labels; the pre-fix regex missed it because the bullet tell was ^-anchored
    # AND required \w after the bullet, and "Draft" was not a known label.
    "shipped: three-draft list (media 18608323627060667)":
        "Progress? * *Draft 2:* Will hardware bottlenecks completely decide the "
        "winner of the AI race? * *Draft 3:* Can software optimization overcome "
        "this massive silicon shortage\n\n#deepseek #leak #leaked "
        "#softwareengineering #webdevelopment #devops #tech #coding",

    "shipped: bare arrow (media 18091192478101049)": "->",

    "shipped: drafting notes (media 18106597351859978)":
        '75 chars) * Value 2: "..." (81 chars) * Value',

    "numbered options at line start":
        "Option 1: Nvidia just cut prices.\nOption 2: The GPU war is over.",

    "bold draft labels":
        "Here are 3 options:\n\n**Draft 1:** one\n**Draft 2:** two",

    "plain draft labels":
        "Draft 1: Android locks down ADB for good.\n"
        "Draft 2: Sideloading gets harder starting today.",

    # max_tokens cut. Never detected upstream: query_llm_with_failover only checks
    # finish_reason == "length" when json_format=True, and captions pass False.
    "truncated mid-sentence":
        "Nvidia just told regulators to back off open weights. The filing argues "
        "licensing would freeze small labs",

    "list of candidate hooks (3+ questions)":
        "Is this the end? Will it scale? Should you care about any of this today?",

    "reasoning voice":
        "Let me write a caption about the new Android ADB restrictions and how "
        "they land for developers.",

    "echoed section labels":
        "HOOK: Android locks down ADB\n"
        "VALUE: the shell user loses install rights on unrooted builds",

    "markdown bullet list":
        "- Nvidia cut prices today\n- Meta shipped a new model\n- Everyone panicked",

    "hashtags with no caption body":
        "#tech #coding #devops #ai #llm #python #rust #linux",

    "empty": "",
}

# --- Must PASS THROUGH (gate returns non-empty) ------------------------------
ACCEPT = {
    "normal caption with hashtags":
        "🚀 DeepSeek's unreleased model config leaked from a public repo.\n\n"
        "⚡ 685B parameters — larger than V3.\n"
        "🧠 Pulled 40 minutes later, but the mirrors were already up.\n\n"
        "Would you ship from a repo that public? 👇\n\n"
        "#deepseek #llm #opensource #tech #coding",

    "normal caption, hashtags backfilled later":
        "Android is about to lock down on-device ADB.\n\n"
        "🔒 The shell user loses install rights on unrooted builds.\n"
        "🧪 Dev options stay, but sideloading gets a second confirm.\n\n"
        "Does this break your workflow?",

    # The <think> stripper must salvage this, not reject it.
    "<think>-wrapped caption":
        "<think>I should mention the params</think>GraphQL subscriptions replace "
        "polling entirely.\n\n⚡ Ten requests become one.\n\n"
        "Would you ship this? 👇\n\n#graphql #api #webdevelopment",

    # Regression guards for false positives found while writing the gate:
    # an unanchored "draft label" rule ate both of these.
    "prose containing 'version <number>.'":
        "Python version 3.13 drops the GIL for real this time.\n\n"
        "🐍 Free-threaded builds ship as an official option.\n\n"
        "Upgrading yet? 👇\n\n#python #performance #coding",

    "prose containing 'options'":
        "Android hides developer options behind a new toggle.\n\n"
        "🔧 The ADB switch now resets after each reboot.\n\n"
        "Annoying or overdue? 👇\n\n#android #mobiledev #tech",

    "em dash mid-sentence (not a bullet)":
        "Rust async closures landed — and they change how you write executors.\n\n"
        "⚙️ No more boxing every future you hand to a spawner.\n\n"
        "Worth the upgrade? 👇\n\n#rustlang #async #tech",

    "two questions is still a caption":
        "Kimi K3 exploited a live Redis server in a benchmark run.\n\n"
        "🔓 It chained a known CVE without being told the version.\n\n"
        "Is your Redis exposed? Would you have caught it? 👇\n\n#infosec #llm",
}


def _run(verbose: bool = False) -> int:
    failures = []

    print("=== captions that must be REJECTED ===")
    for name, caption in REJECT.items():
        got = main._sanitize_caption(caption, "test")
        ok = (got == "")
        if not ok:
            failures.append(f"NOT rejected: {name} -> {got[:80]!r}")
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}")
        if verbose:
            print(f"        {caption[:100]!r}")

    print("\n=== captions that must PASS ===")
    for name, caption in ACCEPT.items():
        got = main._sanitize_caption(caption, "test")
        ok = bool(got)
        if not ok:
            failures.append(f"wrongly rejected: {name}")
        print(f"  {'ok  ' if ok else 'FAIL'}  {name}")
        if verbose:
            print(f"        {caption[:100]!r}")

    print("\n=== deterministic narration fallback ===")
    # The fallback ships whenever the LLM is unusable, so it must itself be a
    # caption — not the bland filler it replaced, and never something the gate
    # would have rejected.
    scenes = {"scenes": [
        {"voiceover": "Three years of real-time data lessons in thirty seconds."},
        {"voiceover": "It enables real-time data without polling."},
        {"voiceover": "Where polling requires ten requests, subscriptions need just one."},
    ]}
    built = main._build_narration_caption(scenes, {"subject": "GraphQL subscriptions"})
    checks = [
        ("uses real narration", "ten requests" in built),
        ("no 60-second-breakdown filler", "60-second breakdown" not in built),
        ("survives the gate", bool(main._sanitize_caption(built, "test"))),
    ]
    # Must not fall over when there is nothing to work with.
    for label, data, topic in (
        ("empty scenes", {"scenes": []}, {"subject": "DeepSeek model leak"}),
        ("nothing at all", {}, {"subject": "", "title": ""}),
    ):
        out = main._build_narration_caption(data, topic)
        checks.append((f"{label} still yields a caption",
                       bool(main._sanitize_caption(out, "test"))))
    for label, ok in checks:
        if not ok:
            failures.append(f"fallback: {label}")
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
    if verbose:
        print(f"\n{built}\n")

    print("\n=== hashtags ===")
    tag_checks = [
        ("leak/leaked collapse to one stem",
         main._dedupe_by_stem(["deepseek", "leak", "leaked"]) == ["deepseek", "leak"]),
        ("curated pools survive stem dedupe",
         len(main._dedupe_by_stem(main._CATEGORY_TAG_POOL + main._EVERGREEN_TAG_POOL))
         == len(main._CATEGORY_TAG_POOL + main._EVERGREEN_TAG_POOL)),
    ]
    for label, ok in tag_checks:
        if not ok:
            failures.append(f"hashtags: {label}")
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}")

    print("\n=== fabrication guard (must stay exactly as strong) ===")
    multiline = ("DeepSeek's unreleased config leaked from a public repo.\n\n"
                 "⚡ 685B parameters, larger than V3.\n"
                 "\U0001f9e0 Pulled 40 minutes later.\n\n"
                 "Would you ship from a repo that public? \U0001f449")
    guard_checks = [
        # Unchanged behaviour — invented attributions still stripped.
        ("invented 'role name says' stripped",
         "John Doe" not in main._scrub_fabricated_people(
             "the lead developer John Doe says the mesh routes tokens locally",
             "", "test", "t")),
        ("invented 'according to' stripped",
         "Jane Smith" not in main._scrub_fabricated_people(
             "According to Jane Smith, the model runs on a single GPU.",
             "", "test", "t")),
        ("real person named in the prompt is kept",
         "Linus Torvalds" in main._scrub_fabricated_people(
             "According to Linus Torvalds, the patch is fine.",
             "linus torvalds wrote about the patch", "test", "t")),
        # The fix: the cosmetic tidy-up used to be a blanket \s{2,} collapse, which
        # flattened every multi-line caption into one run-on paragraph.
        ("multi-line caption keeps its line breaks",
         main._scrub_fabricated_people(multiline, "", "test", "ig_caption") == multiline),
    ]
    for label, ok in guard_checks:
        if not ok:
            failures.append(f"fabrication guard: {label}")
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}")

    print("\n=== Instagram length clamp ===")
    tags = "#deepseek #llm #opensource #tech #coding #devops #python #webdevelopment"
    long_caption = ("Nvidia told regulators to back off open weight models. " * 60).strip() \
        + "\n\n" + tags
    clamped = main._clamp_ig_caption(long_caption, "test")
    short_caption = "A perfectly normal caption.\n\n" + tags
    clamp_checks = [
        ("over-long caption is clamped under the IG limit",
         len(clamped) <= main.INSTAGRAM_CAPTION_LIMIT),
        ("hashtag line survives the clamp", clamped.endswith(tags)),
        ("short caption is left untouched",
         main._clamp_ig_caption(short_caption, "test") == short_caption),
    ]
    for label, ok in clamp_checks:
        if not ok:
            failures.append(f"clamp: {label}")
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}")

    total = (len(REJECT) + len(ACCEPT) + len(checks)
             + len(tag_checks) + len(guard_checks) + len(clamp_checks))
    print()
    if failures:
        print(f"FAILED ({len(failures)}/{total}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"All {total} caption-gate checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(_run(verbose="-v" in sys.argv))

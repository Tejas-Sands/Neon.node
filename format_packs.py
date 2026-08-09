"""Format-pack registry: one content format = runtime band + script contract
+ ending mode + visual sourcing mode.

Pure data + pure functions ONLY. This module must never import main — the
generate_now.py entry point imports both, and main.py imports this registry,
so a main import here would be circular.

A pack decides WHAT SHAPE a video takes (script contract, runtime band,
whether stock b-roll is fetched, how the video ends); the per-video seed and
the Look System keep deciding how it LOOKS. resolve_pack(None) returns the
legacy pack, and every consumer treats the legacy pack as "behave exactly as
before this module existed" — pinned by test_format_packs.py.

Pack fields:
  band         (min_sec, max_sec) spoken-runtime band, or None = defer to the
               env-tunable MIN_SPOKEN_SEC/MAX_SPOKEN_SEC globals in main.py
               (so existing env overrides keep ruling the legacy path).
  broll        "all" = per-scene stock clips as today; "off" = no stock
               b-roll at all (programmatic-graphics formats — also removes
               the unedited-stock originality exposure on those packs).
  outro        True = branded outro card appended (legacy behavior).
  loop_ending  True = no outro, end on the payoff, final frames rhyme with
               frame 0, follow-ask rendered as the FollowChip overlay.
  hook         hook contract for the gate/prompts: "statement" (legacy),
               "question" (quiz), "number-or-payoff".
  brief        extra grounded data the pack needs from the topic engine:
               None, "quiz" ({question/options/answer}), "series" (ranked
               numeric series). Brief planning lands with each pack.
  scenes       (lo, hi) scene-count guidance for prompts/revision notes.
"""

LEGACY_PACK = "legacy-news"

FORMAT_PACKS = {
    # The pre-pack pipeline, unchanged: narrated news arc, stock b-roll on
    # every scene, branded outro card, band from the module-level env knobs.
    "legacy-news": {
        "band": None,
        "broll": "all",
        "outro": True,
        "loop_ending": False,
        "hook": "statement",
        "brief": None,
        "scenes": (4, 8),
    },
    # Today's concrete-news arc, retention-tuned: shorter, no outro coda,
    # loop-friendly ending. Closest pack to current content — ships first.
    #
    # Band retuned 30-45 -> 20-30 (2026-08-09) as the SHORT arm of the runtime
    # experiment. Measured on 52 posts: 42-63s videos were retaining 1.5-3.0s,
    # a ~5% completion rate, and Reels ranks on watch-through. Because this
    # pack has outro=False, total runtime EQUALS the spoken band exactly —
    # there is no 4s outro to reason about, which is why the experiment's
    # short arm is this pack and not a retuned legacy-news (whose retry notes
    # hardcode "40-55 seconds"; see runtime_revision_notes below).
    # 20-30s at the 3.0s/scene floor implies 4-5 scenes at 11-14 spoken words.
    "facts-explainer": {
        "band": (20.0, 30.0),
        "broll": "all",
        "outro": False,
        "loop_ending": True,
        "hook": "number-or-payoff",
        "brief": None,
        "scenes": (4, 5),
    },
    # Animated data ranking with the leader withheld until the last beat.
    "data-rankings": {
        "band": (25.0, 40.0),
        "broll": "off",
        "outro": False,
        "loop_ending": True,
        "hook": "number-or-payoff",
        "brief": "series",
        "scenes": (4, 5),
    },
    # Guess-the-reveal quiz: question -> options -> countdown -> reveal.
    "quiz-reveal": {
        "band": (15.0, 25.0),
        "broll": "off",
        "outro": False,
        "loop_ending": True,
        "hook": "question",
        "brief": "quiz",
        "scenes": (4, 5),
    },
}


def resolve_pack(name):
    """Map a pack name (or None/unknown) to a copy of its config dict.

    Unknown or blank names resolve to the legacy pack rather than raising: a
    stale FORMAT_PACK env value must degrade to today's behavior, never kill
    a posting slot. The returned dict carries its resolved "name".
    """
    key = name.strip().lower() if isinstance(name, str) else ""
    cfg = FORMAT_PACKS.get(key)
    if cfg is None:
        key, cfg = LEGACY_PACK, FORMAT_PACKS[LEGACY_PACK]
    out = dict(cfg)
    out["name"] = key
    return out


# The legacy runtime-revision strings, verbatim from the pre-pack retry loop.
# They are BYTE-PINNED by test_format_packs.py: the legacy path's corrective
# re-asks must never drift, or small-model behavior silently changes.
_LEGACY_EXPAND_NOTE = (
    "when spoken — the video MUST run longer. Write 6-8 scenes and give EVERY scene a \"voiceover\" of "
    "20-35 words (two full sentences is ideal) so the summed narration lasts 40-55 seconds. Do NOT pad "
    "with repetition or filler — every added sentence must contribute a new concrete fact or detail."
)
_LEGACY_TIGHTEN_NOTE = (
    "spoken — too long for a Reel. Cut the weakest scenes and tighten every \"voiceover\" so the "
    "summed narration lasts 40-55 seconds, keeping only the strongest concrete facts."
)


def build_pack_prompt(pack_name, title, brief, seed=None):
    """User prompt for a data-brief pack (quiz-reveal / data-rankings).

    The SCENE OUTLINE is the structure contract; main.apply_pack_postprocess
    later injects/enforces the verified brief data regardless of how
    faithfully the model followed it — so this prompt optimizes for natural
    copy, labels and search queries, while correctness is guaranteed
    downstream. Small-model friendly: short, imperative, field-exact.
    """
    if pack_name == "quiz-reveal":
        opts = brief["options"]
        return f"""Create a guess-the-answer QUIZ reel about this tech story: {title}

THE QUIZ (verified data — use EXACTLY these, verbatim):
- QUESTION: {brief['question']}
- OPTIONS: {" / ".join(opts)}
- CORRECT ANSWER: {opts[brief['answer_index']]}
- PROOF: {brief['answer_fact']}

SCENE OUTLINE (follow exactly — 4 scenes):
- Scene 1 (HOOK): type "hero". On-screen "text" = the QUESTION verbatim. "voiceover" speaks the question plus one short stakes line, max 16 words total. The answer must NOT appear.
- Scene 2 (OPTIONS): type "list". "listItems" = the OPTIONS verbatim, one per item. "voiceover" reads the options and challenges the viewer to pick one, max 18 words. "title" = a 2-3 word label like "YOUR OPTIONS" — never the question again.
- Scene 3 (COUNTDOWN): type "countdown", countFrom 3, countTo 1, durationInFrames 90, "voiceover" = "" (empty string — music only).
- Scene 4 (REVEAL): type "metric". "text" = the CORRECT ANSWER verbatim. "secondaryText" = the PROOF sentence. "voiceover" = the PROOF sentence (numbers spelled out). "title" = a 2-3 word label like "THE ANSWER".

RULES:
- The CORRECT ANSWER must never appear in scenes 1-3 "text" or "voiceover" (scene 2's options list is the only place it may be listed, unmarked).
- No follow/subscribe ask anywhere; the video ends the instant the proof lands.
- Every scene gets a "searchQuery" (concrete tech visual) and a "videoQuery"."""
    if pack_name == "data-rankings":
        series = brief["series"]
        unit = brief.get("unit") or ""
        listing = "; ".join(f"{p['label']} = {p['value']}{unit}" for p in series)
        return f"""Create a RANKED-DATA reel about this tech story: {title}

THE DATA (verified — use EXACTLY these values, never invent or round):
- METRIC: {brief.get('metric_label') or 'the metric'}{f' ({unit})' if unit else ''}
- SERIES: {listing}
- WHY IT MATTERS: {brief.get('insight') or ''}

SCENE OUTLINE (follow exactly — 4 scenes):
- Scene 1 (HOOK): type "hero". Tease the ranking WITHOUT naming the leader (the "#1 is not who you think" energy). Max 8 on-screen words; "voiceover" max 14 words.
- Scene 2 (SETUP): type "split". One line on WHAT was measured and HOW, from the story. No numbers yet.
- Scene 3 (CHART): type "bar-chart". "chartData" = the SERIES verbatim as {{"label","value"}} pairs. "voiceover" walks the ranking WITHOUT the leader's name.
- Scene 4 (REVEAL): type "metric". "text" = the leader's label. "voiceover" names the leader + its exact value, then lands WHY IT MATTERS in one sentence.

RULES:
- The leader's name must never appear in scenes 1-3 "voiceover" or "text".
- Values verbatim from the SERIES — never rounded, never estimated.
- No follow/subscribe ask anywhere; the video ends the instant the payoff lands.
- Every scene gets a "searchQuery" (concrete tech visual) and a "videoQuery"."""
    raise ValueError(f"no pack prompt builder for {pack_name!r}")


def runtime_revision_notes(pack_cfg, min_sec, max_sec):
    """(expand_note, tighten_note) tails for the script retry loop.

    The loop prefixes each with its measured-runtime sentence fragment; these
    tails carry the guidance. Legacy pack returns the historical strings
    byte-for-byte; other packs get band-derived guidance so the retry loop
    can no longer "correct" a 20s quiz back to a 45s news video.
    """
    if pack_cfg.get("name", LEGACY_PACK) == LEGACY_PACK:
        return _LEGACY_EXPAND_NOTE, _LEGACY_TIGHTEN_NOTE
    lo, hi = int(round(min_sec)), int(round(max_sec))
    sc_lo, sc_hi = pack_cfg.get("scenes", (4, 6))
    expand = (
        f"when spoken — too short for this format. Keep {sc_lo}-{sc_hi} scenes and expand the "
        f"voiceovers with new concrete facts so the summed narration lasts {lo}-{hi} seconds. "
        f"Do NOT pad with repetition or filler, and do NOT change the scene structure."
    )
    tighten = (
        f"spoken — too long for this format. Tighten every \"voiceover\" so the summed narration "
        f"lasts {lo}-{hi} seconds, keeping only the strongest concrete facts and the same scene structure."
    )
    return expand, tighten

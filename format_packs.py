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
    "facts-explainer": {
        "band": (30.0, 45.0),
        "broll": "all",
        "outro": False,
        "loop_ending": True,
        "hook": "number-or-payoff",
        "brief": None,
        "scenes": (4, 6),
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

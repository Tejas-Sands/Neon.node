"""Sanity-measure the edge-tts speech rate behind _SPOKEN_RATE_BY_ENGINE (main.py).

The constant (words-per-second, per-scene lead-in) feeds _estimate_spoken_seconds,
which gates script length BEFORE TTS runs. Its docstring requires re-measurement
whenever VOICE_POOL or VOICEOVER_RATE changes. Run locally (needs network —
edge-tts hits the free Microsoft endpoint):

    python scripts/measure_spoken_rate.py

Method: synthesize real multi-scene scripts scene-by-scene — never one long
block, because per-utterance overhead dominates short scenes — and take each
scene's spoken length from its LAST WordBoundary end time, exactly the signal
main.py uses to set scene durations. Ground-truthed 2026-08-09: the mp3 runs
~0.36s past the last WordBoundary (trailing silence), which is what the
pipeline's SCENE_TAIL_PAD_SEC = 0.35 models — so the lead-in term is PINNED
there and only the words-per-second rate is measured:

    wps_effective = total_words / sum(last_word_end per scene)

Do NOT least-squares both terms from one corpus: scene word counts cluster
tightly, the slope/intercept fit is ill-conditioned, and it happily returns a
nonsense 4+ wps slope (observed 2026-08-09).

CAVEAT — corpus matters more than voice. The canonical constant was fit on
production props files (~10-word scenes, see the _estimate_spoken_seconds
docstring); this script's few-shot corpus runs longer, dashed scenes and reads
0.5-1.0 wps faster on token-based counting. Treat this script as a drift
DETECTOR (rerun it after a rate/pool change and compare against the baseline
table below, not against the constant); only update _SPOKEN_RATE_BY_ENGINE
from production props files, per its docstring.

Baseline @ rate=+5% pitch=+2Hz (2026-08-09, this corpus):
    Ava 3.06 wps | Emma 3.28 | Andrew 3.03 | Brian 3.25 | pool-weighted 3.16
"""
import asyncio
import os
import sys

import edge_tts

RATE = os.environ.get("VOICEOVER_RATE", "+5%")
PITCH = os.environ.get("VOICEOVER_PITCH", "+2Hz")
LEADIN = 0.35  # pinned to SCENE_TAIL_PAD_SEC — measured, not fit (see above)

# CHEERFUL_VOICE_POOL rotation weights (see main.py).
VOICES = {
    "en-US-AvaMultilingualNeural": 2,
    "en-US-EmmaMultilingualNeural": 2,
    "en-US-AndrewMultilingualNeural": 1,
    "en-US-BrianMultilingualNeural": 1,
}

# The two SYSTEM_PROMPT few-shot scripts' voiceovers (post spoken-warmth pass,
# 2026-08-09) — real scene-length distribution, not synthetic sentences.
SCRIPTS = {
    "hyperapi": [
        "Your API gateway is the slowest hop in your whole stack — HyperAPI just fixed that.",
        "Old gateways burn two hundred milliseconds a request — this one answers in twenty. So how far does that scale?",
        "All the way to fifty thousand requests a second — and it doesn't even break a sweat.",
        "None of it needs configuring — scaling, global caching, certificates and traffic dashboards all switch on the moment you deploy.",
        "That's not a marketing number — the published benchmark ran a million real requests and held a twenty-millisecond median.",
        "Drop it in front of your API today — the free tier needs no credit card, just a deploy.",
    ],
    "salt-battery": [
        "A battery built on table-salt chemistry just survived three thousand charges nearly untouched.",
        "It swaps lithium ions for sodium ones — heavier, but the team's new electrode stops them from cracking the structure as they cycle.",
        "Three thousand full charges — roughly eight years of daily use — and it kept ninety-two percent of its capacity.",
        "Sodium is dirt cheap and everywhere — that cuts the projected pack cost by about a third.",
        "That retention figure comes straight from the peer-reviewed results, not a press release.",
        "Cheap cells that refuse to die are exactly what solar farms need at night — that's the market it lands in first.",
    ],
}


async def scene_seconds(text: str, voice: str) -> float:
    """Spoken length of one scene = end of its last WordBoundary event."""
    communicate = edge_tts.Communicate(text, voice, rate=RATE, pitch=PITCH, boundary="WordBoundary")
    last_end = 0.0
    async for chunk in communicate.stream():
        if chunk["type"] == "WordBoundary":
            # offset/duration are in 100ns ticks.
            last_end = max(last_end, (chunk["offset"] + chunk["duration"]) / 1e7)
    if last_end <= 0.0:
        raise RuntimeError(f"{voice} emitted no WordBoundary events — unusable for subtitles/calibration")
    return last_end


async def main() -> int:
    print(f"rate={RATE} pitch={PITCH} leadin(pinned)={LEADIN}")
    weighted_wps = weight_total = 0.0
    for voice, weight in VOICES.items():
        total_words = 0
        total_sec = 0.0
        scene_n = 0
        for scenes in SCRIPTS.values():
            for text in scenes:
                total_sec += await scene_seconds(text, voice)
                # .split() to match _estimate_spoken_seconds' token counting.
                total_words += len(text.split())
                scene_n += 1
        wps = total_words / total_sec
        print(f"{voice}  wps={wps:.3f}  ({total_words} words, {total_sec:.1f}s over {scene_n} scenes)")
        weighted_wps += wps * weight
        weight_total += weight
    wps = weighted_wps / weight_total
    print(f"\nPool-weighted (Ava x2, Emma x2, Andrew, Brian): wps={wps:.3f}")
    print("Baseline for THIS corpus @ +5%/+2Hz (2026-08-09): 3.16")
    drift = abs(wps - 3.16) / 3.16
    print(f"drift vs corpus baseline: {drift * 100:.1f}%  "
          f"({'speech rate MOVED — recalibrate _SPOKEN_RATE_BY_ENGINE from production props files' if drift > 0.03 else 'within 3% — constant stays'})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

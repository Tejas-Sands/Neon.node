#!/usr/bin/env python3
"""Kokoro-82M TTS worker — runs under a SIDE Python >=3.10 interpreter.

The pipeline interpreter stays on Python 3.9 (the frozen Instagram posting
path was debugged around 3.9 OpenSSL behavior and must not move); kokoro
requires >=3.10, so main.py shells out to THIS script via the interpreter
named by KOKORO_PYTHON (tts_providers.py builds the command).

Protocol (batch, one process per VIDEO so the model loads once):
  stdin:  {"voice": "af_heart", "speed": 1.05,
           "scenes": [{"idx": 0, "text": "...", "out_path": "/abs/x.wav"}, ...]}
  stdout: LAST line is the JSON result (HF/torch may print noise above it):
          {"results": {"0": {"words": [{"text","start","end"}...],
                             "seconds": 12.3}
                       "1": {"error": "..."}}}

Timestamps are SECONDS, scene-local, monotonically non-decreasing.
kokoro emits punctuation as separate tokens and can leave start_ts/end_ts
None — merge_tokens_to_words() glues tokens into whitespace-delimited words
and fill_missing_times() interpolates the gaps, so the karaoke subtitle
layer never sees a floating "?" pill or a None. Both helpers are pure and
dependency-free ON PURPOSE: test_tts_providers.py imports this file under
the 3.9 pipeline interpreter to pin them (kokoro imports live inside main()).
"""

import json
import sys


def merge_tokens_to_words(tokens):
    """[{text, whitespace, start, end}] -> whitespace-delimited word dicts.

    A token with no trailing whitespace glues to the NEXT token ("cloud" +
    "," -> "cloud,"). start comes from the first constituent carrying one,
    end from the last constituent carrying one; missing values stay None for
    fill_missing_times(). Tokens with empty text are dropped.
    """
    words = []
    open_word = None
    for tok in tokens:
        text = (tok.get("text") or "").strip()
        if not text:
            continue
        ts, te = tok.get("start"), tok.get("end")
        if open_word is None:
            open_word = {"text": text, "start": ts, "end": te}
        else:
            open_word["text"] += text
            if te is not None:
                open_word["end"] = te
            if open_word["start"] is None:
                open_word["start"] = ts
        if tok.get("whitespace"):
            words.append(open_word)
            open_word = None
    if open_word is not None:
        words.append(open_word)
    return words


def fill_missing_times(words, chunk_seconds):
    """Interpolate None start/end times so every word is timed and monotonic.

    Forward pass: a missing start inherits the previous word's end (0.0 at
    the head); a missing end takes the next word's start, else start + a
    nominal 0.30s, capped at the chunk length. Ends are clamped monotonic so
    the karaoke active-word logic (last STARTED word) never flickers back.
    """
    n = len(words)
    for i, w in enumerate(words):
        if w["start"] is None:
            w["start"] = words[i - 1]["end"] if i > 0 and words[i - 1]["end"] is not None else 0.0
        if w["end"] is None:
            nxt = None
            for j in range(i + 1, n):
                if words[j]["start"] is not None:
                    nxt = words[j]["start"]
                    break
            w["end"] = nxt if nxt is not None else min(w["start"] + 0.30, max(chunk_seconds, w["start"]))
        if w["end"] < w["start"]:
            w["end"] = w["start"]
        if i > 0 and w["start"] < words[i - 1]["end"]:
            w["start"] = words[i - 1]["end"]
            if w["end"] < w["start"]:
                w["end"] = w["start"]
    return words


def main():
    req = json.loads(sys.stdin.read())
    voice = req.get("voice") or "af_heart"
    speed = float(req.get("speed") or 1.0)
    scenes = req.get("scenes") or []

    import numpy as np
    import soundfile as sf
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    results = {}
    for scene in scenes:
        idx = scene.get("idx")
        try:
            audio_chunks = []
            words = []
            t_base = 0.0
            for r in pipeline(scene["text"], voice=voice, speed=speed):
                audio = getattr(r, "audio", None)
                if audio is None:
                    continue
                audio_np = audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio)
                chunk_seconds = float(len(audio_np)) / 24000.0
                tok_dicts = [
                    {"text": getattr(t, "text", "") or "",
                     "whitespace": getattr(t, "whitespace", "") or "",
                     "start": getattr(t, "start_ts", None),
                     "end": getattr(t, "end_ts", None)}
                    for t in (getattr(r, "tokens", None) or [])
                ]
                chunk_words = fill_missing_times(merge_tokens_to_words(tok_dicts), chunk_seconds)
                for w in chunk_words:
                    words.append({"text": w["text"],
                                  "start": round(w["start"] + t_base, 4),
                                  "end": round(w["end"] + t_base, 4)})
                t_base += chunk_seconds
                audio_chunks.append(audio_np)
            if not audio_chunks or not words:
                raise Exception("kokoro produced no audio/tokens for this scene")
            sf.write(scene["out_path"], np.concatenate(audio_chunks), 24000)
            results[str(idx)] = {"words": words, "seconds": round(t_base, 3)}
        except Exception as e:  # noqa: BLE001 — per-scene error is data, not a crash
            results[str(idx)] = {"error": str(e)[:400]}

    sys.stdout.write("\n" + json.dumps({"results": results}) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()

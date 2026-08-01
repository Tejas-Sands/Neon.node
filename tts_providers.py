"""TTS provider seam (M2) — Python 3.9-safe, imported by main.py.

Engines:
  edge    — edge-tts (historical default). Synthesis stays inline in
            main.generate_voiceover_and_alignment, byte-for-byte.
  kokoro  — Kokoro-82M via scripts/kokoro_tts_worker.py running under a SIDE
            Python >=3.10 interpreter (KOKORO_PYTHON). Batch: one subprocess
            per VIDEO so the ~330MB model loads once. Native word timestamps
            (seconds) in the exact shape the karaoke layer consumes.

Engine rules (do not weaken):
  * Engines NEVER mix within one video — a kokoro failure triggers a full
    edge-tts restart of the whole video in main.py (mixed narrators read as
    broken; this mirrors the sticky-voice failover lesson).
  * Ledger voice keys are namespaced ("kokoro:af_heart") so the feedback
    voices bucket cold-starts cleanly per engine and never conflates pools.
  * TTS_PROVIDER selects the engine (default "edge" until the CI soak);
    a forced edge-style voice name pins the edge engine regardless.
"""

import json
import os
import re
import shutil
import subprocess

# Bright, energetic narrators first — kokoro delivery is clean-but-calm, so
# the pool leans toward its liveliest voices. Keys are ledgered with the
# "kokoro:" prefix; changing the pool cold-starts those bucket keys (same
# contract as VOICE_POOL — the epsilon floor keeps rotation alive).
KOKORO_VOICE_POOL = ["af_heart", "af_bella", "am_michael", "am_fenrir"]

# Kokoro voice ids look like af_heart / am_michael / bf_emma — two lowercase
# letters (accent + gender) then underscore.
_KOKORO_VOICE_RE = re.compile(r"^[a-z]{2}_[a-z0-9]+$")


def kokoro_python():
    """Absolute path of the side interpreter, or "" when unavailable."""
    py = (os.environ.get("KOKORO_PYTHON") or "").strip()
    if not py:
        return ""
    if os.path.sep in py:
        return py if os.path.exists(py) else ""
    return shutil.which(py) or ""


def is_kokoro_voice(name):
    return bool(name) and bool(_KOKORO_VOICE_RE.match(name.strip()))


def resolve_tts_engine(forced_voice=None):
    """Which engine this video uses. Defaults to edge; kokoro only when
    TTS_PROVIDER=kokoro AND the side interpreter exists AND no edge-style
    voice was forced (a forced edge voice pins the edge engine)."""
    provider = (os.environ.get("TTS_PROVIDER") or "edge").strip().lower()
    if provider != "kokoro":
        return "edge"
    forced = (forced_voice or os.environ.get("VOICEOVER_VOICE", "")).strip()
    if forced and not is_kokoro_voice(forced):
        return "edge"
    if not kokoro_python():
        print("[TTS] TTS_PROVIDER=kokoro but KOKORO_PYTHON is unset/missing — using edge-tts.")
        return "edge"
    return "kokoro"


def edge_rate_to_speed(rate_str, default=1.0):
    """Edge-TTS rate string ("+5%", "-10%") -> kokoro float speed."""
    m = re.match(r"^\s*([+-]?\d+(?:\.\d+)?)\s*%\s*$", str(rate_str or ""))
    if not m:
        return default
    return max(0.5, min(2.0, 1.0 + float(m.group(1)) / 100.0))


def synthesize_scenes_kokoro(batch, voice, speed, session_id=""):
    """Synthesize every spoken scene in ONE worker subprocess.

    batch: [{"idx": int, "text": str, "out_path": abs path}] — the worker
    writes 24kHz WAVs and returns per-scene word timings. Returns
    {idx: {"words": [...], "seconds": s}} with per-scene {"error": ...}
    entries preserved (the caller turns those into failed scenes -> full
    edge restart). Raises on systemic failure (bad interpreter, crash,
    unparseable output, timeout) — same restart path.
    """
    py = kokoro_python()
    if not py:
        raise Exception("KOKORO_PYTHON not set/found — kokoro engine unavailable")
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "scripts", "kokoro_tts_worker.py")
    payload = json.dumps({"voice": voice, "speed": speed, "scenes": batch})
    # Budget: model load (~10-20s cold on CI CPU) + RTF ~0.16 synthesis.
    timeout = int(os.environ.get("KOKORO_TIMEOUT_SEC", "300"))
    try:
        proc = subprocess.run([py, worker], input=payload, capture_output=True,
                              text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Exception(f"kokoro worker timed out after {timeout}s")
    if proc.returncode != 0:
        raise Exception(f"kokoro worker failed (rc={proc.returncode}): "
                        f"{(proc.stderr or '')[-400:]}")
    # HF/torch may print noise on stdout — the result is the LAST JSON line.
    result_line = ""
    for line in (proc.stdout or "").strip().splitlines()[::-1]:
        if line.strip().startswith("{"):
            result_line = line.strip()
            break
    if not result_line:
        raise Exception(f"kokoro worker produced no JSON result: {(proc.stdout or '')[-200:]}")
    results = json.loads(result_line).get("results") or {}
    out = {}
    for item in batch:
        res = results.get(str(item["idx"])) or {"error": "scene missing from worker output"}
        if "words" in res:
            path = item["out_path"]
            if not os.path.exists(path) or os.path.getsize(path) < 1024:
                res = {"error": "worker reported words but wrote empty/near-empty audio"}
        out[item["idx"]] = res
    return out

#!/usr/bin/env python3
"""
TTS Provider Seam — Regression Tests (M2)
=========================================
Pins the engine-routing contract:

  * TTS_PROVIDER unset/edge -> edge engine, byte-for-bit legacy path.
  * kokoro only when the side interpreter exists; a forced edge-style voice
    pins edge; kokoro voice ids recognized by shape (af_heart, am_michael).
  * edge rate strings ("+5%") map to kokoro float speeds, clamped.
  * The worker's pure helpers: punctuation tokens glue onto the preceding
    word (no floating "?" caption pills) and None timestamps interpolate to
    a monotonic, fully-timed word list (a None max_word_end would silently
    freeze scene durations — the R7 failure mode).
  * synthesize_scenes_kokoro subprocess plumbing: noise-tolerant JSON
    parse, empty-audio rejection, systemic-failure raise.
  * The wrapper NEVER mixes engines: a kokoro failure restarts the whole
    video on edge and restores the planned durations first.

Usage: python test_tts_providers.py [-v]
"""

import asyncio
import importlib.util
import json
import os
import stat
import sys
import tempfile

import tts_providers as tp

VERBOSE = "-v" in sys.argv
FAILURES = []


def check(name, cond, detail=""):
    if cond:
        if VERBOSE:
            print(f"  PASS  {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


class env:
    """Temporarily set/unset environment variables."""
    def __init__(self, **kw):
        self.kw = kw
        self.old = {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.old[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def __exit__(self, *a):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# --- 1. Engine resolution --------------------------------------------------------
print("[resolve_tts_engine]")
with env(TTS_PROVIDER=None, VOICEOVER_VOICE=None, KOKORO_PYTHON=None):
    check("default is edge", tp.resolve_tts_engine() == "edge")
with env(TTS_PROVIDER="kokoro", VOICEOVER_VOICE=None, KOKORO_PYTHON=None):
    check("kokoro without interpreter degrades to edge", tp.resolve_tts_engine() == "edge")
with env(TTS_PROVIDER="kokoro", VOICEOVER_VOICE=None, KOKORO_PYTHON=sys.executable):
    check("kokoro with interpreter resolves kokoro", tp.resolve_tts_engine() == "kokoro")
with env(TTS_PROVIDER="kokoro", VOICEOVER_VOICE="en-US-AndrewMultilingualNeural",
         KOKORO_PYTHON=sys.executable):
    check("forced edge voice pins edge", tp.resolve_tts_engine() == "edge")
with env(TTS_PROVIDER="kokoro", VOICEOVER_VOICE="af_heart", KOKORO_PYTHON=sys.executable):
    check("forced kokoro voice keeps kokoro", tp.resolve_tts_engine() == "kokoro")
check("kokoro voice id shapes", tp.is_kokoro_voice("af_heart") and tp.is_kokoro_voice("bm_george")
      and not tp.is_kokoro_voice("en-US-AvaNeural") and not tp.is_kokoro_voice(""))

# --- 2. Rate mapping -------------------------------------------------------------
print("[edge_rate_to_speed]")
check("+5% -> 1.05", abs(tp.edge_rate_to_speed("+5%") - 1.05) < 1e-9)
check("-10% -> 0.90", abs(tp.edge_rate_to_speed("-10%") - 0.90) < 1e-9)
check("junk -> default", tp.edge_rate_to_speed("fast") == 1.0)
check("clamped", tp.edge_rate_to_speed("+500%") == 2.0 and tp.edge_rate_to_speed("-90%") == 0.5)

# --- 3. Worker pure helpers ------------------------------------------------------
print("[worker helpers]")
_worker_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "scripts", "kokoro_tts_worker.py")
spec = importlib.util.spec_from_file_location("kokoro_tts_worker", _worker_path)
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)

# "Can you guess?" -> tokens: Can| |you| |guess|?| . The "?" has no preceding
# whitespace so it glues onto "guess".
toks = [
    {"text": "Can", "whitespace": " ", "start": 0.0, "end": 0.2},
    {"text": "you", "whitespace": " ", "start": 0.2, "end": 0.35},
    {"text": "guess", "whitespace": "", "start": 0.35, "end": 0.7},
    {"text": "?", "whitespace": " ", "start": None, "end": None},
]
words = worker.merge_tokens_to_words(toks)
check("punctuation glues to the word", [w["text"] for w in words] == ["Can", "you", "guess?"],
      f"got {[w['text'] for w in words]}")
check("glued word keeps the word's timing", words[2]["start"] == 0.35 and words[2]["end"] == 0.7)

toks_none = [
    {"text": "three", "whitespace": " ", "start": 0.0, "end": 0.3},
    {"text": "two", "whitespace": " ", "start": None, "end": None},
    {"text": "one", "whitespace": "", "start": 0.8, "end": 1.1},
]
filled = worker.fill_missing_times(worker.merge_tokens_to_words(toks_none), 1.2)
check("None start inherits previous end", filled[1]["start"] == 0.3)
check("None end takes next start", filled[1]["end"] == 0.8)
check("all words timed and monotonic",
      all(w["start"] is not None and w["end"] is not None for w in filled)
      and all(filled[i]["start"] >= filled[i - 1]["end"] for i in range(1, len(filled))))
check("max end > 0 (scene-duration refit stays alive)",
      max(w["end"] for w in filled) > 0)

trailing = worker.merge_tokens_to_words([{"text": "end", "whitespace": "", "start": 0.1, "end": 0.4}])
check("trailing unclosed word is flushed", len(trailing) == 1 and trailing[0]["text"] == "end")

# --- 4. Subprocess plumbing via a stub interpreter -------------------------------
print("[synthesize_scenes_kokoro]")
tmp = tempfile.mkdtemp(prefix="tts-test-")


def make_stub(body):
    path = os.path.join(tmp, f"stub-{len(os.listdir(tmp))}.py")
    with open(path, "w") as f:
        f.write("#!" + sys.executable + "\n" + body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


ok_stub = make_stub("""
import json, sys
req = json.loads(sys.stdin.read())
sys.stdout.write("some torch noise on stdout\\n")
results = {}
for s in req["scenes"]:
    with open(s["out_path"], "wb") as f:
        f.write(b"RIFF" + b"0" * 2048)
    results[str(s["idx"])] = {"words": [{"text": "hi", "start": 0.0, "end": 0.4}], "seconds": 0.5}
sys.stdout.write(json.dumps({"results": results}) + "\\n")
""")
wav_a = os.path.join(tmp, "a.wav")
with env(KOKORO_PYTHON=ok_stub):
    out = tp.synthesize_scenes_kokoro([{"idx": 0, "text": "hi", "out_path": wav_a}],
                                      "af_heart", 1.05)
check("happy path returns words despite stdout noise",
      out.get(0, {}).get("words") and out[0]["words"][0]["text"] == "hi", f"got {out}")

empty_stub = make_stub("""
import json, sys
req = json.loads(sys.stdin.read())
results = {}
for s in req["scenes"]:
    open(s["out_path"], "wb").write(b"x")  # near-empty audio
    results[str(s["idx"])] = {"words": [{"text": "hi", "start": 0, "end": 0.4}], "seconds": 0.5}
sys.stdout.write(json.dumps({"results": results}) + "\\n")
""")
wav_b = os.path.join(tmp, "b.wav")
with env(KOKORO_PYTHON=empty_stub):
    out = tp.synthesize_scenes_kokoro([{"idx": 0, "text": "hi", "out_path": wav_b}],
                                      "af_heart", 1.0)
check("near-empty audio becomes a per-scene error", "error" in out.get(0, {}), f"got {out}")

crash_stub = make_stub("import sys; sys.exit(3)\n")
with env(KOKORO_PYTHON=crash_stub):
    try:
        tp.synthesize_scenes_kokoro([{"idx": 0, "text": "hi", "out_path": wav_b}], "af_heart", 1.0)
        check("worker crash raises (systemic)", False)
    except Exception:
        check("worker crash raises (systemic)", True)

with env(KOKORO_PYTHON=None):
    try:
        tp.synthesize_scenes_kokoro([{"idx": 0, "text": "hi", "out_path": wav_b}], "af_heart", 1.0)
        check("missing interpreter raises", False)
    except Exception:
        check("missing interpreter raises", True)

# --- 5. Never-mix-engines wrapper ------------------------------------------------
print("[full-restart wrapper]")
import main  # noqa: E402  (heavy import kept below the cheap checks)

calls = []


async def fake_engine(engine, scenes, session_id, public_dir, voice=None, rate=None, pitch=None):
    calls.append(engine)
    if engine == "kokoro":
        for s in scenes:
            s["durationInFrames"] = 999  # simulate a partial refit before dying
        raise Exception("boom")
    return "voiceover-x.mp3", [{"text": "w", "start": 0.0, "end": 0.4}]


_real = main._generate_voiceover_with_engine
main._generate_voiceover_with_engine = fake_engine
try:
    scenes = [{"voiceover": "hello world", "durationInFrames": 150}]
    with env(TTS_PROVIDER="kokoro", VOICEOVER_VOICE=None, KOKORO_PYTHON=sys.executable):
        fname, subs = asyncio.run(main.generate_voiceover_and_alignment(
            scenes, "test-sess", tmp))
    check("kokoro failure restarts on edge", calls == ["kokoro", "edge"], f"calls={calls}")
    check("planned durations restored before the edge pass",
          scenes[0]["durationInFrames"] == 150, f"got {scenes[0]['durationInFrames']}")
    check("edge pass result is returned", fname == "voiceover-x.mp3" and subs)
    calls.clear()
    with env(TTS_PROVIDER=None, VOICEOVER_VOICE=None, KOKORO_PYTHON=None):
        asyncio.run(main.generate_voiceover_and_alignment(scenes, "test-sess", tmp))
    check("default goes straight to edge", calls == ["edge"], f"calls={calls}")
finally:
    main._generate_voiceover_with_engine = _real

print()
if FAILURES:
    print(f"FAILED: {len(FAILURES)} check(s): " + "; ".join(FAILURES[:8]))
    sys.exit(1)
print("test_tts_providers.py: ALL PASS")

"""Generate the transition SFX used by the Remotion composition (public/sfx/).

Synthesized procedurally with the Python stdlib — no licensing, no downloads,
fully reproducible. Run once (files are committed to the repo):

    python scripts/generate_sfx.py

Why SFX at all: audio pattern-interrupts (a whoosh on every cut, an impact on
the hook) measurably lift short-form watch time — viewers' attention resets on
each audio event. Volumes are kept low in the composition so they sit under
the voiceover.
"""
import math
import os
import random
import struct
import wave

SR = 44100
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public", "sfx")


def _write_wav(path: str, samples: list) -> None:
    peak = max(1e-9, max(abs(s) for s in samples))
    norm = 0.92 / peak
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(b"".join(
            struct.pack("<h", int(max(-1.0, min(1.0, s * norm)) * 32767)) for s in samples
        ))
    print(f"wrote {path} ({len(samples)/SR:.2f}s)")


def make_whoosh(duration=0.55, seed=7) -> list:
    """Filtered noise with a rising-then-falling lowpass sweep = air whoosh."""
    rnd = random.Random(seed)
    n = int(SR * duration)
    out, lp = [], 0.0
    for i in range(n):
        t = i / n
        # Amplitude envelope: fast attack, smooth decay
        env = math.sin(min(1.0, t * 3.2) * math.pi / 2) * (1.0 - t) ** 1.6
        # Lowpass coefficient sweeps up then down (brightness follows motion)
        sweep = math.sin(t * math.pi)
        alpha = 0.02 + 0.32 * sweep
        lp += alpha * (rnd.uniform(-1, 1) - lp)
        out.append(lp * env)
    return out


def make_impact(duration=0.6, seed=3) -> list:
    """Sub-bass thump (58→34 Hz sweep) + 12ms noise click = hook impact."""
    rnd = random.Random(seed)
    n = int(SR * duration)
    out, phase = [], 0.0
    for i in range(n):
        t = i / SR
        prog = i / n
        freq = 58.0 * math.exp(-prog * 1.6) + 34.0
        phase += 2 * math.pi * freq / SR
        body = math.sin(phase) * math.exp(-prog * 7.0)
        # Soft-clip for weight
        body = math.tanh(body * 2.2) * 0.8
        click = rnd.uniform(-1, 1) * math.exp(-t * 400.0) * 0.5
        out.append(body + click)
    return out


def make_pop(duration=0.16, seed=11) -> list:
    """Short bright blip — for text/metric reveals."""
    n = int(SR * duration)
    out, phase = [], 0.0
    for i in range(n):
        prog = i / n
        freq = 720.0 - 300.0 * prog
        phase += 2 * math.pi * freq / SR
        env = math.exp(-prog * 9.0)
        out.append(math.sin(phase) * env)
    return out


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    _write_wav(os.path.join(OUT_DIR, "whoosh.wav"), make_whoosh())
    _write_wav(os.path.join(OUT_DIR, "impact.wav"), make_impact())
    _write_wav(os.path.join(OUT_DIR, "pop.wav"), make_pop())

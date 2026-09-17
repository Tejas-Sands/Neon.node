"""Scene speech timing. Native TTS timestamps remain the source of truth.

Only exterior silence is removed. No time stretching, interior pause removal,
network calls, or renderer-specific animation state belongs here.
"""
from array import array
import math
from pathlib import Path
import subprocess
import sys
import wave


def fit_frames(audio_end_sec, read_floor_frames, fps=30):
    return max(math.ceil(audio_end_sec * fps), read_floor_frames)


def reading_frames(scene, fps=30):
    # Sequential legacy layouts have their own timed reveals. Keep their
    # planned floor until they have an explicit reading-time model.
    if scene.get('type', 'split') not in ('hero', 'split', 'metric', 'comparison', 'cta', 'outro'):
        return max(90, scene.get('durationInFrames', 150))
    reads = [str(scene.get(key) or '') for key in
             ('title', 'text', 'subtitle', 'secondaryText', 'leftLabel', 'rightLabel')]
    longest = max((len(text.split()) for text in reads), default=0)
    entrance = 0 if scene.get('type') == 'hero' else 22 / fps
    return max(60, math.ceil((entrance + max(1.2, .3 * longest)) * fps))


def prepare_audio(path, words):
    """Return (local PCM path, shifted words, measured timing).

    -55dB peak threshold is deliberately conservative: quiet endings count as
    speech. Native word bounds AND detected sound constrain the trim, and a
    60ms head / 180ms tail protects their edges. Uncertain noise keeps more audio.
    The input is retained; its caller owns cleanup of both files.
    """
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 's16le',
                          '-ac', '1', '-ar', '24000', 'pipe:1'],
                         capture_output=True, check=True, timeout=30).stdout
    samples = array('h'); samples.frombytes(pcm)
    if sys.byteorder != 'little': samples.byteswap()
    seconds = len(samples) / 24000
    if not words or not samples:
        raise ValueError('Missing speech or word boundaries')
    if any(not math.isfinite(w[k]) or w[k] < 0 for w in words for k in ('start', 'end')) or any(
            w['end'] < w['start'] or w['end'] > seconds + .05 for w in words):
        raise ValueError('Word boundaries outside decoded audio')
    threshold = 32768 * 10 ** (-55 / 20)
    first = next((i for i, value in enumerate(samples) if abs(value) > threshold), None)
    if first is None:
        raise ValueError('Synthesized audio contains no detectable speech')
    last = len(samples) - next(i for i, value in enumerate(reversed(samples)) if abs(value) > threshold)
    begin = max(0, math.floor((min(first / 24000, min(w['start'] for w in words)) - .06) * 24000))
    end = min(len(samples), math.ceil((max(last / 24000, max(w['end'] for w in words)) + .18) * 24000))
    output = str(Path(path).with_suffix('.paced.wav'))
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes(pcm[begin * 2:end * 2])
    shift = begin / 24000
    aligned = [dict(w, start=max(0, w['start'] - shift), end=w['end'] - shift) for w in words]
    return output, aligned, {'original_seconds': seconds, 'seconds': (end - begin) / 24000,
                             'trim_start': shift, 'trim_end': end / 24000}

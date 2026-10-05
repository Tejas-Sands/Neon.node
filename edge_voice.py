"""Key-free Edge narration with full context and native word boundaries.

Retry entire performances, never splice different narrators. Decode once and
split only in measured silence between scene words; no time stretching.
"""
from array import array
import os
from pathlib import Path
import subprocess
import sys
import wave

from expressive_voice import align_script, _canonical


def split_scenes(batch, path, words):
    pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 's16le',
                          '-ac', '1', '-ar', '24000', 'pipe:1'],
                         capture_output=True, check=True, timeout=30).stdout
    samples = array('h'); samples.frombytes(pcm)
    if sys.byteorder != 'little':
        samples.byteswap()
    seconds = len(samples) / 24000
    # Validate exact text and real intervals before assigning any scene.
    aligned = align_script(' '.join(item['text'] for item in batch), words, seconds)
    groups, cursor = [], 0
    for item in batch:
        target = sum(bool(_canonical(t)) for t in item['text'].split())
        group, count = [], 0
        while count < target and cursor < len(aligned):
            word = aligned[cursor]
            group.append(word)
            count += len(word['text'].split())
            cursor += 1
        if not group or count != target:
            raise ValueError('Edge word alignment crosses a scene boundary')
        groups.append(group)
    if cursor != len(aligned):
        raise ValueError('Edge narration has unassigned words')
    cuts = [0]
    threshold = 32768 * 10 ** (-55 / 20)
    for before, after in zip(groups, groups[1:]):
        lo = int(before[-1]['end'] * 24000 + .999999)
        hi = int(after[0]['start'] * 24000)
        # Native word ends can precede audible consonant decay. Require a
        # real quiet window, not just the midpoint of two metadata events.
        runs, start = [], None
        for i in range(lo, hi):
            if abs(samples[i]) <= threshold:
                if start is None:
                    start = i
            elif start is not None:
                runs.append((start, i)); start = None
        if start is not None:
            runs.append((start, hi))
        quiet = max(runs, key=lambda r: r[1] - r[0], default=(0, 0))
        if quiet[1] - quiet[0] < 480:  # 20ms of measured silence
            raise ValueError('Edge narration has no safe silent scene boundary')
        cuts.append((quiet[0] + quiet[1]) // 2)
    cuts.append(len(samples))
    results = {}
    for item, group, start, end in zip(batch, groups, cuts, cuts[1:]):
        with wave.open(item['out_path'], 'wb') as wav:
            wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
            wav.writeframes(pcm[start * 2:end * 2])
        results[item['idx']] = {'words': [dict(w, start=w['start'] - start / 24000,
                                             end=w['end'] - start / 24000) for w in group]}
    return results


async def synthesize_scenes(batch, voices, rate='+12%', pitch='+0Hz'):
    """Return (scene results, actual voice) after a complete successful pass."""
    import edge_tts
    if not batch:
        return {}, voices[0]
    full_path = batch[0]['out_path'] + '.full.mp3'
    last_error = None
    try:
        for voice in dict.fromkeys(voices):
            try:
                print(f'[TTS] Edge continuous narration: {len(batch)} scenes, '
                      f'voice={voice}, rate={rate}, pitch={pitch}')
                words = []
                speech = edge_tts.Communicate(' '.join(item['text'] for item in batch),
                                             voice, rate=rate, pitch=pitch,
                                             boundary='WordBoundary')
                with open(full_path, 'wb') as audio:
                    async for chunk in speech.stream():
                        if chunk['type'] == 'audio':
                            audio.write(chunk['data'])
                        elif chunk['type'] == 'WordBoundary':
                            start = chunk['offset'] / 1e7
                            words.append(dict(text=chunk['text'].strip(), start=start,
                                              end=start + chunk['duration'] / 1e7))
                if not words or Path(full_path).stat().st_size < 1024:
                    raise ValueError('Edge returned empty audio or word boundaries')
                return split_scenes(batch, full_path, words), voice
            except Exception as error:
                last_error = error
                for item in batch:
                    Path(item['out_path']).unlink(missing_ok=True)
                print(f'[TTS] Edge performance failed ({voice}): {error}; retrying all scenes')
        raise RuntimeError(f'All Edge narration voices failed: {last_error}')
    finally:
        Path(full_path).unlink(missing_ok=True)

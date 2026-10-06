"""Opt-in expressive speech with audio-derived, transcript-checked captions.

Gemini has a free tier, not an unlimited-free guarantee. Keep account billing
unchanged and fall back at the whole-video boundary on quota/alignment failures.
"""
import base64
from functools import lru_cache
import json
import math
import os
import re
import time
from urllib.error import HTTPError, URLError
from http.client import IncompleteRead, RemoteDisconnected
import urllib.request
import wave


class SpeechPerformanceError(ValueError):
    """A complete retake may fix delivery; quotas/configuration may not."""


def _canonical(text):
    # Treat common numeric ASR spellings identically without weakening negations
    # or ignoring numbers. Unsupported spellings fail closed, never fuzzy-match.
    small = ('zero one two three four five six seven eight nine ten eleven twelve '
             'thirteen fourteen fifteen sixteen seventeen eighteen nineteen').split()
    tens = 'zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()
    def number(match):
        n = int(match[0])
        if n < 20:
            return small[n]
        if n < 100:
            return tens[n // 10] + (small[n % 10] if n % 10 else '')
        return match[0]
    text = re.sub(r'(?<=\d)\s*\.\s*(?=\d)', ' point ', text.lower()).replace('%', ' percent ').replace('−', '-')
    text = re.sub(r'(?<!\w)-(?=\d)', ' minus ', text).replace('+', ' plus ')
    text = re.sub(r'\d+', number, text)
    # Preserve word boundaries: "now here" must not match "nowhere".
    text = re.sub(r'(?<=[a-z])\s*-\s*(?=[a-z])', '', text)
    text = text.replace("'", '').replace('’', '')
    # Unknown symbols are significant (C#, currencies); never discard them.
    text = text.translate(str.maketrans({c: ' ' for c in ',.:;!?()[]{}"“”–—-'}))
    text = ' '.join(text.split())
    text = re.sub(r'\b(twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety) '
                  r'(one|two|three|four|five|six|seven|eight|nine)\b', r'\1\2', text)
    return text


def align_script(text, words, seconds):
    """Use measured word intervals; reject changed/missing speech.

    ASR sometimes splits hyphenated words or joins a written number. Keep the
    source spelling, grouping words that share an acoustic interval instead of
    manufacturing sub-word timing from character counts.
    """
    spans, heard, raw, previous = [], '', '', 0.0
    for word in words:
        start, end = float(word['start']), float(word['end'])
        if not all(math.isfinite(v) for v in (start, end)) or not 0 <= previous <= start <= end <= seconds + .05:
            raise ValueError('Invalid expressive speech alignment')
        previous = end
        raw += ' ' + word['text']
        normalized = _canonical(raw).replace(' ', '')
        if len(normalized) > len(heard):
            spans.append((len(heard), len(normalized), start, end))
        heard = normalized
    if not heard or _canonical(' '.join(w['text'] for w in words)) != _canonical(text):
        # Short diagnostics make production fallback actionable. The acceptance
        # comparison stays exact, including numbers, signs and negations.
        expected = _canonical(text).split()
        actual = _canonical(' '.join(w['text'] for w in words)).split()
        at = next((i for i, pair in enumerate(zip(expected, actual)) if pair[0] != pair[1]),
                  min(len(expected), len(actual)))
        raise SpeechPerformanceError('Expressive speech transcript differs from the script '
            f'at word {at + 1}: expected {" ".join(expected[at:at+5])!r}, '
            f'heard {" ".join(actual[at:at+5])!r}')
    result, offset = [], 0
    for token in text.split():
        size = len(_canonical(token).replace(' ', ''))
        if not size:
            continue
        matches = [s for s in spans if s[0] < offset + size and s[1] > offset]
        start, end = matches[0][2], matches[-1][3]
        if result and (start < result[-1]['end'] or result[-1]['start'] == result[-1]['end']):
            result[-1]['text'] += ' ' + token
            result[-1]['end'] = max(result[-1]['end'], end)
        else:
            result.append(dict(text=token, start=start, end=end))
        offset += size
    if result[-1]['start'] == result[-1]['end']:
        raise ValueError('Final spoken word has no usable acoustic interval')
    return result


@lru_cache(maxsize=1)
def _alignment_model():
    from faster_whisper import WhisperModel
    # base.en hallucinated an extra "Nice" on the CUDA audition's quiet tail;
    # small recovered the exact line without weakening the transcript guard.
    return WhisperModel('small', device='cpu', compute_type='int8', cpu_threads=2)


def build_speech_prompt(text, rate='+12%'):
    from tts_providers import edge_rate_to_speed
    target_wpm = round(185 * edge_rate_to_speed(rate) / 1.12)
    return (
        'AUDIO PROFILE: Lively, warm tech-and-science creator telling one friend '
        'something surprising. A close, clear conversational voice.\n'
        'SCENE: One connected short story for a phone viewer.\n'
        "DIRECTOR'S NOTES: Make the opening sentence immediate: land its first "
        'three words with conviction, with no introductory breath or long pause. '
        'Settle into a clear explanation, then brighten and lean in at the most '
        'surprising fact. Give the written reaction audible surprise and questions '
        'a curious upward inflection. Finish with a confident, useful payoff. '
        'Use connected phrasing, varied stress and natural pitch; avoid a repeated '
        'sentence-ending drop, news-anchor cadence, singsong delivery or shouting. '
        f'Brisk pace, about {target_wpm} words per minute; brief punctuation pauses. '
        'Speak ONLY the exact transcript below. Do not add reactions, filler, '
        'stage directions or a sign-off.\nTRANSCRIPT:\n' + text
    )


def synthesize(text, output, voice='Leda', rate='+12%'):
    key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not key:
        raise ValueError('GEMINI_API_KEY is required for expressive speech')
    prompt = build_speech_prompt(text, rate)
    payload = {'contents': [{'parts': [{'text': prompt}]}], 'generationConfig': {
        'responseModalities': ['AUDIO'], 'speechConfig': {'voiceConfig': {
            'prebuiltVoiceConfig': {'voiceName': voice}}}}}
    request = urllib.request.Request(
        'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent',
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
    with urllib.request.urlopen(request, timeout=120) as response:
        data = json.load(response)
    candidate = (data.get('candidates') or [{}])[0]
    if candidate.get('finishReason') != 'STOP':
        reason = candidate.get('finishReason', 'no candidate')
        error = SpeechPerformanceError if reason in ('OTHER', 'MAX_TOKENS') else ValueError
        raise error(f'Expressive speech did not complete ({reason})')
    audio = [p['inlineData'] for p in candidate.get('content', {}).get('parts', []) if 'inlineData' in p]
    if len(audio) != 1 or not audio[0].get('mimeType', '').startswith('audio/L16') or 'rate=24000' not in audio[0]['mimeType']:
        raise ValueError('Unexpected expressive speech audio format')
    pcm = base64.b64decode(audio[0]['data'], validate=True)
    if len(pcm) < 1024 or len(pcm) % 2:
        raise ValueError('Empty or invalid expressive speech audio')
    seconds = len(pcm) / 48000
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(pcm)
    for attempt in range(2):
        # Re-decode the same audio once without transcript priming. This can
        # resolve an ASR error without spending another API request, but neither
        # pass may discard mismatched words or manufacture word timestamps.
        segments, _ = _alignment_model().transcribe(output, language='en', word_timestamps=True,
            beam_size=5 if attempt == 0 else 8, condition_on_previous_text=False,
            initial_prompt=text if attempt == 0 else None)
        words = [dict(text=w.word.strip(), start=w.start, end=w.end) for segment in segments for w in segment.words]
        try:
            return align_script(text, words, seconds)
        except SpeechPerformanceError as error:
            if attempt:
                raise
            print(f'[TTS] Gemini alignment recheck on the same audio: {error}')


def synthesize_scenes(batch, voice='Leda', rate='+12%'):
    """One coherent performance; split only between measured scene words.

    Short isolated prompts can elicit unwanted continuations. Whole narration
    gives the performer context and uses one API request per video.
    """
    if not batch:
        return {}
    full_path = batch[0]['out_path'] + '.full.wav'
    try:
        for attempt in range(2):
            try:
                words = synthesize(' '.join(s['text'] for s in batch), full_path, voice=voice, rate=rate)
                break
            except (SpeechPerformanceError, URLError, TimeoutError, ConnectionError, IncompleteRead, RemoteDisconnected) as error:
                transient = (isinstance(error, (URLError, TimeoutError, ConnectionError, IncompleteRead, RemoteDisconnected))
                    and (not isinstance(error, HTTPError) or error.code in (408, 500, 502, 503, 504)))
                if attempt or not (transient or isinstance(error, SpeechPerformanceError)):
                    raise  # Quota/auth/config failures make no further requests.
                if os.path.exists(full_path):
                    os.remove(full_path)
                print(f'[TTS] Gemini complete retake 1/1 ({voice}): {error}')
                if transient:
                    time.sleep(1)
        groups, cursor = [], 0
        for scene in batch:
            target = sum(bool(_canonical(token)) for token in scene['text'].split())
            group, count = [], 0
            while count < target and cursor < len(words):
                word = words[cursor]
                group.append(word)
                count += len(word['text'].split())
                cursor += 1
            if not group or count != target:
                raise ValueError('Expressive alignment crosses a scene boundary')
            groups.append(group)
        if cursor != len(words):
            raise ValueError('Expressive alignment has unassigned words')
        with wave.open(full_path, 'rb') as wav:
            params = wav.getparams()
            pcm = wav.readframes(wav.getnframes())
        rate_hz = params.framerate
        cuts = [0] + [round((a[-1]['end'] + b[0]['start']) * rate_hz / 2)
                      for a, b in zip(groups, groups[1:])] + [params.nframes]
        result = {}
        for scene, group, start, end in zip(batch, groups, cuts, cuts[1:]):
            with wave.open(scene['out_path'], 'wb') as wav:
                wav.setparams(params)
                wav.writeframes(pcm[start * 2:end * 2])
            result[scene['idx']] = {'words': [dict(w, start=max(0., w['start'] - start/rate_hz),
                                                  end=w['end'] - start/rate_hz) for w in group]}
        return result
    except Exception:
        for scene in batch:
            if os.path.exists(scene['out_path']):
                os.remove(scene['out_path'])
        raise
    finally:
        if os.path.exists(full_path):
            os.remove(full_path)

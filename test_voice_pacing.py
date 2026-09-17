"""Exercise real audio trimming and scene fitting, not just configuration."""
import asyncio
import io
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

import main
import voice_pacing as pacing


def clip_bytes():
    # Speech-like tone from .4–1.4s, a quiet ending through 1.5s, then silence.
    import array
    samples = array.array('h', (int((6000 if .4 <= i / 24000 < 1.4 else
                                     100 if 1.4 <= i / 24000 < 1.5 else 0) *
                                    math.sin(i * 2 * math.pi * 440 / 24000))
                                for i in range(24000 * 3)))
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(24000)
        wav.writeframes(samples.tobytes())
    return output.getvalue()


class VoicePacingTests(unittest.TestCase):
    def test_estimator_accounts_for_explicit_rate_and_reading_floor(self):
        scenes = [{'text': 'One fact', 'voiceover': ' '.join(['word'] * 18)}]
        slow = main._estimate_spoken_seconds(scenes, 'edge', rate='+5%', pacing='tight')
        fast = main._estimate_spoken_seconds(scenes, 'edge', rate='+16%', pacing='tight')
        self.assertLess(fast, slow)
        self.assertGreaterEqual(main._estimate_spoken_seconds([{'text': 'Hi'}], 'edge', rate='+16%', pacing='tight'), 2)

    def test_short_speech_fits_two_seconds_and_long_speech_is_never_clipped(self):
        self.assertEqual(pacing.fit_frames(1.1, 60), 60)
        self.assertEqual(pacing.fit_frames(4.01, 60), 121)
        self.assertEqual(pacing.fit_frames(1.1, 108), 108)

    def test_reading_floor_accounts_for_dense_or_sequential_copy(self):
        self.assertEqual(pacing.reading_frames({'text': 'One fact'}), 60)
        self.assertGreaterEqual(pacing.reading_frames({'text': 'one two three four five six seven eight nine ten'}), 112)
        self.assertGreaterEqual(pacing.reading_frames({'type': 'list', 'durationInFrames': 200}), 200)

    def test_trim_preserves_quiet_ending_and_shifts_all_words_equally(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'speech.wav'
            source.write_bytes(clip_bytes())
            words = [{'text': 'Your', 'start': .4, 'end': .8}, {'text': 'model', 'start': .9, 'end': 1.4}]
            path, aligned, report = pacing.prepare_audio(str(source), words)
            self.assertAlmostEqual(report['trim_start'], .34, places=2)
            self.assertGreaterEqual(report['trim_end'], 1.67, 'quiet consonant/decay must survive')
            self.assertLess(report['seconds'], 1.36)
            for before, after in zip(words, aligned):
                self.assertAlmostEqual(before['start'] - after['start'], report['trim_start'])
                self.assertAlmostEqual(before['end'] - after['end'], report['trim_start'])
            self.assertEqual(words[0]['start'], .4, 'caller timings are not mutated')
            with wave.open(path) as wav:
                self.assertEqual(wav.getnframes() / wav.getframerate(), report['seconds'])
            self.assertGreater(report['seconds'], aligned[-1]['end'] + .18)

    def test_timing_outside_audio_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'speech.wav'; source.write_bytes(clip_bytes())
            with self.assertRaises(ValueError):
                pacing.prepare_audio(str(source), [{'text': 'bad', 'start': 0, 'end': 9}])

    def test_real_synthesis_path_offsets_and_explicit_rate(self):
        calls = []
        class Speech:
            def __init__(self, text, voice, **settings): calls.append(settings)
            async def stream(self):
                yield {'type': 'audio', 'data': clip_bytes()}
                yield {'type': 'WordBoundary', 'text': 'Your', 'offset': 4000000, 'duration': 4000000}
                yield {'type': 'WordBoundary', 'text': 'model', 'offset': 9000000, 'duration': 5000000}
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'VOICE_PACING': 'tight', 'VOICEOVER_RATE': '+5%'}):
            scenes = [{'text': 'Your model', 'durationInFrames': 150} for _ in range(2)]
            with patch('edge_tts.Communicate', Speech):
                name, words = asyncio.run(main._generate_voiceover_with_engine(
                    'edge', scenes, 'pacing-test', directory, rate='+12%', voice='en-US-JennyNeural', pitch='+0Hz'))
            self.assertEqual(calls[0]['rate'], '+12%')
            self.assertEqual([s['durationInFrames'] for s in scenes], [60, 60])
            self.assertAlmostEqual(words[2]['start'] - words[0]['start'], 2)
            self.assertGreater(words[0]['start'], 0)
            self.assertTrue((Path(directory) / name).exists())
            self.assertFalse(list(Path(directory).glob('temp-*')), 'raw and paced clips are cleaned')

    def test_empty_audio_still_aborts(self):
        class Empty:
            def __init__(self, *args, **kwargs): pass
            async def stream(self): yield {'type': 'audio', 'data': b''}
        with tempfile.TemporaryDirectory() as directory, patch('edge_tts.Communicate', Empty), patch.object(main, 'REQUIRE_VOICEOVER', True):
            with self.assertRaises(Exception):
                asyncio.run(main._generate_voiceover_with_engine('edge', [{'text': 'Your model'}], 'empty-pacing', directory))

    def test_audition_diagnostics_keep_silent_scene_indices(self):
        from scripts import preview_editorial as review
        class Speech:
            def __init__(self, *args, **kwargs): pass
            async def stream(self):
                yield {'type': 'audio', 'data': clip_bytes()}
                yield {'type': 'WordBoundary', 'text': 'Your', 'offset': 4000000, 'duration': 4000000}
                yield {'type': 'WordBoundary', 'text': 'model', 'offset': 9000000, 'duration': 5000000}
        with tempfile.TemporaryDirectory() as directory, patch('edge_tts.Communicate', Speech), patch.object(review, 'ROOT', Path(directory)):
            (Path(directory) / 'public').mkdir()
            props = {'scenes': [{'text': 'Your model'},
                                {'text': '', 'voiceover': '', 'durationInFrames': 30},
                                {'text': 'Your model'}]}
            report = asyncio.run(review.audition(props, 'local fixture', 'silent-review',
                                'en-US-JennyNeural', '+12%', '+0Hz', 'tight'))
            self.assertEqual([c['scene'] for c in report['clips']], [0, 2])
            self.assertEqual(report['clips'][1]['offset'], 3)
            self.assertAlmostEqual(report['clips'][1]['last_word'], 1.06, places=2)

    def test_pacing_matrices_do_not_overwrite_each_other(self):
        from scripts import preview_editorial as review
        from argparse import Namespace
        labels = []
        async def capture(props, source, label, *args):
            labels.append(label)
            return {'label': label}
        with tempfile.TemporaryDirectory() as directory, patch.object(review, 'ROOT', Path(directory)), patch.object(review, 'audition', capture), patch.object(review, 'load_props', return_value=({}, 'local')), patch.object(review, 'kokoro_python', return_value=''):
            output = Path(directory) / 'out/voice-review'; output.mkdir(parents=True)
            for pacing_mode in ('legacy', 'tight'):
                asyncio.run(review.run(Namespace(report=False, story='quantization', fixture=None,
                                                auditions=True, pacing=pacing_mode)))
            self.assertEqual(len(set(labels)), 12)
            self.assertEqual(len(list(output.glob('*-auditions.json'))), 2)


if __name__ == '__main__': unittest.main()

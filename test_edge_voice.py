"""Continuous Edge delivery must keep words, acoustic tails and one narrator."""
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


def audio_and_words(text):
    import array
    tokens = text.split()
    words = [dict(text=t, start=.2 + i * .6, end=.6 + i * .6)
             for i, t in enumerate(tokens)]
    samples = array.array('h', (int(6000 * math.sin(i * 2 * math.pi * 440 / 24000))
                              if any(w['start'] <= i / 24000 < w['end'] + .04 for w in words)
                              else 0 for i in range(round((len(tokens) * .6 + .3) * 24000))))
    out = io.BytesIO()
    with wave.open(out, 'wb') as wav:
        wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        wav.writeframes(samples.tobytes())
    return out.getvalue(), words


class EdgeVoiceTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'VOICE_PACING': 'tight', 'VOICE_FLOW': 'continuous', 'VOICEOVER_VOICE': '',
                                     'VOICEOVER_PITCH': '', 'VOICE_IDENTITY': 'consistent'})
        env.start(); self.addCleanup(env.stop)

    def render(self, fail=False, wrapper=False):
        requests = []
        class Speech:
            def __init__(self, text, voice, **settings):
                self.text, self.voice = text, voice
                requests.append((text, voice, settings))
            async def stream(self):
                audio, words = audio_and_words(self.text)
                yield {'type': 'audio', 'data': audio}
                if fail and self.voice == 'en-US-AriaNeural' and 'Great' in self.text:
                    raise RuntimeError('connection lost after partial audio')
                for w in words:
                    yield {'type': 'WordBoundary', 'text': w['text'],
                           'offset': round(w['start'] * 1e7),
                           'duration': round((w['end'] - w['start']) * 1e7)}
        with tempfile.TemporaryDirectory() as directory, patch('edge_tts.Communicate', Speech):
            scenes = [dict(type='hero', text='Hello there.', durationInFrames=120),
                      dict(type='split', text='Great, right?', durationInFrames=150)]
            if wrapper:
                name, words = asyncio.run(main.generate_voiceover_and_alignment(
                    scenes, 'edge-flow-test', directory, voice='gemini:Leda'))
            else:
                name, words = asyncio.run(main._generate_voiceover_with_engine(
                    'edge', scenes, 'edge-flow-test', directory, voice='en-US-AriaNeural'))
            self.assertTrue((Path(directory) / name).exists())
            self.assertFalse(list(Path(directory).glob('temp-*')))
            self.assertEqual([w['text'] for w in words], ['Hello', 'there.', 'Great,', 'right?'])
            self.assertLessEqual(words[-1]['end'], sum(s['durationInFrames'] for s in scenes) / 30)
            return requests, list(main.render_status_store['edge-flow-test']['voice_scene_timings'])

    def test_whole_narration_supplies_context_and_keeps_measured_subtitles(self):
        requests, timings = self.render()
        self.assertEqual([r[0] for r in requests], ['Hello there. Great, right?'])
        self.assertEqual(len(timings), 2)
        self.assertGreater(timings[0]['seconds'], timings[0]['last_word'])

    def test_partial_failure_retries_all_words_on_one_voice(self):
        requests, timings = self.render(fail=True)
        self.assertEqual(len({t['voice'] for t in timings}), 1,
                         'a recovered reel must never contain two narrators')
        self.assertNotEqual(timings[0]['voice'], 'en-US-AriaNeural')
        self.assertTrue(all(r[0] == 'Hello there. Great, right?' for r in requests))

    def test_missing_gemini_key_recovers_with_complete_key_free_emma(self):
        with patch.dict(os.environ, {'GEMINI_API_KEY': ''}):
            requests, timings = self.render(wrapper=True)
        self.assertEqual([r[0] for r in requests], ['Hello there. Great, right?'])
        self.assertEqual({t['voice'] for t in timings}, {'en-US-EmmaNeural'})
        status = main.render_status_store['edge-flow-test']
        self.assertEqual(status['tts_provider'], 'edge')
        self.assertIn('GEMINI_API_KEY', status['tts_fallback_reason'])

    def test_split_retains_every_pcm_sample_and_silent_scene_indices(self):
        import edge_voice
        audio, words = audio_and_words('Hello there. Great, right?')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'full.wav'; source.write_bytes(audio)
            batch = [dict(idx=i, text=t, out_path=str(Path(directory) / f'{i}.wav'))
                     for i, t in ((0, 'Hello there.'), (2, 'Great, right?'))]
            result = edge_voice.split_scenes(batch, source, words)
            self.assertEqual(set(result), {0, 2})
            combined = b''
            for item in batch:
                with wave.open(item['out_path']) as wav:
                    combined += wav.readframes(wav.getnframes())
            with wave.open(str(source)) as wav:
                self.assertEqual(combined, wav.readframes(wav.getnframes()))
            self.assertLess(result[2]['words'][0]['start'], .2)

    def test_missing_negation_is_rejected_before_any_scene_is_written(self):
        import edge_voice
        audio, words = audio_and_words('It can run.')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'full.wav'; source.write_bytes(audio)
            output = Path(directory) / 'scene.wav'
            with self.assertRaisesRegex(ValueError, 'transcript differs'):
                edge_voice.split_scenes([dict(idx=0, text="It can't run.", out_path=str(output))], source, words)
            self.assertFalse(output.exists())

    def test_metadata_gap_without_acoustic_silence_cannot_cut_speech(self):
        import edge_voice
        import array
        audio, words = audio_and_words('Hello there. Great, right?')
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'full.wav'
            with wave.open(str(source), 'wb') as wav:
                wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                wav.writeframes(array.array('h', [3000] * 64800).tobytes())
            batch = [dict(idx=i, text=t, out_path=str(Path(directory) / f'{i}.wav'))
                     for i, t in enumerate(('Hello there.', 'Great, right?'))]
            with self.assertRaisesRegex(ValueError, 'no safe silent'):
                edge_voice.split_scenes(batch, source, words)
            self.assertEqual(list(Path(directory).iterdir()), [source])


if __name__ == '__main__':
    unittest.main()

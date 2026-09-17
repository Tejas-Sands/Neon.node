"""The expressive provider must earn its captions from the actual audio."""
import os
import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import expressive_voice as voice
from tts_providers import resolve_tts_engine


class ExpressiveVoiceTests(unittest.TestCase):
    def test_gemini_voice_rotation_is_seeded_and_explicit_voice_wins(self):
        import main
        first = main.select_gemini_voice('voice-rotation-a')
        self.assertEqual(first, main.select_gemini_voice('voice-rotation-a'))
        choices = {main.select_gemini_voice(f'voice-rotation-{i}') for i in range(24)}
        self.assertGreater(len(choices), 1)
        self.assertTrue(choices <= set(main.GEMINI_VOICE_POOL))
        self.assertEqual(main.select_gemini_voice('voice-rotation-a', 'gemini:Leda'), 'Leda')

    def test_gemini_prompt_calls_for_immediate_opening_hook(self):
        prompt = voice.build_speech_prompt('Three tools just changed your build.', '+12%')
        self.assertIn('opening sentence', prompt)
        self.assertIn('immediate', prompt)

    def test_transcript_matches_but_preserves_script_spelling(self):
        words = [dict(text="Here's", start=0.0, end=.3),
                 dict(text='the', start=.3, end=.5),
                 dict(text='trade', start=.5, end=.7),
                 dict(text='-off.', start=.7, end=.9),
                 dict(text='32', start=1.0, end=1.5),
                 dict(text='bits.', start=1.5, end=1.8)]
        aligned = voice.align_script("Here's the tradeoff: thirty-two bits.", words, 2.0)
        self.assertEqual([w['text'] for w in aligned], ["Here's", 'the', 'tradeoff:', 'thirty-two', 'bits.'])
        self.assertEqual((aligned[2]['start'], aligned[2]['end']), (.5, .9))
        self.assertEqual(aligned[-1]['end'], 1.8)

    def test_changed_or_missing_words_are_rejected(self):
        words = [dict(text='It', start=0., end=.2), dict(text='can', start=.2, end=.4),
                 dict(text='run', start=.4, end=.6)]
        for text in ("It can't run", 'It can run locally', 'It cannot run'):
            with self.assertRaises(ValueError): voice.align_script(text, words, 1.)

    def test_invalid_audio_timings_are_rejected(self):
        for start, end in [(float('nan'), .5), (.5, .4), (-.1, .5), (0., 2.)]:
            with self.assertRaises(ValueError):
                voice.align_script('Hello', [dict(text='Hello', start=start, end=end)], 1.)

    def test_decimal_split_by_recognizer_keeps_following_word_timing(self):
        words = [dict(text='8', start=0., end=.2), dict(text='.0', start=.2, end=.5),
                 dict(text='works.', start=.6, end=1.)]
        result = voice.align_script('8.0 works.', words, 1.)
        self.assertEqual(result, [dict(text='8.0', start=0., end=.5), words[2]])

    def test_numeric_signs_and_language_names_are_not_discarded(self):
        for script, heard in [('-32', '32'), ('C++', 'C'), ('+12', '12'),
                              ('−12', '12'), ('C#', 'C'), ('€12', '$12')]:
            with self.assertRaises(ValueError):
                voice.align_script(script, [dict(text=heard, start=0., end=.5)], 1.)
        with self.assertRaises(ValueError):
            voice.align_script('Your model is now here.', [dict(text='Your model is nowhere.', start=0., end=1.)], 2.)

    def test_quota_failure_stops_requests_and_cleans_audio(self):
        import main
        def fail(text, output, **kwargs):
            Path(output).write_bytes(b'partial')
            raise ValueError('quota exhausted')
        with tempfile.TemporaryDirectory() as directory, patch.object(voice, 'synthesize', side_effect=fail) as synth, patch.object(main, 'REQUIRE_VOICEOVER', False):
            with self.assertRaisesRegex(Exception, 'quota exhausted'):
                asyncio.run(main._generate_voiceover_with_engine('gemini', [dict(text='Hello')]*3, 'quota-test', directory))
            self.assertEqual(synth.call_count, 1)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_explicit_provider_and_voice_precedence(self):
        with patch.dict(os.environ, {'TTS_PROVIDER': 'edge', 'VOICEOVER_VOICE': ''}):
            self.assertEqual(resolve_tts_engine('gemini:Leda'), 'gemini')
            self.assertEqual(resolve_tts_engine(), 'edge')
        with patch.dict(os.environ, {'TTS_PROVIDER': 'gemini', 'VOICEOVER_VOICE': ''}):
            self.assertEqual(resolve_tts_engine(), 'gemini')
            self.assertEqual(resolve_tts_engine('en-US-AriaNeural'), 'edge')

    def test_expressive_audio_uses_shared_fitting_and_captions(self):
        import main
        from test_voice_pacing import clip_bytes
        def synthesize_scenes(batch, **kwargs):
            result = {}
            for scene in batch:
                Path(scene['out_path']).write_bytes(clip_bytes())
                result[scene['idx']] = {'words': [dict(text='Your', start=.4, end=.8), dict(text='model', start=.9, end=1.4)]}
            return result
        with tempfile.TemporaryDirectory() as directory, patch.object(voice, 'synthesize_scenes', synthesize_scenes), patch('edge_tts.Communicate', side_effect=AssertionError('Gemini path must not use Edge')), patch.dict(os.environ, {'VOICE_PACING':'tight'}):
            scenes = [dict(text='Your model', durationInFrames=150) for _ in range(2)]
            name, words = asyncio.run(main._generate_voiceover_with_engine('gemini', scenes, 'expressive-test', directory, voice='gemini:Leda'))
            self.assertEqual([s['durationInFrames'] for s in scenes], [60, 60])
            self.assertAlmostEqual(words[2]['start'] - words[0]['start'], 2.)
            self.assertEqual(main.render_status_store['expressive-test']['resolved_voice'], 'gemini:Leda')
            self.assertTrue((Path(directory)/name).exists())
            self.assertFalse(list(Path(directory).glob('temp-*')))

    def test_batch_keeps_acoustic_offsets_without_cutting_words(self):
        import wave
        def synthesize(text, output, **kwargs):
            self.assertEqual(text, 'Hello there. Great, right?')
            with wave.open(output, 'wb') as wav:
                wav.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
                wav.writeframes(b'\0\0' * 72000)
            return [dict(text='Hello', start=.1, end=.5), dict(text='there.', start=.5, end=1.),
                    dict(text='Great,', start=1.5, end=2.), dict(text='right?', start=2., end=2.7)]
        with tempfile.TemporaryDirectory() as directory, patch.object(voice, 'synthesize', side_effect=synthesize) as synth:
            batch = [dict(idx=i, text=t, out_path=str(Path(directory)/f'{i}.wav')) for i,t in enumerate(('Hello there.', 'Great, right?'))]
            result = voice.synthesize_scenes(batch)
            self.assertEqual(synth.call_count, 1)
            self.assertAlmostEqual(result[1]['words'][0]['start'], .25)
            with wave.open(batch[0]['out_path']) as wav:
                self.assertEqual(wav.getnframes(), 30000)
            with wave.open(batch[1]['out_path']) as wav:
                self.assertEqual(wav.getnframes(), 42000)
            self.assertEqual(len(list(Path(directory).iterdir())), 2)

    def test_expressive_failure_restarts_the_whole_video(self):
        import main
        calls = []
        async def render(engine, scenes, session, directory, voice, rate, pitch):
            calls.append((engine, scenes[0]['durationInFrames'], voice))
            if engine == 'gemini':
                scenes[0]['durationInFrames'] = 66
                raise ValueError('Transcript mismatch')
            return ('fallback.mp3', [])
        with patch.object(main, '_generate_voiceover_with_engine', render):
            asyncio.run(main.generate_voiceover_and_alignment([dict(text='Hello', durationInFrames=150)], 'expressive-failure', '/tmp', voice='gemini:Leda'))
        self.assertEqual(calls, [('gemini', 150, 'gemini:Leda'), ('edge', 150, 'en-US-AriaNeural')])


if __name__ == '__main__': unittest.main()

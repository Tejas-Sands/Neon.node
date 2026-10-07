"""Offline HTTP-boundary regressions for JSON failover and timing repairs."""
import asyncio
from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import main
from test_retention import story


def completion(content, finish_reason='stop'):
    return SimpleNamespace(status_code=200, headers={}, text='', json=lambda: {
        'choices': [{'message': {'content': content}, 'finish_reason': finish_reason}]})


class LLMFailoverTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {'GEMINI_API_KEY': 'test'}, clear=True))
        for name, value in (('_LLM_DEAD_MODELS', set()), ('_LLM_DEAD_PROVIDERS', set()),
                            ('_LLM_MODEL_CATALOG', {}), ('_LLM_JSON_PREFERRED', {}),
                            ('render_status_store', {})):
            self.stack.enter_context(patch.object(main, name, value, create=True))
        self.stack.enter_context(patch.object(main, '_llm_live_models',
            side_effect=lambda provider, url, key, models, prefix, **kwargs: models[:3]))
        self.stack.enter_context(patch.object(main.time, 'sleep'))

    def test_json_reuses_successful_fallback_after_overload_or_truncation(self):
        for failure in (SimpleNamespace(status_code=503, text='High demand', headers={}),
                        completion('{"scenes":[', 'length')):
            with self.subTest(failure=failure):
                tried = []
                main._LLM_JSON_PREFERRED.clear()

                def respond(url, **kwargs):
                    model = kwargs['json']['model']
                    tried.append(model)
                    return failure if model == 'gemini-3.5-flash' else completion('{"ok":true}')

                with patch.object(main.requests, 'post', side_effect=respond):
                    self.assertEqual(json.loads(main.query_llm_with_failover(
                        'JSON only', 'Plan', session_id='video-a', reuse_session_model=True)), {'ok': True})
                    tried.clear()
                    self.assertEqual(json.loads(main.query_llm_with_failover(
                        'JSON only', 'Script', session_id='video-a', reuse_session_model=True)), {'ok': True})
                self.assertEqual(tried, ['gemini-3.5-flash-lite'])
                self.assertNotIn(('Gemini', 'gemini-3.5-flash'), main._LLM_DEAD_MODELS)

    def test_preference_does_not_change_captions_or_other_sessions(self):
        tried = []
        primary_busy = True

        def respond(url, **kwargs):
            payload = kwargs['json']
            tried.append(payload['model'])
            if primary_busy and payload['model'] == 'gemini-3.5-flash':
                return SimpleNamespace(status_code=503, text='High demand', headers={})
            return completion('{"ok":true}' if 'response_format' in payload else 'Finished caption.')

        with patch.object(main.requests, 'post', side_effect=respond):
            main.query_llm_with_failover('JSON only', 'Plan', session_id='video-a', reuse_session_model=True)
            primary_busy = False
            tried.clear()
            self.assertEqual(main.query_llm_with_failover(
                'Caption', 'Caption', json_format=False, session_id='video-a'), 'Finished caption.')
            main.query_llm_with_failover('JSON only', 'Plan', session_id='video-b', reuse_session_model=True)
        self.assertEqual(tried, ['gemini-3.5-flash', 'gemini-3.5-flash'])

    def test_youtube_metadata_keeps_default_order_after_narration_fallback(self):
        main._LLM_JSON_PREFERRED['video-a'] = ('Gemini', 'gemini-3.5-flash-lite')
        tried = []

        def respond(url, **kwargs):
            model = kwargs['json']['model']
            tried.append(model)
            return completion(json.dumps({'title': 'Postgres index lookups',
                                         'description': 'Postgres reuses index locations. #Shorts',
                                         'tags': ['postgres', 'database']}))

        with patch.object(main.requests, 'post', side_effect=respond):
            meta = main.generate_youtube_metadata({'scenes': story()}, 'test', session_id='video-a')
        self.assertEqual(meta['title'], 'Postgres index lookups')
        self.assertEqual(tried, ['gemini-3.5-flash'])
        self.assertEqual(main._LLM_JSON_PREFERRED['video-a'], ('Gemini', 'gemini-3.5-flash-lite'))

    def test_a_failing_preferred_model_still_recovers_through_the_chain(self):
        primary_busy = True
        tried = []

        def respond(url, **kwargs):
            model = kwargs['json']['model']
            tried.append(model)
            if (model == 'gemini-3.5-flash') == primary_busy:
                return SimpleNamespace(status_code=503, text='High demand', headers={})
            return completion('{"ok":true}')

        with patch.object(main.requests, 'post', side_effect=respond):
            main.query_llm_with_failover('JSON only', 'Plan', session_id='video-a', reuse_session_model=True)
            primary_busy = False
            tried.clear()
            self.assertEqual(json.loads(main.query_llm_with_failover(
                'JSON only', 'Repair', session_id='video-a', reuse_session_model=True)), {'ok': True})
        self.assertEqual(tried[0], 'gemini-3.5-flash-lite')
        self.assertEqual(tried[-1], 'gemini-3.5-flash')

    def test_overbudget_http_success_falls_through_and_regenerates_all_audio(self):
        scenes = story()
        original = ('Subscribers of Paramount Plus and HBO Max, along with viewers of CBS and CNN, '
                    'now share a single parent company following the $111 billion deal.')
        repaired = ('Paramount Plus, HBO Max, CBS and CNN share a parent company '
                    'after the $111 billion deal.')
        scenes[2].update(title='SHARED OWNER', text='One parent company', voiceover=original)
        before = copy.deepcopy(scenes)
        spoken, tried = [], []

        def respond(url, **kwargs):
            model = kwargs['json']['model']
            tried.append(model)
            line = original if model in ('gemini-3.5-flash', 'gemini-3.5-flash-lite') else repaired
            return completion(json.dumps({'scenes': [{'scene': 2, 'voiceover': line}]}))

        async def synth(items, session, directory, **kwargs):
            spoken.append(copy.deepcopy(items))
            items[2]['durationInFrames'] = 304 if len(spoken) == 1 else 240
            main.render_status_store.setdefault(session, {})['resolved_voice'] = 'en-US-AvaNeural'
            Path(directory, 'narration.mp3').write_bytes(str(len(spoken)).encode())
            return 'narration.mp3', [dict(text=items[2]['voiceover'], start=0, end=7.8)]

        with tempfile.TemporaryDirectory() as directory, patch.object(
                main.requests, 'post', side_effect=respond), patch.object(
                main, 'generate_voiceover_and_alignment', synth):
            try:
                name, words = asyncio.run(main._generate_retention_voiceover(
                    scenes, 'merger-repair', directory, max_seconds=70))
            except main.RetentionError as error:
                self.fail(f'An unusable HTTP success blocked a valid fallback: {error}')
            self.assertEqual(Path(directory, name).read_bytes(), b'2')
        self.assertEqual(tried, ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'])
        self.assertEqual(len(spoken), 2)
        self.assertEqual(spoken[0], before)
        self.assertEqual(spoken[1][2]['voiceover'], repaired)
        self.assertEqual(scenes[:2], before[:2])
        self.assertEqual(words[0]['text'], repaired)
        self.assertEqual(main.render_status_store['merger-repair']['retention']['repairs'], 1)

    def test_qualifier_losing_http_success_falls_through_without_mutating_copy(self):
        scenes = story()
        before = copy.deepcopy(scenes)
        tried = []

        def respond(url, **kwargs):
            self.assertEqual(scenes, before)
            model = kwargs['json']['model']
            tried.append(model)
            line = 'Your database writes skip another index lookup.' if len(tried) == 1 else 'Writes can skip second lookups.'
            return completion(json.dumps({'scenes': [{'scene': 0, 'voiceover': line}]}))

        with patch.object(main.requests, 'post', side_effect=respond):
            main._revise_retention_copy(scenes, {0: 8}, '', 'claim-repair', 'facts-explainer')
        self.assertEqual(scenes[0]['voiceover'], 'Writes can skip second lookups.')
        self.assertEqual(scenes[1:], before[1:])
        self.assertEqual(tried, ['gemini-3.5-flash', 'gemini-3.5-flash-lite'])

    def test_exhausted_semantic_fallbacks_keep_two_pass_cap_and_remove_audio(self):
        scenes = story()
        before = copy.deepcopy(scenes)
        tried, spoken = [], []

        def respond(url, **kwargs):
            tried.append(kwargs['json']['model'])
            return completion(json.dumps({'scenes': [{'scene': 0, 'voiceover': before[0]['voiceover']}]}))

        async def synth(items, session, directory, **kwargs):
            spoken.append(copy.deepcopy(items))
            items[0]['durationInFrames'] = 180
            Path(directory, 'narration.mp3').write_bytes(b'overlong')
            return 'narration.mp3', []

        with tempfile.TemporaryDirectory() as directory, patch.object(
                main.requests, 'post', side_effect=respond), patch.object(
                main, 'generate_voiceover_and_alignment', synth):
            with self.assertRaisesRegex(main.RetentionError, 'after 2 repairs') as failure:
                asyncio.run(main._generate_retention_voiceover(
                    scenes, 'exhausted-repair', directory, max_seconds=70))
            self.assertFalse(Path(directory, 'narration.mp3').exists())
        self.assertIn('9 words (max 5)', str(failure.exception))
        self.assertEqual(tried, ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-3.1-flash-lite'] * 2)
        self.assertEqual(spoken, [before])
        self.assertEqual(scenes, before)
        self.assertEqual(main._LLM_DEAD_MODELS, set())

    def test_preferred_provider_recovers_before_retrying_unavailable_provider(self):
        self.stack.enter_context(patch.dict(os.environ, {'GROQ_API_KEY': 'test'}))
        tried = []

        def respond(url, **kwargs):
            model = kwargs['json']['model']
            tried.append(model)
            if 'googleapis.com' in url:
                return SimpleNamespace(status_code=401, text='Invalid API key', headers={})
            return completion('{"ok":true}')

        with patch.object(main.requests, 'post', side_effect=respond):
            main.query_llm_with_failover('JSON only', 'Plan', session_id='video-a', reuse_session_model=True)
            # A provider rejected on an earlier call remains skipped. A session
            # with a working provider should still start there if that key recovers.
            main._LLM_DEAD_PROVIDERS.clear()
            tried.clear()
            self.assertEqual(json.loads(main.query_llm_with_failover(
                'JSON only', 'Script', session_id='video-a', reuse_session_model=True)), {'ok': True})
        self.assertEqual(tried, ['openai/gpt-oss-120b'])


if __name__ == '__main__':
    unittest.main()

"""Regression coverage for the production opening and measured pacing failures."""
import asyncio
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import main
from retention import repair_targets, preserves_claim


def story():
    return [
        dict(type='hero', title='POSTGRES WRITES', text='Less index work',
             voiceover='Your database writes can skip a second index lookup.', durationInFrames=110),
        dict(type='split', title='ONE LOOKUP', text='Reuse the index location',
             voiceover='Postgres reuses the index location instead of searching twice.', durationInFrames=150),
        dict(type='split', title='THE LIMIT', text='Only matching updates benefit',
             voiceover='Your matching updates benefit; other writes still need both lookups.', durationInFrames=150),
    ]


class RetentionTests(unittest.TestCase):
    def test_measured_boundaries_and_total_include_countdowns(self):
        scenes = story()
        scenes[1]['type'] = 'list'
        scenes[1]['listItems'] = ['Reuse the index location', 'Avoid the second search']
        scenes[0]['durationInFrames'] = 120
        scenes[1]['durationInFrames'] = 250
        self.assertEqual(repair_targets(scenes, measured=True, max_seconds=30), {})
        scenes[0]['durationInFrames'] = 121
        scenes[1]['durationInFrames'] = 251
        self.assertEqual(set(repair_targets(scenes, measured=True)), {0, 1})
        scenes = story() + [dict(type='countdown', voiceover='', text='', durationInFrames=90)]
        targets = repair_targets(scenes, measured=True, max_seconds=15)
        self.assertTrue(targets)
        self.assertNotIn(3, targets)

    def test_claim_guard_preserves_sign_units_modality_and_conditions(self):
        for before, after in (
            ('It costs -2 dollars.', 'It costs 2 dollars.'),
            ('It needs 32 GB.', 'It needs 32 MB.'),
            ('It may run locally.', 'It runs locally.'),
            ('It works only on Linux.', 'It works on Linux.'),
            ('It takes thirty-two bits.', 'It takes four bits.'),
            ('They reported a speedup.', 'They proved a speedup.'),
        ):
            self.assertFalse(preserves_claim(before, after), (before, after))
        self.assertTrue(preserves_claim('Your install can fail before the build. Check the lockfile.',
                                       'A lockfile mismatch can stop your install.'))
    def test_hook_limits_are_hard_failures(self):
        scenes = story()
        scenes[0].update(voiceover=' '.join(['writes'] * 13), title=' '.join(['title'] * 5),
                         text=' '.join(['label'] * 9))
        hard, _ = main._script_vagueness_reasons({'scenes': scenes})
        self.assertTrue(any('hook voiceover' in x for x in hard), hard)
        self.assertEqual(sum('hook on-screen' in x for x in hard), 2)

    def test_actual_audio_is_revised_and_resynthesized_without_clipping(self):
        self.assertTrue(hasattr(main, '_generate_retention_voiceover'))
        scenes = story()
        scenes[1].update(type='list', listItems=['Reuse the index location', 'Avoid the second search'])
        scenes[1]['imageUrl'] = 'data:image/png;base64,PRIVATE_ASSET'
        calls = []
        async def synth(items, session, directory, **kwargs):
            calls.append(copy.deepcopy(items))
            frames = [158, 300, 180] if len(calls) == 1 else [90, 210, 180]
            for item, count in zip(items, frames):
                item['durationInFrames'] = count
            main.render_status_store.setdefault(session, {})['resolved_voice'] = 'en-US-AriaNeural'
            main.render_status_store[session]['tts_fallback_reason'] = 'transcript mismatch'
            Path(directory, 'narration.mp3').write_bytes(str(len(calls)).encode())
            return 'narration.mp3', [dict(text='final', start=0, end=frames[0]/30)]
        response = json.dumps({'scenes': [
            {'scene': 0, 'voiceover': 'Writes can skip second lookups.'},
            {'scene': 1, 'voiceover': 'Postgres avoids searching twice.'},
        ]})
        with tempfile.TemporaryDirectory() as directory, patch.object(main, 'generate_voiceover_and_alignment', synth), patch.object(main, 'query_llm_with_failover', return_value=response) as llm:
            name, words = asyncio.run(main._generate_retention_voiceover(
                scenes, 'retention-test', directory, source_prompt='Postgres reuses the index location.',
                format_pack='facts-explainer', max_seconds=30))
            self.assertEqual([s['durationInFrames'] for s in scenes], [90, 210, 180])
            self.assertEqual(Path(directory, name).read_bytes(), b'2')
            self.assertEqual(words[0]['end'], 3.)
            self.assertNotIn('PRIVATE_ASSET', llm.call_args.kwargs['user_prompt'])
        self.assertEqual(len(calls), 2)
        self.assertEqual(scenes[1]['imageUrl'], 'data:image/png;base64,PRIVATE_ASSET')
        self.assertEqual(main.render_status_store['retention-test']['retention']['revision'], 'opening-v1')

    def test_failed_repairs_abort_and_remove_rejected_audio(self):
        self.assertTrue(hasattr(main, '_generate_retention_voiceover'))
        async def synth(items, session, directory, **kwargs):
            items[0]['durationInFrames'] = 180
            Path(directory, 'narration.mp3').write_bytes(b'overlong')
            return 'narration.mp3', []
        with tempfile.TemporaryDirectory() as directory, patch.object(main, 'generate_voiceover_and_alignment', synth), patch.object(main, 'query_llm_with_failover', return_value='{}'):
            with self.assertRaisesRegex(ValueError, 'retention'):
                asyncio.run(main._generate_retention_voiceover(
                    story(), 'retention-failure', directory, format_pack='facts-explainer', max_seconds=30))
            self.assertFalse(Path(directory, 'narration.mp3').exists())

    def test_copy_failure_after_pack_rebuild_is_checked_before_synthesis(self):
        self.assertTrue(hasattr(main, '_generate_retention_voiceover'))
        scenes = story()
        scenes[0]['voiceover'] = ' '.join(['Postgres'] * 16)
        with tempfile.TemporaryDirectory() as directory, patch.object(main, 'generate_voiceover_and_alignment', side_effect=AssertionError('bad copy reached TTS')), patch.object(main, 'query_llm_with_failover', return_value='{}'):
            with self.assertRaisesRegex(ValueError, 'retention'):
                asyncio.run(main._generate_retention_voiceover(
                    scenes, 'retention-copy', directory, format_pack='facts-explainer', max_seconds=30))

    def test_overlong_quiz_brief_degrades_before_it_can_rebuild_a_bad_hook(self):
        brief = dict(question='How many seconds did the latest database release require for each lookup?',
                     options=['2 seconds', '3 seconds', '4 seconds'], answer_index=0,
                     answer_fact='The database release requires 2 seconds for each lookup.')
        with patch.object(main, 'query_llm_with_failover', return_value=json.dumps(brief)):
            self.assertIsNone(main.plan_pack_brief('quiz-reveal', 'Database release', brief['answer_fact']))

    def test_revision_rejects_new_numbers_and_quiz_spoilers(self):
        self.assertTrue(hasattr(main, '_revise_retention_copy'))
        scenes = story()
        for response, brief in [
            ({'scenes': [{'scene': 0, 'voiceover': 'Your database runs 900 times faster.'}]}, None),
            ({'scenes': [{'scene': 0, 'voiceover': 'Is Postgres the answer?'}]},
             {'kind': 'quiz', 'options': ['Postgres', 'Redis', 'SQLite'], 'answer_index': 0}),
        ]:
            with patch.object(main, 'query_llm_with_failover', return_value=json.dumps(response)):
                with self.assertRaises(ValueError):
                    main._revise_retention_copy(scenes, {0: 8}, 'source Postgres database writes',
                                                'retention-invalid', 'quiz-reveal' if brief else 'facts-explainer', brief)
        self.assertEqual(scenes, story())

    def test_verified_reveal_and_scene_shape_cannot_be_rewritten(self):
        self.assertTrue(hasattr(main, '_revise_retention_copy'))
        scenes = story()
        brief = {'kind': 'quiz', 'options': ['Postgres', 'Redis', 'SQLite'], 'answer_index': 0}
        for patch_data in ({'scene': 2, 'voiceover': 'Changed proof.'},
                           {'scene': 0, 'type': 'split', 'voiceover': 'Your writes skip an index lookup.'}):
            with patch.object(main, 'query_llm_with_failover', return_value=json.dumps({'scenes': [patch_data]})):
                with self.assertRaises(ValueError):
                    main._revise_retention_copy(scenes, {0: 8}, '', 'retention-protected', 'quiz-reveal', brief)
        self.assertEqual(scenes, story())

    def test_rewrite_cannot_remove_negation_or_scope(self):
        scenes = story()
        scenes[1]['voiceover'] = 'Your model cannot run locally without a cloud connection.'
        replies = ['Your model runs locally without a cloud connection.',
                   'Your model cannot run locally.']
        for reply in replies:
            with patch.object(main, 'query_llm_with_failover', return_value=json.dumps(
                    {'scenes': [{'scene': 1, 'voiceover': reply}]})):
                with self.assertRaisesRegex(ValueError, 'meaning|scope|qualifier'):
                    main._revise_retention_copy(scenes, {1: 9}, '', 'retention-negation', 'facts-explainer')

    def test_visible_copy_cannot_strengthen_a_claim(self):
        scenes = story()
        scenes[0]['text'] = 'Your model may run locally'
        response = {'scenes': [{'scene': 0, 'voiceover': scenes[0]['voiceover'],
                               'text': 'Your model runs locally'}]}
        with patch.object(main, 'query_llm_with_failover', return_value=json.dumps(response)):
            with self.assertRaisesRegex(ValueError, 'qualifier|scope|meaning'):
                main._revise_retention_copy(scenes, {0: 12}, '', 'retention-visible', 'facts-explainer')

    def test_kokoro_identity_survives_a_repair(self):
        voices = []
        async def synth(items, session, directory, **kwargs):
            voices.append(kwargs['voice'])
            items[0]['durationInFrames'] = 150 if len(voices) == 1 else 90
            main.render_status_store.setdefault(session, {})['resolved_voice'] = 'kokoro:af_heart'
            return None, []
        response = json.dumps({'scenes': [{'scene': 0, 'voiceover': 'Writes can skip second lookups.'}]})
        with tempfile.TemporaryDirectory() as directory, patch.object(main, 'generate_voiceover_and_alignment', synth), patch.object(main, 'query_llm_with_failover', return_value=response):
            asyncio.run(main._generate_retention_voiceover(
                story(), 'retention-kokoro', directory, voice='af_heart', max_seconds=30))
        self.assertEqual(voices, ['af_heart', 'af_heart'])

    def test_impossible_reading_floor_is_rejected_before_paid_speech(self):
        scenes = story()
        scenes[1].update(type='list', listItems=['a', 'b'], durationInFrames=300)
        with tempfile.TemporaryDirectory() as directory, patch.object(main, 'generate_voiceover_and_alignment', side_effect=AssertionError('unrepairable floor reached TTS')):
            with self.assertRaisesRegex(ValueError, 'reading|visual'):
                asyncio.run(main._generate_retention_voiceover(
                    scenes, 'retention-floor', directory, max_seconds=30))


if __name__ == '__main__':
    unittest.main()

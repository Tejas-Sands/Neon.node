"""Exercise narrator selection through the real synthesis path, without network."""
import asyncio
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import main


class VoiceIdentityTests(unittest.TestCase):
    def synthesize(self, session, **kwargs):
        calls = []

        class Speech:
            def __init__(self, text, voice, **settings):
                calls.append((voice, settings))

            async def stream(self):
                yield {"type": "audio", "data": b"x" * 2048}
                yield {"type": "WordBoundary", "text": "Your", "offset": 0, "duration": 3000000}
                yield {"type": "WordBoundary", "text": "model", "offset": 3000000, "duration": 5000000}

        with tempfile.TemporaryDirectory() as directory:
            def mix(files, offsets, output):
                Path(output).write_bytes(b"test audio")

            scenes = [{"text": "Your model", "voiceover": "Your model", "durationInFrames": 150}]
            with patch("edge_tts.Communicate", Speech), patch.object(main, "mix_scene_audios", mix):
                _, words = asyncio.run(main._generate_voiceover_with_engine(
                    "edge", scenes, session, directory, **kwargs))
            self.assertEqual(words[-1]["end"], 0.8)
            self.assertEqual(scenes[0]["durationInFrames"], 90)
        return calls[0]

    def setUp(self):
        self.env = patch.dict(os.environ, {"VOICE_IDENTITY": "consistent", "VOICEOVER_VOICE": "",
                                          "VOICEOVER_PITCH": "", "VOICEOVER_RATE": "+5%"})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.style = patch.object(main, "VOICE_STYLE", "cheerful")
        self.style.start()
        self.addCleanup(self.style.stop)

    def test_different_sessions_keep_one_natural_pitch_narrator(self):
        for session in ("identity-a", "identity-b", "identity-c"):
            voice, settings = self.synthesize(session)
            self.assertEqual(voice, "en-US-JennyNeural")
            self.assertEqual(settings["pitch"], "+0Hz")
            self.assertEqual(settings["boundary"], "WordBoundary")

    def test_explicit_voice_and_pitch_win(self):
        with patch.dict(os.environ, {"VOICEOVER_VOICE": "en-US-AriaNeural", "VOICEOVER_PITCH": "+3Hz"}):
            voice, settings = self.synthesize("identity-pin", voice="en-US-GuyNeural", pitch="-2Hz")
            self.assertEqual((voice, settings["pitch"]), ("en-US-GuyNeural", "-2Hz"))
            voice, settings = self.synthesize("identity-env")
            self.assertEqual((voice, settings["pitch"]), ("en-US-AriaNeural", "+3Hz"))

    def test_rotation_escape_hatch_keeps_old_pitch_profile(self):
        with patch.dict(os.environ, {"VOICE_IDENTITY": "rotate"}):
            voice, settings = self.synthesize("identity-rotate", voice="en-US-JennyNeural")
            self.assertEqual(settings["pitch"], "+10Hz")


if __name__ == "__main__":
    unittest.main()

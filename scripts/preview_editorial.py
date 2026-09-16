"""Generate a narrated review fixture and matched voice auditions. NEVER posts.

Run from the repo root: python3 scripts/preview_editorial.py
Then: scripts/render_preview.sh public/test-editorial-preview.json out/editorial-preview.mp4
Facts: https://huggingface.co/docs/transformers/quantization/overview
"""
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from main import _generate_voiceover_with_engine  # noqa: E402


async def main():
    props = json.loads((ROOT / "tests/fixtures/story-motion.json").read_text())
    image = props["scenes"][0]["imageUrl"]
    props["scenes"] = [
        dict(type="hero", title="4-BIT WEIGHTS", text="Smaller numbers. A bigger tradeoff.",
             voiceover="Four-bit weights save space, but what's the catch for you?", imageUrl=image,
             sourceDomain="huggingface.co"),
        dict(type="metric", title="FULL PRECISION", text="32-bit", secondaryText="One weight, full precision",
             voiceover="Full precision can store each weight in thirty-two bits."),
        dict(type="split", title="32-bit weights", text="Quantization reduces precision",
             secondaryText="4-bit storage · illustrated",
             voiceover="Quantization packs weights into fewer bits — four, in this example."),
        dict(type="split", title="THE TRADEOFF", text="Smaller isn't identical",
             secondaryText="Quality depends on the task",
             voiceover="That's the tradeoff. Fewer bits can change your model's answers."),
        dict(type="split", title="THE USEFUL COMPARISON", text="Memory saved versus task quality",
             voiceover="For you, the useful comparison is memory saved versus task quality."),
    ]
    for scene in props["scenes"]:
        scene.setdefault("imageUrl", image)
        scene["durationInFrames"] = 120
    name, words = await _generate_voiceover_with_engine("edge", props["scenes"], "editorial-preview", str(ROOT / "public"),
                                                      voice="en-US-JennyNeural", rate="+5%", pitch="+0Hz")
    props.update(voiceoverUrl=name, subtitles=words)
    (ROOT / "public/test-editorial-preview.json").write_text(json.dumps(props, indent=2))
    print("Preview props: public/test-editorial-preview.json (not a scheduled post)")
    # Identical sentences, synthesis rate and final mix; only voice/pitch vary.
    sample = " ".join(s["voiceover"] for s in props["scenes"][:3])
    for label, voice, pitch in [("current-lift", "en-US-JennyNeural", "+10Hz"),
                                ("natural-jenny", "en-US-JennyNeural", "+0Hz"),
                                ("natural-aria", "en-US-AriaNeural", "+0Hz")]:
        await _generate_voiceover_with_engine("edge", [{"text": sample, "durationInFrames": 120}],
                                              "audition-" + label, str(ROOT / "public"),
                                              voice=voice, rate="+5%", pitch=pitch)


if __name__ == "__main__":
    asyncio.run(main())

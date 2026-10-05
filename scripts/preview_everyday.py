"""Create a local narrated everyday-story preview. Never calls publishing.

This September FTC advisory is an editorial example, not a fresh news pick.
python3 scripts/preview_everyday.py
bash scripts/render_preview.sh public/test-everyday-qr.json out/everyday-review/qr.mp4
"""
import asyncio
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main
from editorial_evidence import verified_excerpt

SOURCE = "https://consumer.ftc.gov/consumer-alerts/2026/09/see-qr-code-parked-somewhere-dont-scan-ityet"
EXCERPT = "Many QR readers preview the link they will send you to."
# Source-grounded paraphrases plus the one literal quotation. No invented
# amounts, loss rate, brand UI, live QR code or claims of firsthand testing.
CONTEXT = """The FTC reports scammers placing their QR stickers over legitimate parking codes.
A fraudulent destination may seek payment or personal information.
Many QR readers preview the link they will send you to.
The FTC recommends inspecting the URL for spelling errors or switched letters before clicking."""


async def run(voice):
    props = json.loads((ROOT / "tests/fixtures/story-motion.json").read_text())
    background = props["scenes"][0]["imageUrl"]
    scenes = [
        dict(type="hero", title="PARKING QR SCAMS", text="A sticker can redirect your payment",
             voiceover="Parking QR codes can hide a scam.", sourceDomain="consumer.ftc.gov"),
        dict(type="split", title="CHECK THE LINK", text=verified_excerpt(EXCERPT, CONTEXT),
             voiceover="The FTC reports fake stickers covering parking codes. Your reader may preview their destination.",
             sourceDomain="consumer.ftc.gov"),
        dict(type="comparison", title="BEFORE YOU PAY", leftLabel="THE CODE", text="Looks familiar",
             rightLabel="THE DESTINATION", secondaryText="Could be a fake site",
             voiceover="That familiar-looking code can lead to a fake site asking for payment or personal details, the FTC warns."),
        dict(type="cta", title="CHECK THE ADDRESS", text="Look for misspellings or switched letters",
             ctaText="INSPECT THE LINK",
             voiceover="Check the address for misspellings or switched letters before opening it. That's the useful check."),
    ]
    for scene in scenes:
        scene.update(imageUrl=background, durationInFrames=150)
    scenes[0]["durationInFrames"] = 110
    props["theme"].update(seed=11, primaryColor="#91f7c2", secondaryColor="#f9c65d", musicTrack="none", formatPack="facts-explainer")
    props["scenes"] = scenes
    label = "everyday-qr"
    name, words = await main._generate_retention_voiceover(
        scenes, label, str(ROOT / "public"), voice=voice,
        rate="+12%", pitch="+0Hz", source_prompt=SOURCE + "\n" + CONTEXT,
        topic_meta={"title": "Parking QR code scams", "source_excerpt": EXCERPT},
        format_pack="facts-explainer", max_seconds=30.)
    props.update(voiceoverUrl=name, subtitles=words)
    (ROOT / "public/test-everyday-qr.json").write_text(json.dumps(props, indent=2) + "\n")
    directory = ROOT / "out/everyday-review"
    directory.mkdir(parents=True, exist_ok=True)
    report = dict(source=SOURCE, source_date="2026-09-03", example_only=True,
                  timeline_seconds=sum(s["durationInFrames"] for s in scenes) / 30,
                  retention=main.render_status_store[label].get("retention"),
                  listening_review="pending", scenes=scenes)
    (directory / "qr.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "scenes"}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--voice", default="gemini:Leda")
    asyncio.run(run(parser.parse_args().voice))

"""Matched local-only voice reviews. Never generates news or posts.

python3 scripts/preview_editorial.py --auditions --pacing legacy
python3 scripts/preview_editorial.py --story scripts --rate +12% --label scripts-fast
bash scripts/render_preview.sh public/test-scripts-fast.json out/scripts-fast.mp4
"""
import argparse
import asyncio
import copy
from html import escape
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import main as renderer  # noqa: E402
from tts_providers import kokoro_python  # noqa: E402


def inspect_audio(path):
    duration = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)], text=True))
    result = subprocess.run([
        "ffmpeg", "-hide_banner", "-i", str(path), "-af",
        "silencedetect=noise=-45dB:d=0.08", "-f", "null", "-"],
        capture_output=True, text=True, check=True)
    return {"decoded_seconds": duration,
            "silence_events": re.findall(r"silence_(start|end): ([\d.]+)", result.stderr)}


def load_props(story, fixture=None):
    if fixture:
        return json.loads(Path(fixture).read_text()), str(fixture)
    props = json.loads((ROOT / "tests/fixtures/story-motion.json").read_text())
    sample = json.loads((ROOT / "tests/fixtures/voice-review.json").read_text())[story]
    image = props["scenes"][0]["imageUrl"]
    props["scenes"] = copy.deepcopy(sample["scenes"])
    for scene in props["scenes"]:
        scene.setdefault("imageUrl", image)
        scene.setdefault("durationInFrames", 120)
    props["scenes"][0]["sourceDomain"] = sample["source"].split("/")[2]
    props.pop("subtitles", None)
    return props, sample["source"]


async def audition(props, source, label, voice, rate, pitch, pacing):
    if not re.fullmatch(r"[a-z0-9-]+", label):
        raise ValueError("label must contain only lowercase letters, digits and hyphens")
    props = copy.deepcopy(props)
    directory = ROOT / "out/voice-review" / label
    directory.mkdir(parents=True, exist_ok=True)
    clips = []
    spoken_indices = [i for i, scene in enumerate(props["scenes"])
                      if (scene.get("voiceover") or scene.get("text") or "").strip()]
    original_mix = renderer.mix_scene_audios

    def inspect_mix(files, offsets, output):
        for index, (path, offset) in enumerate(zip(files, offsets)):
            destination = directory / (str(index) + Path(path).suffix)
            shutil.copyfile(path, destination)
            clips.append(dict(index=index, scene=spoken_indices[index], offset=offset, path=str(destination.relative_to(ROOT)),
                              **inspect_audio(path)))
        original_mix(files, offsets, output)

    engine = "kokoro" if voice.startswith(("af_", "am_")) else "edge"
    with patch.dict(os.environ, {"VOICE_PACING": pacing}), patch.object(renderer, "mix_scene_audios", inspect_mix):
        name, words = await renderer._generate_voiceover_with_engine(
            engine, props["scenes"], label, str(ROOT / "public"), voice=voice, rate=rate, pitch=pitch)
    props.update(voiceoverUrl=name, subtitles=words)
    output = ROOT / "public" / ("test-" + label + ".json")
    output.write_text(json.dumps(props, indent=2) + "\n")
    for clip in clips:
        scene = props["scenes"][clip["scene"]]
        start = clip["offset"]
        duration = scene["durationInFrames"] / 30
        local = [w for w in words if start <= w["start"] < start + duration]
        clip.update(scene_seconds=duration, first_word=local[0]["start"] - start if local else None,
                    last_word=local[-1]["end"] - start if local else None,
                    tail=round(start + duration - local[-1]["end"], 4) if local else None)
    status = renderer.render_status_store[label]
    report = dict(label=label, source=source, requested_voice=voice,
                  resolved_voice=status.get("resolved_voice"), provider=status.get("tts_provider"),
                  rate=rate, pitch=pitch, pacing=pacing, clips=clips,
                  per_scene=status.get("voice_scene_timings", []),
                  timeline_seconds=sum(s["durationInFrames"] for s in props["scenes"]) / 30,
                  mix=inspect_audio(ROOT / "public" / name),
                  perceptual_review="pending human listening", props=str(output.relative_to(ROOT)))
    (directory / "timing.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"REVIEW {label}: {report['timeline_seconds']:.2f}s, {output}")
    return report


def write_review_page():
    directory = ROOT / "out/voice-review"
    directory.mkdir(parents=True, exist_ok=True)
    sections = []
    for story in ("quantization", "scripts", "lockfiles"):
        if not all((directory / f"{story}-{arm}.mp4").exists() for arm in ("before", "after")):
            continue
        sections.append(f"<h2>{escape(story.title())}</h2><div class='pair'>")
        for arm, title in (("before", "Current visuals"), ("after", "Brag-inspired treatment")):
            sections.append(f"<figure><figcaption>{title}</figcaption><video controls preload='metadata' src='{story}-{arm}.mp4'></video></figure>")
        sections.append("</div>")
    if (directory / "quantization-full.mp4").exists():
        sections.append("<h2>Full-resolution candidate with existing music</h2><video class='full' controls preload='metadata' src='quantization-full.mp4'></video>")
    sections.append("<h2>Voice auditions</h2><p>Same copy, natural pitch, original scene timing. User selected Aria at +12%; final mix review remains pending.</p><div class='auditions'>")
    for name in ("control", "jenny-eight", "jenny-fast", "jenny-sixteen", "aria-fast", "guy-fast"):
        label = "quantization-legacy-" + name
        report_path = directory / label / "timing.json"
        if not report_path.exists():
            continue
        report = json.loads(report_path.read_text())
        sections.append(f"<section><h3>{escape(name)}</h3><p>{escape(report['resolved_voice'] or 'unresolved')} · {escape(report['rate'])} · {report['timeline_seconds']:.2f}s</p><audio controls preload='none' src='../../public/voiceover-{label}.mp3'></audio></section>")
    sections.append("</div>")
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Neon Node — voice and motion review</title>
<style>
body{margin:0 auto;padding:32px 20px;max-width:1100px;background:#10151b;color:#f4f1e9;font:16px/1.5 system-ui}
h1{font-size:clamp(28px,4vw,48px);line-height:1.1}h2{margin-top:48px}p{color:#b8c4ce}figure{margin:0}figcaption{margin:8px 0}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:24px}video{display:block;width:100%;max-height:620px;background:#000;border-radius:8px}
.full{max-width:420px}.auditions{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.auditions section{background:#1c252e;padding:16px;border-radius:8px}audio{width:100%}h3{margin:0}
@media(max-width:540px){.pair{grid-template-columns:1fr}}
</style><h1>Voice & motion review</h1><p>Local previews only. Each visual pair uses identical audio, words, seed and duration. The full-resolution version adds the existing music bed. No posts were published.</p>""" + "".join(sections) + "</html>"
    (directory / "index.html").write_text(page)
    print("Review page:", directory / "index.html")


async def run(args):
    if args.report:
        write_review_page()
        return
    props, source = load_props(args.story, args.fixture)
    if args.auditions:
        candidates = [("control", "en-US-JennyNeural", "+5%"),
                      ("jenny-fast", "en-US-JennyNeural", "+12%"),
                      ("aria-fast", "en-US-AriaNeural", "+12%"),
                      ("guy-fast", "en-US-GuyNeural", "+12%"),
                      ("jenny-eight", "en-US-JennyNeural", "+8%"),
                      ("jenny-sixteen", "en-US-JennyNeural", "+16%")]
        if kokoro_python():
            candidates += [("kokoro-heart", "af_heart", "+12%"), ("kokoro-bella", "af_bella", "+12%")]
        else:
            print("Kokoro unavailable: no configured side interpreter.")
        reports = []
        for label, voice, rate in candidates:
            reports.append(await audition(props, source, args.story + "-" + args.pacing + "-" + label, voice, rate, "+0Hz", args.pacing))
        (ROOT / "out/voice-review" / (args.story + "-" + args.pacing + "-auditions.json")).write_text(json.dumps(reports, indent=2) + "\n")
    else:
        await audition(props, source, args.label, args.voice, args.rate, args.pitch, args.pacing)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auditions", action="store_true")
    parser.add_argument("--report", action="store_true", help="Build a local review page from existing artifacts")
    parser.add_argument("--story", choices=["quantization", "scripts", "lockfiles"], default="quantization")
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--label", default="editorial-preview")
    parser.add_argument("--voice", default="en-US-AriaNeural")
    parser.add_argument("--rate", default="+12%")
    parser.add_argument("--pitch", default="+0Hz")
    parser.add_argument("--pacing", choices=["legacy", "tight"], default="tight")
    asyncio.run(run(parser.parse_args()))

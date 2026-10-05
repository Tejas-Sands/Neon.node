"""Local-only pacing check using existing grounded fixtures. Never posts.

python3 scripts/preview_retention.py --story lockfiles --voice gemini:Leda
"""
import argparse
import asyncio
import copy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.preview_editorial import load_props, inspect_audio
import main


async def run(args):
    props, source = load_props(args.story)
    original = copy.deepcopy(props['scenes'])
    label = 'retention-' + args.story
    source_copy = '\n'.join(s.get('voiceover', '') for s in original)
    name, words = await main._generate_retention_voiceover(
        props['scenes'], label, str(ROOT / 'public'), voice=args.voice,
        rate='+12%', pitch='+0Hz', source_prompt=source + '\n' + source_copy,
        format_pack='facts-explainer', max_seconds=30.)
    props.update(voiceoverUrl=name, subtitles=words)
    props_path = ROOT / 'public' / ('test-' + label + '.json')
    props_path.write_text(json.dumps(props, indent=2) + '\n')
    directory = ROOT / 'out' / 'retention-review'
    directory.mkdir(parents=True, exist_ok=True)
    status = main.render_status_store[label]
    report = dict(source=source, original=original, final=props['scenes'],
                  retention=status['retention'], timings=status.get('voice_scene_timings'),
                  seconds=sum(s['durationInFrames'] for s in props['scenes']) / 30,
                  audio=inspect_audio(ROOT / 'public' / name), props=str(props_path),
                  perceptual_review='pending human listening')
    (directory / (args.story + '.json')).write_text(json.dumps(report, indent=2) + '\n')
    print(f'PREVIEW: {props_path}; {report["seconds"]:.2f}s; {status["retention"]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--story', choices=['quantization', 'scripts', 'lockfiles'], default='lockfiles')
    parser.add_argument('--voice', default='gemini:Leda')
    asyncio.run(run(parser.parse_args()))

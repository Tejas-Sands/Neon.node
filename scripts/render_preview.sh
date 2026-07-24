#!/usr/bin/env bash
# Quick TEST render of the MyComp composition — never for production output.
# Half resolution + ultrafast x264 cut render time ~4x; visual identity
# (looks, prism, transitions, polish) is unchanged, just fewer pixels.
# Usage: scripts/render_preview.sh <props.json> [out.mp4]
set -euo pipefail
cd "$(dirname "$0")/.."
PROPS="${1:?usage: render_preview.sh <props.json> [out.mp4]}"
OUT="${2:-out/preview.mp4}"
npx remotion render src/remotion/index.ts MyComp "$OUT" \
  --props="$PROPS" \
  --scale=0.5 \
  --x264-preset=ultrafast \
  --overwrite
echo "preview written: $OUT"

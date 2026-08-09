#!/usr/bin/env bash
# Frame 0 IS the Instagram reel cover — the profile-grid tile and the image a
# viewer judges before the video starts. Instagram takes it implicitly (we do
# not send thumb_offset; IG_COVER_ENABLED is off by design), so nothing in the
# posting path protects it: only this check does.
#
# This bug class has shipped TWICE and was invisible in every other local check
# — the composition looked right in the player because the player starts moving
# immediately, while the still it publishes did not exist anywhere in CI:
#   2026-08-09  every reel led with a BLACK card (scene 0 entered from nothing)
#   2026-08-09  the fix left a 42%-opacity title, 30px low, behind two colour
#               flashes at peak, plus iris corner-clipping and residual blur
#
# What is asserted (deliberately NOT mean luma — a dark-aesthetic cover is
# legitimate, and the old flash-washed frame scored BRIGHTER than the good one,
# so a brightness band both passes bad frames and fails good ones):
#   edge  — a black or flat-washed card has almost no edge energy
#   sd    — a near-uniform frame has almost no contrast
#   corner— iris-open / clip-path transitions blank the corners mid-enter
#
# Usage: scripts/check-cover-frame.sh [props.json] [seed ...]
set -euo pipefail
cd "$(dirname "$0")/.."

PROPS="${1:-public/props-force-post-6533.json}"
shift || true
SEEDS=("$@")
if [ ${#SEEDS[@]} -eq 0 ]; then
  # Six unrelated seeds exercise different look families, media framings and
  # transition anchors — one seed only ever proves one code path.
  SEEDS=(11 2024 777001 31337 90210 5150)
fi

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

echo "Cover-frame check — $PROPS, ${#SEEDS[@]} seeds"
for s in "${SEEDS[@]}"; do
  python3 -c "
import json, sys
d = json.load(open(sys.argv[1]))
d.setdefault('theme', {})['seed'] = int(sys.argv[3])
json.dump(d, open(sys.argv[2], 'w'))
" "$PROPS" "$WORK/props-$s.json" "$s"
  npx remotion still src/remotion/index.ts MyComp "$WORK/f-$s.png" \
    --props="$WORK/props-$s.json" --frame=0 --scale=0.4 >/dev/null 2>&1
done

python3 -W ignore - "$WORK" "${SEEDS[@]}" <<'PY'
import math, sys
try:
    from PIL import Image, ImageFilter
except ImportError:
    print("SKIP — Pillow not installed (pip install pillow to enable)")
    sys.exit(0)

work, seeds = sys.argv[1], sys.argv[2:]
MIN_EDGE, MIN_SD, MIN_CORNER = 1.0, 8.0, 3.0
fails = []
print(f"{'seed':>8}{'luma':>7}{'sd':>7}{'edge':>7}{'corner':>8}  verdict")
for s in seeds:
    im = Image.open(f"{work}/f-{s}.png").convert("L")
    px = list(im.getdata())
    n = len(px)
    mean = sum(px) / n
    sd = math.sqrt(sum((q - mean) ** 2 for q in px) / n)
    edge = sum(im.filter(ImageFilter.FIND_EDGES).getdata()) / n
    w, h = im.size
    corner = min(sum(im.crop((x, y, x + 50, y + 50)).getdata()) / 2500
                 for (x, y) in ((0, 0), (w - 50, 0), (0, h - 50), (w - 50, h - 50)))
    bad = []
    if edge < MIN_EDGE:
        bad.append(f"edge {edge:.2f}<{MIN_EDGE} (blank/flat cover)")
    if sd < MIN_SD:
        bad.append(f"sd {sd:.1f}<{MIN_SD} (near-uniform cover)")
    if corner < MIN_CORNER:
        bad.append(f"corner {corner:.1f}<{MIN_CORNER} (clipped by a transition)")
    print(f"{s:>8}{mean:>7.1f}{sd:>7.1f}{edge:>7.2f}{corner:>8.1f}  "
          f"{'OK' if not bad else 'FAIL — ' + '; '.join(bad)}")
    if bad:
        fails.append(s)
print()
if fails:
    print(f"FAILED: {len(fails)} cover frame(s): {', '.join(map(str, fails))}")
    sys.exit(1)
print("check-cover-frame: ALL PASS")
PY

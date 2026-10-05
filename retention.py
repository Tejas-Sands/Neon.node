"""Opening and scene budgets checked against the final, audio-fitted timeline."""
import math
import re
from collections import Counter


class RetentionError(ValueError):
    """A bounded repair could not produce a compliant narration."""


def preserves_claim(original, rewritten):
    """Conservative compression guard, not a semantic fact checker.

    Word overlap alone accepts reversed claims. Preserve polarity, modality,
    quantities, units and scope/attribution clauses; reject uncertain rewrites.
    """
    def normalize(text):
        text = text.lower().replace('’', "'").replace('−', '-')
        text = re.sub(r"\bcannot\b|\b\w+n't\b", 'not', text)
        return ' '.join(text.split())
    original, rewritten = normalize(original), normalize(rewritten)
    patterns = (
        r'\b(?:not|never|no|without|unless|only|if|may|might|could|can|must|should|'
        r'reported|reportedly|claims|claimed|according)\b',
        r'(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:\s*(?:%|ms|ns|gb|mb|tb|kb|seconds?|milliseconds?|bits?|bytes?|tokens?))?',
        r'\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|'
        r'thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|'
        r'forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion|'
        r'trillion|once|twice|percent|bits?|bytes?|seconds?|milliseconds?|nanoseconds?|dollars?)\b',
        r'\b(?:only|unless|without|if|when|except|according to|per the)\b[^.!?;]*',
    )
    return all(Counter(re.findall(pattern, original)) == Counter(re.findall(pattern, rewritten))
               for pattern in patterns)


def repair_targets(scenes, *, measured=False, max_seconds=None):
    """Scene index -> shorter narration word budget; never alter audio or frames.

    Reading holds count too: a four-second utterance in a six-second opening
    still delays the next scene. Format totals include silent countdowns.
    The separately appended legacy outro is outside its content runtime band.
    """
    targets = {}
    if not scenes:
        raise RetentionError('retention: missing scenes')
    hook = scenes[0]
    if any(len(str(hook.get(field) or '').split()) > limit
           for field, limit in (('voiceover', 12), ('title', 4), ('text', 8))):
        targets[0] = 8
    if not measured:
        return targets
    total = sum(s.get('durationInFrames', 0) for s in scenes if s.get('type') != 'outro') / 30
    ratio = min(1., max_seconds / total) if max_seconds and total else 1.
    for index, scene in enumerate(scenes):
        seconds = scene.get('durationInFrames', 0) / 30
        if not math.isfinite(seconds) or seconds <= 0:
            raise RetentionError('retention: invalid measured scene duration')
        limit = 4. if index == 0 else 250 / 30
        over_scene = seconds > limit
        over_total = ratio < 1 and scene.get('type') != 'outro' and bool(
            str(scene.get('voiceover') or scene.get('text') or '').strip())
        if not over_scene and not over_total:
            continue
        words = len(str(scene.get('voiceover') or scene.get('text') or '').split())
        # Leave breathing/reading headroom. This is a rewrite target, never an
        # estimate masquerading as measured audio or an instruction to truncate.
        target_seconds = min(limit, seconds * ratio)
        budget = max(1, min(words - 1, math.floor(words * target_seconds / seconds * .85)))
        targets[index] = min(targets.get(index, budget), budget)
    return targets

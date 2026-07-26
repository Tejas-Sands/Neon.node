// ============================================================================
// fitStack.ts — vertical budget for stacked text blocks
// ----------------------------------------------------------------------------
// The hero stack is an absolutely-positioned flex column anchored at `heroTop%`
// with NO height bound, holding title + accent rule + body + subtitle. The
// caption band is pinned at `bottom: 24%` (zIndex 40, so it always paints over).
// Nothing related the two, so a scene with four populated blocks — or simply a
// long title that wraps to three lines — grew down into the caption and had its
// last line covered. Observed in a real render: "REAL-TIME DATA, NO POLLING"
// half-hidden behind the subtitle plate.
//
// This solves the one number that prevents it: a uniform scale applied to the
// stack's type so the whole column fits the space above the caption. Uniform,
// not per-slot, because shrinking only the offender inverts the type hierarchy —
// a subtitle should never end up larger than the title that owns it.
//
// WHY IT IS ESTIMATED, NOT MEASURED. Remotion renders frames in parallel worker
// processes; there is no layout pass to query, and measuring in one worker would
// not be deterministic across the others. So line counts are predicted with the
// same width model AnimatedText already uses for its longest-word auto-fit
// (~0.68em per character), which keeps the two in agreement.
//
// Pure function of its inputs — no RNG, no seed stream, no draw-order risk.
// ============================================================================

/** Per-character advance as a fraction of font size. Matches AnimatedText's
 *  auto-fit constant, so both agree about how wide a string renders. */
const CHAR_ADVANCE_EM = 0.68;

export interface StackSlot {
  /** The string that will render. Empty/absent slots should be omitted. */
  text: string;
  /** Requested size in px BEFORE the look's fontScale is applied. */
  basePx: number;
}

export interface FitStackInput {
  slots: StackSlot[];
  /** The look's fontScale — applied on top of basePx by AnimatedText. */
  fontScale: number;
  /** Vertical space the column may occupy, in px. */
  availablePx: number;
  /** Horizontal space available for wrapping, in px. */
  widthPx: number;
  /** Per-family line height from FONT_METRICS. */
  lineHeight: number;
  /** Flex gap between slots, in px. */
  gapPx: number;
  /** Fixed-height furniture inside the column (e.g. the 3px accent rule). */
  fixedPx?: number;
  /**
   * Vertical padding each block adds. AnimatedText's baseStyle carries
   * `padding: "12px 24px"`, so every slot is 24px taller than its text — three
   * slots is 72px, which is most of a wrapped line and cannot be ignored.
   */
  slotPaddingPx?: number;
  /** AnimatedText clamps to 28px; scaling below it achieves nothing. */
  minPx?: number;
}

/** Predicted rendered height of one slot at a given size. */
const slotHeight = (text: string, px: number, widthPx: number, lineHeight: number): number => {
  const perLine = Math.max(1, Math.floor(widthPx / (px * CHAR_ADVANCE_EM)));
  const lines = Math.max(1, Math.ceil(text.trim().length / perLine));
  return lines * px * lineHeight;
};

/**
 * Text width actually available inside a block, given the column width.
 * AnimatedText's baseStyle caps the block at `maxWidth: 90%` and then insets it
 * by 24px of horizontal padding on each side, so the string wraps well before
 * the column edge. Using the raw column width here predicted one line where the
 * renderer produced two — which is exactly how the collision slipped through.
 */
export const textWidthFor = (columnPx: number): number =>
  Math.max(80, columnPx * 0.9 - 48);

/**
 * Correction applied to the predicted height, MEASURED against a real render.
 *
 * The analytical model consistently under-predicts, because it cannot resolve
 * the actual CSS layout: `maxWidth: 90%` resolves against a flex line whose
 * width depends on content, plate padding is inside that, and uppercase display
 * type advances wider than the 0.68em average. In the reference render both the
 * body and subtitle blocks wrapped to two lines where the model predicted one.
 *
 * Ground truth from that render: heroTop 52%, stack bottom ~71% => ~365px
 * actual against 251px predicted, a ratio of 1.45.
 *
 * Erring HIGH is the safe direction: over-predicting costs a few percent of
 * type size, under-predicting puts a line back under the caption — which is the
 * bug this exists to prevent. Re-measure if AnimatedText's baseStyle padding,
 * maxWidth or tracking change.
 */
const HEIGHT_CORRECTION = 1.45;

/** Predicted height of the whole column at a trial scale. */
export function stackHeightAt(input: FitStackInput, scale: number): number {
  const { slots, fontScale, widthPx, lineHeight, gapPx, fixedPx = 0 } = input;
  const pad = input.slotPaddingPx ?? 0;
  let total = fixedPx;
  for (const s of slots) {
    total += slotHeight(s.text, s.basePx * fontScale * scale, widthPx, lineHeight) + pad;
  }
  const gaps = Math.max(0, slots.length - 1 + (fixedPx > 0 ? 1 : 0));
  return (total + gaps * gapPx) * HEIGHT_CORRECTION;
}

/**
 * Largest scale in (0, 1] whose predicted column height fits `availablePx`.
 *
 * Binary search rather than division: height is a STEP function of scale,
 * because shrinking type can drop a whole wrapped line at once. Dividing
 * available by predicted would overshoot every one of those steps.
 *
 * Returns 1 when the stack already fits — the common case, so most scenes are
 * completely unaffected by this.
 */
export function fitStackScale(input: FitStackInput): number {
  const { slots, fontScale, availablePx, minPx = 28 } = input;
  if (!slots.length || availablePx <= 0) return 1;
  if (stackHeightAt(input, 1) <= availablePx) return 1;

  // Never scale below AnimatedText's own floor — past it the text stops
  // shrinking and the result would silently overflow anyway.
  const largestBase = Math.max(...slots.map((s) => s.basePx * fontScale));
  const floor = Math.min(1, minPx / Math.max(1, largestBase));

  let lo = floor;
  let hi = 1;
  for (let i = 0; i < 16; i++) {
    const mid = (lo + hi) / 2;
    if (stackHeightAt(input, mid) <= availablePx) lo = mid;
    else hi = mid;
  }
  return lo;
}

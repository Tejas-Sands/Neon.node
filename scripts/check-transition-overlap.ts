import assert from 'node:assert/strict';
import {transitionOverlapFrames} from '../src/remotion/MyComp/transitions';

assert.equal(transitionOverlapFrames('crossfade', 120, 150), 10);
assert.equal(transitionOverlapFrames('push-up', 120, 150), 10);
assert.equal(transitionOverlapFrames('none', 120, 150), 0);
assert.equal(transitionOverlapFrames('punch-in', 120, 150), 0);
assert.equal(transitionOverlapFrames('crossfade', 120, 150, 'quiz-reveal'), 0);
assert.equal(transitionOverlapFrames('crossfade', 120, 150, 'data-rankings'), 0);
assert.equal(transitionOverlapFrames('crossfade', 9, 150), 3);
// Extending the outgoing visual and offsetting the next sequence by the same
// amount must preserve every narration boundary and the total composition.
const durations = [120, 150, 90];
const overlap = [0, 10, 10, 0];
let cursor = 0;
const starts: number[] = [];
durations.forEach((duration, i) => {
  cursor -= overlap[i]; starts.push(cursor);
  cursor += duration + overlap[i + 1];
});
assert.deepEqual(starts, [0, 120, 270]);
assert.equal(cursor, 360);
console.log('Transition overlap: PASS');

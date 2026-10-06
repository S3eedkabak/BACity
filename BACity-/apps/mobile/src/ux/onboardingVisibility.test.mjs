import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
test('onboarding scrim uses explicit full-height coordinates and preserves footage above copy', () => {
  const source = readFileSync(new URL('../../app/welcome.tsx', import.meta.url), 'utf8');
  assert.match(source, /y2="100%"/);
  const stops = [...source.matchAll(/<Stop offset="([\d.]+)" stopColor="[^"]+" stopOpacity="([\d.]+)"/g)].map(x => [Number(x[1]), Number(x[2])]);
  assert.equal(stops.length, 7);
  assert.ok(stops.filter(x => x[0] <= .45).every(x => x[1] <= .12));
  assert.ok(stops.find(x => x[0] === .9)[1] >= .9);
  assert.deepEqual(stops.at(-1), [1, 1]);
  const video = readFileSync(new URL('../components/OnboardingVideo.tsx', import.meta.url), 'utf8');
  assert.match(video, /ResizeMode.COVER/);
  assert.match(video, /useNativeControls=\{false\}/);
  assert.doesNotMatch(video, /borderRadius|brightness|contrast|filter:/);
});

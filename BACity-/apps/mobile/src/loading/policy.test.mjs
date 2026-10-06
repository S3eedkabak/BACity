import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { LoadingPresentation, developmentDelay } from './policy.ts';
import { createNavigationGuard } from './navigation.ts';
import { loadingRegistry, walkAsset } from './registry.ts';
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
function fixture() {
  let now = 0, next = 0; const timers = new Map(); const events = [];
  const clock = { now: () => now, set: (callback, ms) => { const id = ++next; timers.set(id, { callback, at: now + ms }); return id; }, clear: id => timers.delete(id) };
  const advance = ms => { const end = now + ms; while (true) { const due = [...timers].filter(([, t]) => t.at <= end).sort((a, b) => a[1].at - b[1].at)[0]; if (!due) break; now = due[1].at; timers.delete(due[0]); due[1].callback(); } now = end; };
  const controller = new LoadingPresentation(() => events.push('show'), () => events.push('exit'), () => events.push('hide'), clock);
  return { events, advance, controller, timers };
}
test('fast/cache-ready operation never shows or waits for a loader', () => {
  const f = fixture(); f.controller.start(); f.advance(499); f.controller.complete(); f.advance(5000); assert.deepEqual(f.events, []); assert.equal(f.timers.size, 0);
});
test('500ms grace, medium/long waits and short bounded completion exit', () => {
  for (const wait of [500, 1500, 3000]) {
    const f = fixture(); f.controller.start(); f.advance(wait); assert.deepEqual(f.events, ['show']);
    f.controller.complete(); f.advance(380); assert.deepEqual(f.events, ['show', 'exit', 'hide']); assert.equal(f.timers.size, 0);
  }
});
test('request failure stops presentation like successful completion', () => {
  const f = fixture(); f.controller.start(); f.advance(3000); f.controller.complete(); f.controller.complete(); f.advance(180); assert.deepEqual(f.events, ['show', 'exit', 'hide']);
});
test('cancel/unmount/background clears all timers and cannot show later', () => {
  for (const wait of [100, 700]) { const f = fixture(); f.controller.start(); f.advance(wait); f.controller.dispose(); const before = [...f.events]; f.advance(5000); f.controller.complete(); assert.deepEqual(f.events, before); assert.equal(f.timers.size, 0); }
});
test('replacement during exit cannot complete a new loading session', () => {
  const old = fixture(); old.controller.start(); old.advance(500); old.controller.complete(); old.controller.dispose(); old.advance(500); assert.deepEqual(old.events, ['show']);
  const fresh = fixture(); fresh.controller.start(); fresh.advance(500); assert.deepEqual(fresh.events, ['show']);
});
test('rapid route taps are guarded and returning to origin resets guard', () => {
  const guard = createNavigationGuard(); assert.equal(guard.allow(1), true); assert.equal(guard.allow(100), false); guard.reset(); assert.equal(guard.allow(101), true); assert.equal(guard.allow(802), true);
});
test('latency simulation explicitly opts in and is disabled in production', () => {
  for (const value of ['500', '1500', '3000']) { assert.equal(developmentDelay(true, value), Number(value)); assert.equal(developmentDelay(false, value), 0); }
  for (const value of [undefined, '', '99999', 'invalid']) assert.equal(developmentDelay(true, value), 0);
});
test('registry uses only real looping timelines, never button timelines', () => {
  assert.equal(walkAsset.artboard, 'New Artboard');
  assert.deepEqual(walkAsset.stateMachines, [{ name: 'State Machine 1', inputs: [{ name: 'level', type: 'number' }] }]);
  for (const context of Object.values(loadingRegistry)) assert.ok(walkAsset.cycles.includes(context.animation));
  assert.equal(new Set(Object.values(loadingRegistry).map(value => value.animation)).size, 3);
});
test('runtime fallback, local WASM and background disposal are explicit', () => {
  const provider = read('../components/loading/LoadingExperience.tsx');
  assert.match(provider, /failed \|\| reduced/); assert.match(provider, /presentation.current\?\.dispose\(\)/);
  assert.equal((provider.match(/<RiveCharacter /g) || []).length, 1);
  assert.match(provider, /focused/); assert.match(provider, /listener.remove/);
  assert.match(read('../components/loading/RiveCharacter.web.tsx'), /player.cleanup/);
  assert.match(read('../components/loading/RiveCharacter.web.tsx'), /setWasmFallbackUrl\(null\)/);
  assert.match(read('../components/loading/RiveCharacter.tsx'), /getViewManagerConfig/);
});
test('real browser timers keep their global receiver', () => {
  assert.match(read('./policy.ts'), /set: \(callback, ms\) => setTimeout\(callback, ms\)/);
  assert.match(read('./policy.ts'), /clear: timer => clearTimeout\(timer\)/);
});
test('full-bleed onboarding video loops, pauses offscreen/background and falls back safely', () => {
  const source = read('../components/OnboardingVideo.tsx');
  assert.match(source, /focused && active/); assert.match(source, /useNativeControls=\{false\}/);
  assert.match(source, /isLooping/); assert.match(source, /isMuted/); assert.match(source, /ResizeMode.COVER/);
  assert.match(source, /StyleSheet\.absoluteFillObject/); assert.doesNotMatch(source, /borderRadius/);
  assert.match(source, /bratislava-poster.jpg/); assert.match(source, /setFailed\(true\)/); assert.match(source, /!failed && !reduced/);
});
test('only missing-data foreground loading integrates; cached refresh remains visible', () => {
  assert.match(read('../../app/event/[id].tsx'), /isLoading && !event/);
  assert.doesNotMatch(read('../../app/event/[id].tsx'), /if \(isError \|\| !event\)/);
  assert.match(read('../../app/(tabs)/saved.tsx'), /isLoading && !data/);
  assert.match(read('../../app/(tabs)/explore.tsx'), /!initialFinished.current/);
  assert.doesNotMatch(read('../../app/(tabs)/map.tsx'), /useMeaningfulLoading/);
});
test('central Rive system owns major Map, Plus and generation transitions', () => {
  const provider = read('../components/loading/LoadingExperience.tsx');
  assert.match(provider, /beginMajor/); assert.match(provider, /finishMajor/); assert.match(provider, /useBrandedLoading/);
  assert.match(read('../../app/(tabs)/_layout.tsx'), /major\.begin\('map'\)/);
  assert.match(read('../../app/(tabs)/map.tsx'), /onDidFinishRenderingFrameFully/);
  assert.match(read('../../app/evening-plan.tsx'), /useBrandedLoading\('plan-generation', generation\.isPending\)/);
  assert.match(read('../../app/weekend-plan.tsx'), /useBrandedLoading\('weekend-generation', generation\.isPending\)/);
});

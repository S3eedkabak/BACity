import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

function nativeOffsetParser() {
  // Exercise the INSTALLED native extraction implementation, rather than
  // Number(), which silently accepted the invalid leading-dot offsets on web.
  const source = readFileSync(new URL('../../node_modules/react-native-svg/src/lib/extract/extractGradient.ts', import.meta.url), 'utf8');
  const body = source.slice(source.indexOf('const percentReg'), source.indexOf('const offsetComparator')) + '\nexport { percentToFloat };';
  const compiled = ts.transpileModule(body, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const exports = {};
  const warnings = [];
  new Function('exports', 'console', compiled)(exports, { warn: message => warnings.push(message) });
  return { parse: exports.percentToFloat, warnings };
}

test('all onboarding stops survive the native SVG parser without collapsing to the top', () => {
  const { parse, warnings } = nativeOffsetParser();
  const source = readFileSync(new URL('../../app/welcome.tsx', import.meta.url), 'utf8');
  const offsets = [...source.matchAll(/<Stop offset="([^"]+)"/g)].map(x => x[1]);
  assert.deepEqual(offsets.map(parse), [0, .2, .45, .6, .75, .9, 1]);
  assert.deepEqual(warnings, []);
  // Prove this catches the actual regression, not just formatting changes.
  assert.equal(parse('.90'), 0);
  assert.equal(warnings.length, 1);
});
test('onboarding scrim uses explicit full-height coordinates and preserves footage above copy', () => {
  const source = readFileSync(new URL('../../app/welcome.tsx', import.meta.url), 'utf8');
  assert.match(source, /y2="100%"/);
  const stops = [...source.matchAll(/<Stop offset="([\d.]+)%" stopColor="[^"]+" stopOpacity="([\d.]+)"/g)].map(x => [Number(x[1]) / 100, Number(x[2])]);
  assert.equal(stops.length, 7);
  assert.ok(stops.filter(x => x[0] <= .45).every(x => x[1] <= .12));
  assert.ok(stops.find(x => x[0] === .9)[1] >= .9);
  assert.deepEqual(stops.at(-1), [1, 1]);
  const video = readFileSync(new URL('../components/OnboardingVideo.tsx', import.meta.url), 'utf8');
  assert.match(video, /ResizeMode.COVER/);
  assert.match(video, /useNativeControls=\{false\}/);
  assert.doesNotMatch(video, /borderRadius|brightness|contrast|filter:/);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { createSessionGreeting } from './session.ts';
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
test('guests and unresolved auth never claim a welcome', () => {
  const session = createSessionGreeting();
  assert.equal(session.claim(null, false, 'returning', 0), null);
  assert.equal(session.claim('a', true, 'returning', 0), null);
  assert.equal(session.claim('a', false, 'returning', 100).deadline, 2300);
});
test('StrictMode/remount retains the original greeting and deadline', () => {
  const session = createSessionGreeting();
  const first = session.claim('a', false, 'new', 0);
  assert.strictEqual(session.claim('a', false, 'returning', 200), first);
  assert.equal(first.kind, 'new');
  session.finish('a');
  for (let i = 0; i < 10; i++) assert.equal(session.claim('a', false, 'returning', 300), null);
});
test('background, logout and another login cannot replay a claimed welcome', () => {
  const session = createSessionGreeting();
  session.claim('a', false, 'returning', 0);
  session.finish('a');
  assert.equal(session.claim(null, false, 'returning', 100), null);
  assert.equal(session.claim('b', false, 'new', 200), null);
  assert.equal(createSessionGreeting().claim('a', false, 'returning', 300).kind, 'returning');
});
test('obsolete owner and elapsed deadline finish instead of replaying', () => {
  const session = createSessionGreeting();
  session.claim('a', false, 'new', 0);
  session.finish('stale');
  assert.ok(session.claim('a', false, 'new', 100));
  assert.equal(session.claim('b', false, 'returning', 150), null);
  assert.equal(session.claim('a', false, 'new', 200), null);
  const timed = createSessionGreeting();
  timed.claim('a', false, 'new', 0);
  assert.equal(timed.claim('a', false, 'new', 2200), null);
});
test('logout during the greeting cannot resume it on immediate login', () => {
  const session = createSessionGreeting();
  session.claim('a', false, 'returning', 0);
  assert.equal(session.claim(null, false, 'returning', 100), null);
  assert.equal(session.claim('a', false, 'returning', 200), null);
});
test('greeting fallback is separate from startup and always releases Home', () => {
  const root = read('../../app/_layout.tsx');
  assert.equal((root.match(/<SessionWelcome /g) || []).length, 1);
  assert.ok(root.indexOf('</QueryClientProvider>') < root.indexOf('<SessionWelcome'));
  const overlay = read('../components/greeting/SessionWelcome.tsx');
  for (const value of ['greeting.deadline - Date.now()', 'clearTimeout(deadline)', 'listener.remove()', 'withTiming', "state !== 'active'"]) assert.ok(overlay.includes(value));
  assert.doesNotMatch(overlay, /router\.|AsyncStorage|ActivityIndicator|Video/);
  assert.doesNotMatch(overlay, /GreetingCharacter|\.riv|borderRadius/);
  for (const platform of ['tsx', 'web.tsx']) assert.ok(!existsSync(new URL(`../components/greeting/GreetingCharacter.${platform}`, import.meta.url)));
  assert.doesNotMatch(read('../components/loading/RiveCharacter.tsx'), /greeting/);
  for (const route of ['auth', 'oauth']) assert.doesNotMatch(read(`../../app/${route}.tsx`), /router.replace\("\/\(tabs\)\/discover"\)/);
});

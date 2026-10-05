import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { entryPlayback, visibleWait, substantialWait } from './motionPolicy.ts';
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');

test('inbox and library retain loaded content on refresh failure and expose recovery', () => {
  const inbox = read('../../app/messages/index.tsx');
  assert.match(inbox, /error && !rows.length/);
  assert.match(inbox, /conversations.forEach/);
  assert.match(inbox, /onRefresh=\{retry\}/);
  assert.match(inbox, /toLocaleTimeString/);
  const library = read('../../app/collections.tsx');
  assert.match(library, /query.isError && !query.data/);
  assert.match(library, /Couldn't refresh. Tap to retry/);
});

test('entry waits for accessibility preference, pauses in background, and fails safely', () => {
  assert.equal(entryPlayback(null, false, true), 'hold');
  assert.equal(entryPlayback(false, false, true), 'video');
  assert.equal(entryPlayback(true, false, true), 'static');
  assert.equal(entryPlayback(false, true, true), 'static');
  assert.equal(entryPlayback(false, false, false), 'hold');
});
test('real wait dismisses immediately on completion, entry, or user dismissal', () => {
  assert.equal(visibleWait(true, true, false, false), true);
  for (const values of [[false,true,false,false],[true,false,false,false],[true,true,true,false],[true,true,false,true]]) assert.equal(visibleWait(...values), false);
});
test('cached content and entitlement failure never request a substantial loader', () => {
  assert.equal(substantialWait(true, true, false), true);
  assert.equal(substantialWait(true, true, true), false);
  assert.equal(substantialWait(false, true, false), false);
  assert.equal(substantialWait(true, false, false), false);
});
test('single centralized player uses supplied bundled media, no loop or audio', () => {
  const source = read('../components/BACityMotion.tsx');
  assert.equal((source.match(/<Video /g) || []).length, 1);
  assert.match(source, /isMuted volume=\{0\} isLooping=\{false\}/);
  assert.match(source, /didJustFinish/);
  assert.match(source, /unloadAsync/);
  assert.match(source, /15_000/);
  assert.doesNotMatch(source, /router\.(push|replace)/);
  for (const name of ['squiggle-flow', 'car-racing']) assert.ok(existsSync(new URL(`../../assets/motion/${name}.mp4`, import.meta.url)));
});
test('session cache changes before descendants mount, initial query is not cleared on mount', () => {
  const source = read('../../app/_layout.tsx');
  assert.match(source, /useMemo\(\(\) => new QueryClient/);
  assert.match(source, /key=\{userId \|\| 'guest'\}/);
  assert.match(source, /return \(\) => queryClient.clear\(\)/);
  assert.doesNotMatch(source, /setTimeout/);
});
test('Home retains hero, personalized feed, location and premium routes', () => {
  const source = read('../../app/(tabs)/discover.tsx');
  for (const name of ['FeaturedEvent', 'excludeFeaturedEvent', 'useRecommendations', 'LocationPreference', 'TonightEntry', 'EveningPlanEntry', 'WeekendPlanEntry', 'GroupsEntry', 'AreaWatchEntry']) assert.ok(source.includes(name));
  assert.ok(source.indexOf('<FeaturedEvent') < source.indexOf('<SectionHeader title="Compose your city"'));
  assert.doesNotMatch(source, /if \(fallback.isLoading\) return/);
});
test('media failures use local vector fallback; no arbitrary web stock imagery', () => {
  const source = read('../components/EventMedia.tsx');
  assert.match(source, /onError=\{\(\) => setFailed\(true\)\}/);
  assert.match(source, /onLoad=\{\(\) => setLoaded\(true\)\}/);
  assert.match(source, /<Svg/);
  assert.doesNotMatch(source + read('../components/EventCard.tsx'), /unsplash|pexels|https:\/\//i);
});
test('contribution steps keep structured fields, review and verified-account requirement', () => {
  const source = read('../../app/(tabs)/contribute.tsx');
  for (const value of ['step === 0','step === 1','step === 2','public_source_url','image_url','ticket_url','wheelchair_accessible','email_verified','Submit for review']) assert.ok(source.includes(value));
});
test('planner screens retain fail-closed gates, real generation and event detail', () => {
  for (const name of ['evening-plan','weekend-plan','event-chains','tonight']) {
    const source = read(`../../app/${name}.tsx`);
    assert.ok(source.includes('usePlusGate'));
    assert.ok(source.includes('plusPaywallRoute'));
    assert.ok(source.includes('useBACityWaiting'));
    assert.ok(source.includes('PremiumIntro'));
  }
  assert.match(read('../components/PremiumUI.tsx'), /router.push\('\/event\/' \+ event.id\)/);
});
test('group participants are not accidentally paywalled by presentation', () => {
  const source = read('../../app/group/[id].tsx');
  assert.ok(source.includes('groupsApi.vote'));
  assert.ok(source.includes('groupsApi.preferences'));
  assert.ok(source.includes('group.role === "host"'));
  assert.ok(source.includes('<PlusGateAction feature="group_match"'));
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { entryDestination } from './motionPolicy.ts';
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');

test('completed sign-in entry goes to Home from auth, detail, map and restored routes', () => {
  for (const pathname of ['/auth', '/oauth', '/event/abc', '/map', '/profile']) {
    assert.equal(entryDestination('account-a', 'account-a', pathname), 'home');
  }
  assert.equal(entryDestination('account-a', 'account-a', '/discover'), 'complete');
  assert.equal(entryDestination('account-a', 'account-a', '/(tabs)/discover'), 'complete');
});

test('stale entry completion after logout or account switch cannot navigate', () => {
  for (const currentOwner of [null, 'account-b']) assert.equal(entryDestination('account-a', currentOwner, '/auth'), 'ignore');
  assert.equal(entryDestination(null, 'account-a', '/discover'), 'ignore');
});

test('entry route is acknowledged before releasing overlay; callback remains stable', () => {
  const source = read('../../app/_layout.tsx');
  assert.match(source, /const finishEntry = useCallback/);
  assert.match(source, /if \(!navigation\?\.key \|\| completedOwner === userId\) return/);
  assert.match(source, /destination === 'home'\) router.replace\('\/\(tabs\)\/discover'\)/);
  assert.match(source, /destination === 'complete'\) setCompletedOwner\(finishedOwner\)/);
  assert.match(source, /useAuthStore.getState\(\).user\?\.id === userId/);
});

test('startup uses central loading without mandatory intro or video playback', () => {
  const source = read('../components/StartupScene.tsx');
  assert.match(source, /useStartupLoading/);
  assert.match(source, /startupTimeout/);
  assert.doesNotMatch(source, /expo-av|Video|\.mp4|router\.(push|replace)/);
  assert.ok(!existsSync(new URL('../components/BACityMotion.tsx', import.meta.url)));
});

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

test('fast startup has no artificial intro delay', () => {
  assert.doesNotMatch(read('../components/StartupScene.tsx'), /tokens.motion.intro|INTRO_DONE/);
});
test('slow startup presentation depends on actual readiness', () => {
  assert.match(read('../components/StartupScene.tsx'), /useStartupLoading\(!ready && !failed\)/);
});
test('startup timeout stops animation and offers retry without changing auth', () => {
  const source = read('../components/StartupScene.tsx');
  assert.match(source, /setFailed\(true\)/);
  assert.match(source, /clearTimeout\(timer\)/);
  assert.match(source, /onRetry\(\)/);
});
test('cold startup survives session cache remount and is not replayed on login', () => {
  const source = read('../../app/_layout.tsx');
  assert.equal((source.match(/<StartupScene /g) || []).length, 1);
  assert.ok(source.indexOf('</QueryClientProvider>') < source.indexOf('<StartupScene'));
  assert.match(source, /if \(userId\) finishEntry\(\)/);
  assert.doesNotMatch(source, /prepareEntryFilm|BACityLoadingProvider|BACityEntrySequence/);
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
    assert.ok(!source.includes('useBACityWaiting'));
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

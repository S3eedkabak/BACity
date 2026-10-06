import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { colors } from '../theme/colors.ts';
const read = path => readFileSync(new URL(path, import.meta.url), 'utf8');
const luminance = hex => {
  const rgb = hex.slice(1).match(/../g).map(x => parseInt(x, 16) / 255).map(x => x <= .04045 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4);
  return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
};
const contrast = (a, b) => (Math.max(luminance(a), luminance(b)) + .05) / (Math.min(luminance(a), luminance(b)) + .05);

test('dark semantic text/action/status pairs meet normal-text contrast', () => {
  for (const [a, b] of [[colors.text, colors.background], [colors.textMuted, colors.surfaceAlt], [colors.primaryDark, colors.primarySoft], [colors.white, colors.primary], [colors.danger, colors.dangerSurface], [colors.free, colors.successSurface]]) {
    assert.ok(contrast(a, b) >= 4.5, `${a} on ${b}: ${contrast(a, b)}`);
  }
});
test('all application UI icons use the central Iconoir adapter', () => {
  const inspect = dir => {
    for (const entry of readdirSync(new URL(dir, import.meta.url), { withFileTypes: true })) {
      const path = `${dir}/${entry.name}`;
      if (entry.isDirectory()) inspect(path);
      else if (entry.name.endsWith('.tsx')) assert.doesNotMatch(read(path), /@expo\/vector-icons|Ionicons|FontAwesome|MaterialIcons|Feather/);
    }
  };
  inspect('../../app'); inspect('../components');
  assert.match(read('../components/AppIcon.tsx'), /from 'iconoir-react-native\/regular\//);
});
test('Iconoir workaround resolves its real export without changing other package resolution', () => {
  const source = read('../../metro.config.js');
  assert.match(source, /moduleName === 'iconoir-react-native'/);
  assert.match(source, /context.resolveRequest\(context, moduleName, platform\)/);
  assert.ok(existsSync(new URL('../../node_modules/iconoir-react-native/dist/index.js', import.meta.url)));
});
test('onboarding video and real Rive loading have separate responsibilities', () => {
  const pkg = JSON.parse(read('../../package.json'));
  assert.ok(pkg.dependencies['expo-av']);
  assert.equal(pkg.dependencies['rive-react-native'], '8.0.0');
  assert.ok(!pkg.dependencies['@expo/vector-icons']);
  assert.equal(pkg.dependencies['iconoir-react-native'], '7.10.1');
  for (const path of ['../../assets/motion/car-racing.mp4', '../../assets/motion/squiggle-flow.mp4', '../../assets/bratislava-welcome.mp4']) assert.ok(!existsSync(new URL(path, import.meta.url)));
  assert.match(read('../../app/welcome.tsx'), /OnboardingVideo/);
  assert.doesNotMatch(read('../../app/welcome.tsx'), /requestForegroundPermissions/);
  assert.doesNotMatch(read('../components/loading/LoadingExperience.tsx'), /expo-av|\.mp4/);
});
test('tactile feedback honors disabled/reduced motion and remains a directly attached animated style', () => {
  const source = read('../components/motion/Motion.tsx');
  assert.match(source, /!disabled && !reduced/);
  assert.match(source, /onPressOut/);
  assert.match(source, /style=\{\[typeof style/);
  assert.match(source, /cancelAnimation\(opacity\)/);
  assert.match(source, /listener.remove\(\)/);
});
test('Home retains cached hero on refresh errors and bounds initial row entrances', () => {
  const source = read('../../app/(tabs)/discover.tsx');
  assert.match(source, /fallback.isError && !featured/);
  assert.match(source, /index < 3 && !revealed.current.has/);
  assert.match(source, /excludeFeaturedEvent/);
  assert.match(source, /initialNumToRender=\{6\}/);
});
test('contextual empty and loading states have intentional geometry', () => {
  assert.match(read('../../app/(tabs)/saved.tsx'), /scene="saved"/);
  assert.match(read('../../app/event/[id].tsx'), /LoadingState variant="detail"/);
  assert.match(read('../components/SocialUI.tsx'), /SkeletonPulse/);
  assert.match(read('../components/illustrations/CharacterScene.tsx'), /react-native-svg/);
});
test('onboarding preserves sign-in options, guest discovery and permission consent', () => {
  const source = read('../../app/welcome.tsx');
  for (const value of ['authApi.oauthStatus', '/auth', 'continueWith', 'Explore without an account', 'Previous introduction page']) assert.ok(source.includes(value));
  assert.doesNotMatch(source, /requestForegroundPermissions|useRecommendationLocation|SecureStore/);
});

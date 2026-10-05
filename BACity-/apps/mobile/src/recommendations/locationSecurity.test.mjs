import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';
import { getSessionRevision, setSessionToken } from '../store/tokenSession.ts';

async function locationHook() {
  const source = await readFile(new URL('./useRecommendationLocation.ts', import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const exports = {};
  const states = [];
  let finish;
  let started;
  const acquisitionStarted = new Promise(resolve => { started = resolve; });
  const dependencies = {
    '@react-native-async-storage/async-storage': { default: { setItem: async () => {} } },
    'expo-location': {
      getForegroundPermissionsAsync: async () => ({ granted: true }),
      getProviderStatusAsync: async () => ({ locationServicesEnabled: true }),
      getLastKnownPositionAsync: () => new Promise(resolve => { finish = resolve; started(); }),
    },
    'react-native': { Linking: {} },
    'react': {
      useState: initial => { const index = states.length; states.push(initial); return [initial, value => { states[index] = value; }]; },
      useRef: value => ({ current: value }), useCallback: callback => callback, useEffect: () => {},
    },
    '../store/tokenSession': { getSessionRevision },
    './locationPolicy': { coarsenCoordinates: (latitude, longitude) => ({ latitude, longitude }),
      isWithinRecommendationArea: () => true, shouldRequestPermission: () => false },
  };
  vm.runInNewContext(compiled, { exports, require: name => dependencies[name], __DEV__: false });
  return { hook: exports.useRecommendationLocation(true), states, acquisitionStarted,
    finish: () => finish({ coords: { latitude: 48.149, longitude: 17.108 } }) };
}

test('disabling location cancels an outstanding acquisition without restoring coordinates', async () => {
  setSessionToken('test-account');
  const instance = await locationHook();
  const pending = instance.hook.enable();
  await instance.acquisitionStarted;
  await instance.hook.disable();
  instance.finish();
  await pending;
  assert.equal(instance.states[2], null);
  assert.equal(instance.states[1], 'disabled');
  setSessionToken(null);
});

test('an acquisition from a previous session never restores coordinates', async () => {
  setSessionToken('test-account-a');
  const instance = await locationHook();
  const pending = instance.hook.enable();
  await instance.acquisitionStarted;
  setSessionToken('test-account-b');
  instance.finish();
  await pending;
  assert.equal(instance.states[2], null);
  setSessionToken(null);
});

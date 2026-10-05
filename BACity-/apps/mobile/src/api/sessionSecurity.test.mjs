import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import vm from 'node:vm';
import ts from 'typescript';
import { getSessionToken, setSessionToken, getSessionRevision } from '../store/tokenSession.ts';

async function loadClient(fetch) {
  const source = await readFile(new URL('./client.ts', import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const exports = {};
  const dependencies = {
    '../store/tokenSession': { getSessionToken, getSessionRevision },
    'react-native': { Platform: { OS: 'web' } },
    './apiUrl': { resolveApiUrl: () => 'http://localhost:8000' },
    './requestBody': { serializeRequestBody: body => body === undefined ? undefined : JSON.stringify(body) },
  };
  vm.runInNewContext(compiled, { exports, require: name => dependencies[name], fetch,
    process: { env: {} }, AbortController, setTimeout, clearTimeout, URLSearchParams });
  return exports;
}

test('old authenticated responses are rejected after logout or account switching', async () => {
  for (const nextToken of [null, 'account-b', 'account-a']) {
    setSessionToken(null);
    setSessionToken('account-a');
    let finish;
    const client = await loadClient(() => new Promise(resolve => { finish = resolve; }));
    const pending = client.apiRequest('/community/messages', { auth: true });
    setSessionToken(null);
    setSessionToken(nextToken);
    finish({ ok: true, status: 200, json: async () => ({ private: 'account-a-data' }) });
    await assert.rejects(pending, /Session changed/);
  }
  setSessionToken(null);
});

test('account change during JSON decoding cannot return private data', async () => {
  setSessionToken('account-a');
  const client = await loadClient(async () => ({ ok: true, status: 200, json: async () => {
    setSessionToken('account-b');
    return { private: 'account-a-data' };
  } }));
  await assert.rejects(client.apiRequest('/community/profile', { auth: true }), /Session changed/);
  setSessionToken(null);
});

test('stable sessions and free discovery still return data', async () => {
  setSessionToken('account-a');
  const client = await loadClient(async () => ({ ok: true, status: 200, json: async () => ({ count: 1 }) }));
  assert.equal((await client.apiRequest('/community/profile', { auth: true })).count, 1);
  assert.equal((await client.apiRequest('/events')).count, 1);
  setSessionToken(null);
});

async function loadAuthStore(auth, logoutRequest = async () => {}) {
  const source = await readFile(new URL('../store/authStore.ts', import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const exports = {};
  let state;
  let storedToken = 'account-a';
  const storage = {
    getItemAsync: async () => storedToken,
    setItemAsync: async (key, token) => { storedToken = token; },
    deleteItemAsync: async () => { storedToken = null; },
  };
  const dependencies = {
    'zustand': { create: initializer => {
      state = initializer(patch => { Object.assign(state, patch); }, () => state);
      return { getState: () => state };
    } },
    './tokenStorage': { tokenStorage: storage },
    '../api/client': { apiRequest: logoutRequest },
    '../api/auth': auth,
    './tokenSession': { getSessionRevision, setSessionToken },
    'react-native': { Platform: { OS: 'web' }, NativeModules: {} },
  };
  vm.runInNewContext(compiled, { exports, require: name => dependencies[name] });
  return { state: exports.useAuthStore.getState(), storedToken: () => storedToken };
}

test('logout clears identity before an unavailable backend answers', async () => {
  setSessionToken('account-a');
  let finish;
  const store = await loadAuthStore({}, () => new Promise(resolve => { finish = resolve; }));
  store.state.token = 'account-a';
  store.state.user = { id: 'account-a' };
  const pending = store.state.logout();
  assert.equal(getSessionToken(), null);
  assert.equal(store.state.user, null);
  assert.equal(store.state.token, null);
  finish();
  await pending;
  assert.equal(store.storedToken(), null);
});

test('a stale hydration failure cannot clear a newly logged-in account', async () => {
  setSessionToken(null);
  let rejectOld;
  let started;
  const oldStarted = new Promise(resolve => { started = resolve; });
  const store = await loadAuthStore({
    login: async () => ({ access_token: 'account-b' }),
    getMe: () => getSessionToken() === 'account-a'
      ? new Promise((resolve, reject) => { rejectOld = reject; started(); })
      : Promise.resolve({ id: 'account-b' }),
  });
  const hydration = store.state.hydrate();
  await oldStarted;
  await store.state.login('b@example.com', 'password');
  rejectOld(new Error('Session changed'));
  await hydration;
  assert.equal(getSessionToken(), 'account-b');
  assert.equal(store.state.user.id, 'account-b');
  assert.equal(store.storedToken(), 'account-b');
  setSessionToken(null);
});

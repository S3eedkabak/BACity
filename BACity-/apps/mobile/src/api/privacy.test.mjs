import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import ts from 'typescript';

const source = path => readFileSync(new URL(path, import.meta.url), 'utf8');
test('privacy routes remain account scoped and present accessible controls', () => {
  const page = source('../../app/privacy.tsx');
  assert.match(page, /privacy-requests', user\?\.id, offset/);
  assert.match(page, /getState\(\)\.user\?\.id === owner/);
  assert.match(page, /PrivacyContent key=\{owner \|\| 'guest'\}/);
  assert.match(page, /getState\(\)\.user\?\.id !== owner/);
  assert.match(page, /Submit privacy request/);
  assert.match(page, /Export all account data/);
  assert.match(source('../../app/account.tsx'), /Privacy & account rights/);
  assert.match(source('../../app/privacy-admin.tsx'), /role === 'ADMIN'/);
  assert.match(source('../../app/privacy-admin.tsx'), /PrivacyAdminContent key=\{owner \|\| 'guest'\}/);
});
test('permission minimization persists across prebuild and checked-in projects', () => {
  const app = JSON.parse(source('../../app.json')).expo;
  assert.ok(app.android.blockedPermissions.includes('android.permission.CAMERA'));
  assert.ok(app.android.blockedPermissions.includes('android.permission.ACCESS_BACKGROUND_LOCATION'));
  const manifest = source('../../android/app/src/main/AndroidManifest.xml');
  assert.match(manifest, /android.permission.CAMERA" tools:node="remove"/);
  const plist = source('../../ios/BratislavaEvents/Info.plist');
  assert.match(plist, /NSLocationWhenInUseUsageDescription/);
  assert.match(plist, /NSPhotoLibraryUsageDescription/);
});

test('privacy API uses centralized authenticated transport without caller identity', async () => {
  const calls = [];
  const exports = {};
  const compiled = ts.transpileModule(source('./privacy.ts'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  vm.runInNewContext(compiled, { exports, require: () => ({ apiRequest: async (path, options) => { calls.push({ path, options }); return []; } }) });
  await exports.privacyApi.submit('OBJECTION', 'Assessed request');
  await exports.privacyApi.requests(20);
  await exports.privacyApi.information();
  assert.equal(calls[0].options.auth, true);
  assert.deepEqual(JSON.parse(JSON.stringify(calls[0].options.body)), { kind: 'OBJECTION', details: 'Assessed request' });
  assert.equal(calls[1].path, '/privacy/requests?offset=20&limit=20');
  assert.equal(calls[1].options.auth, true);
  assert.equal(calls[2].path, '/privacy/information');
});

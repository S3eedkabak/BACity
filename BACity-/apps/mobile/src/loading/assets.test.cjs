const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { copyResource } = require('../../plugins/withRiveAsset');
test('native Rive packaging copies unchanged bytes and is idempotent', () => {
  const root = path.resolve(__dirname, '../..');
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'bacity-rive-asset-test-'));
  try {
    copyResource(root, directory); copyResource(root, directory);
    assert.deepEqual(fs.readFileSync(path.join(directory, 'bacity_walk.riv')), fs.readFileSync(path.join(root, 'assets/rive/walk-cycle.riv')));
    assert.deepEqual(fs.readdirSync(directory), ['bacity_walk.riv']);
    assert.deepEqual(fs.readFileSync(path.join(root, 'android/app/src/main/res/raw/bacity_walk.riv')), fs.readFileSync(path.join(root, 'assets/rive/walk-cycle.riv')));
  } finally { fs.rmSync(directory, { recursive: true }); }
});

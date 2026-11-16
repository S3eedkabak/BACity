import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

test('staff CSS remains synchronized with the canonical native foundations', () => {
  const command = fileURLToPath(new URL('../../scripts/export-design-tokens.mjs', import.meta.url));
  const result = spawnSync(process.execPath, ['--experimental-strip-types', command, '--check'], { encoding: 'utf8' });
  assert.equal(result.status, 0, result.stderr || result.stdout);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const cliRequire = createRequire(require.resolve('@expo/cli/package.json'));
const tar = cliRequire('tar');

test('archive dependency supports actual Expo extraction and rejects parent traversal', async () => {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'bacity-archive-security-'));
  try {
    const input = path.join(root, 'input');
    const output = path.join(root, 'output');
    await fs.mkdir(input);
    await fs.mkdir(output);
    await fs.writeFile(path.join(input, 'fixture.txt'), 'Controlled archive fixture');
    const archive = path.join(root, 'fixture.tgz');
    await tar.create({ cwd: input, file: archive, gzip: true }, ['fixture.txt']);
    const { extractAsync } = cliRequire('./build/src/utils/tar.js');
    await extractAsync(archive, output);
    assert.equal(await fs.readFile(path.join(output, 'fixture.txt'), 'utf8'), 'Controlled archive fixture');
    // A hostile entry may not write above the requested extraction directory.
    const header = new tar.Header({ path: '../escaped.txt', mode: 0o644, size: 4, type: 'File' });
    header.encode();
    const content = Buffer.alloc(512);
    content.write('evil');
    const malicious = path.join(root, 'malicious.tar');
    await fs.writeFile(malicious, Buffer.concat([header.block, content, Buffer.alloc(1024)]));
    await tar.extract({ cwd: output, file: malicious });
    await assert.rejects(fs.access(path.join(root, 'escaped.txt')), { code: 'ENOENT' });
  } finally {
    // Remove only this test's freshly-created, validated temporary directory.
    assert.equal(path.dirname(root), path.resolve(os.tmpdir()));
    assert.ok(path.basename(root).startsWith('bacity-archive-security-'));
    await fs.rm(root, { recursive: true });
  }
});

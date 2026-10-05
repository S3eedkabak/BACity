import assert from 'node:assert/strict';
import test from 'node:test';
import { safeExternalUrl } from './externalUrl.ts';

test('content links reject executable, file, custom schemes and embedded credentials', () => {
  for (const url of ['javascript:alert(1)', 'data:text/html,<script>', 'file:///private', 'intent://app',
    '//example.com', 'https://user:secret@example.com', 'https://example.com\\@evil.example',
    'https://example.com\n', 'https://', null, 'https://' + 'x'.repeat(4096)]) {
    assert.equal(safeExternalUrl(url), null);
  }
});

test('original public links and their meaningful query parameters remain unchanged', () => {
  for (const url of ['https://venue.sk/events?id=123#tickets', 'http://venue.sk/old-calendar',
    'https://veranstaltungen.example/koncert']) assert.equal(safeExternalUrl(url), url);
});

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('community source evidence is optional, explicit and transmitted', () => {
  const screen = readFileSync(new URL('../../app/(tabs)/contribute.tsx', import.meta.url), 'utf8');
  assert.match(screen, /source_url: fields.source_url \|\| ''/);
  assert.match(screen, /public_source_url: fields.public_source_url \|\| null/);
  assert.match(screen, /Original event website \(optional, HTTPS\)/);
});

test('sourceless events cannot open an empty original link', () => {
  const screen = readFileSync(new URL('../../app/event/[id].tsx', import.meta.url), 'utf8');
  assert.match(screen, /!!event.source_url && <Pressable/);
  assert.match(screen, /Linking.openURL\(event.source_url\)/);
});

test('learning stays in role-gated moderation tools, not consumer actions', () => {
  const screen = readFileSync(new URL('../../app/moderator.tsx', import.meta.url), 'utf8');
  assert.match(screen, /learning: "\/crawler\/admin\/learning"/);
  assert.match(screen, /\["ADMIN", "MODERATOR"\].includes\(user.role\)/);
  assert.match(screen, /!\['audit', 'sources', 'learning'\].includes\(mode\)/);
});

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { serializeRequestBody } from "./requestBody.ts";

const here = dirname(fileURLToPath(import.meta.url));
const premiumClients = [
  "groups.ts",
  "areaWatches.ts",
  "eveningPlans.ts",
  "weekendPlans.ts",
];

test("central request serialization sends premium payloads as JSON objects", () => {
  const cases = [
    { name: "Friends", target_date: "2026-10-03", start_time: "18:00", end_time: "23:00", categories: ["Music"], max_participants: 6 },
    { code: "a".repeat(32) },
    { name: "Old Town", center_latitude: 48.1486, center_longitude: 17.1077, radius_km: 2, categories: ["Culture"] },
    { date: "2026-10-03", start_time: "18:00", end_time: "00:00", categories: ["Music"] },
    { weekend_start: "2026-10-03", mode: "weekend", categories: ["Culture"] },
  ];

  for (const payload of cases) {
    const encoded = serializeRequestBody(payload);
    assert.equal(typeof encoded, "string");
    const decoded = JSON.parse(encoded);
    assert.equal(Array.isArray(decoded), false);
    assert.equal(typeof decoded, "object");
    assert.deepEqual(decoded, payload);
  }
});

test("premium API callers never pre-serialize bodies", async () => {
  for (const file of premiumClients) {
    const source = await readFile(join(here, file), "utf8");
    assert.doesNotMatch(source, /body\s*:\s*JSON\.stringify\s*\(/, `${file} must pass an object to apiRequest`);
  }
});

test("group create and join keep independent mutation state", async () => {
  const source = await readFile(join(here, "../../app/groups.tsx"), "utf8");
  assert.match(source, /const createMutation = useGroupMutation\(\)/);
  assert.match(source, /const joinMutation = useGroupMutation\(\)/);
  assert.match(source, /createMutation\.mutateAsync/);
  assert.match(source, /joinMutation\.mutateAsync/);
});

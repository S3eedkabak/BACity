import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { EVENT_VIEWPORT_LIMIT, mergeViewportEvents } from "./viewportData.ts";

const here = dirname(fileURLToPath(import.meta.url));
const bounds = { min_lat: 48.1, max_lat: 48.2, min_lng: 17.0, max_lng: 17.2 };
const event = (id, latitude, longitude, title = id) => ({ id, latitude, longitude, title });

test("viewport refresh replaces only records inside the refreshed bounds", () => {
  const merged = mergeViewportEvents(
    [event("changed", 48.15, 17.1, "old"), event("removed", 48.16, 17.11), event("outside", 48.25, 17.1)],
    [event("changed", 48.15, 17.1, "new"), event("added", 48.17, 17.12)],
    bounds,
  );
  assert.deepEqual(merged.map(({ id, title }) => ({ id, title })), [
    { id: "changed", title: "new" },
    { id: "outside", title: "outside" },
    { id: "added", title: "added" },
  ]);
});

test("a capped viewport response never erases cached events that may be beyond the server limit", () => {
  const cached = [event("cached", 48.15, 17.1)];
  const capped = Array.from({ length: EVENT_VIEWPORT_LIMIT }, (_, index) => event(`fresh-${index}`, 48.15, 17.1));
  const merged = mergeViewportEvents(cached, capped, bounds);
  assert.equal(merged.some(item => item.id === "cached"), true);
});

test("native and web maps use bounded viewport APIs instead of the first event page", async () => {
  for (const relative of ["../../app/(tabs)/map.tsx", "../../app/(tabs)/map.web.tsx"]) {
    const source = await readFile(join(here, relative), "utf8");
    assert.match(source, /eventsInViewport/);
    assert.doesNotMatch(source, /useEvents\s*\(\s*\{\s*limit\s*:\s*100/);
  }
});

import assert from "node:assert/strict";
import test from "node:test";

import { resolveApiUrl } from "./apiUrl.ts";

test("uses the Android emulator host on Android", () => {
  assert.equal(resolveApiUrl("http://10.0.2.2:8000", "android"), "http://10.0.2.2:8000");
  assert.equal(resolveApiUrl("http://localhost:8000", "android"), "http://10.0.2.2:8000");
});

test("uses localhost for local web and iOS simulator builds", () => {
  assert.equal(resolveApiUrl("http://10.0.2.2:8000", "web"), "http://localhost:8000");
  assert.equal(resolveApiUrl("http://10.0.2.2:8000", "ios"), "http://localhost:8000");
});

test("does not rewrite production, staging, or LAN URLs", () => {
  const urls = [
    "https://api.bacity.example",
    "https://staging.bacity.example/v1",
    "http://192.168.1.25:8000",
  ];
  for (const url of urls) {
    assert.equal(resolveApiUrl(url, "android"), url);
    assert.equal(resolveApiUrl(url, "ios"), url);
    assert.equal(resolveApiUrl(url, "web"), url);
  }
});

test("uses platform-correct local defaults", () => {
  assert.equal(resolveApiUrl(undefined, "android"), "http://10.0.2.2:8000");
  assert.equal(resolveApiUrl(undefined, "ios"), "http://localhost:8000");
  assert.equal(resolveApiUrl(undefined, "web"), "http://localhost:8000");
});

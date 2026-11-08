const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const ts = require("typescript");

function loadTypeScriptModule(file) {
  const source = fs.readFileSync(file, "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
    },
  }).outputText;
  const module = { exports: {} };
  Function("exports", "module", "require", output)(module.exports, module, require);
  return module.exports;
}

const geoJson = loadTypeScriptModule(path.join(__dirname, "eventGeoJson.ts"));

function event(overrides = {}) {
  return {
    id: "event-1",
    title: "Map event",
    latitude: 48.1486,
    longitude: 17.1077,
    ...overrides,
  };
}

test("populated event data creates longitude-latitude GeoJSON points", () => {
  const located = [event()].filter(geoJson.hasValidMapCoordinates);
  const shape = geoJson.buildEventFeatureCollection(located, () => true);

  assert.equal(shape.features.length, 1);
  assert.equal(shape.features[0].id, "event-1");
  assert.deepEqual(shape.features[0].geometry.coordinates, [17.1077, 48.1486]);
  assert.deepEqual(shape.features[0].properties, {
    id: "event-1",
    title: "Map event",
    nearby: true,
  });
});

test("invalid coordinates cannot poison the native ShapeSource", () => {
  const located = [
    event(),
    event({ id: "nan", latitude: Number.NaN }),
    event({ id: "bad-latitude", latitude: 91 }),
    event({ id: "bad-longitude", longitude: -181 }),
    event({ id: "string-coordinate", longitude: "17.1" }),
  ].filter(geoJson.hasValidMapCoordinates);

  assert.deepEqual(located.map((item) => item.id), ["event-1"]);
});

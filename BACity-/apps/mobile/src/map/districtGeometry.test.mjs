import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {districtBoundaryLines,DISTRICT_INKS} from './districtGeometry.ts';

test('every official polygon ring becomes native line geometry with unchanged coordinates',async()=>{
  const data=JSON.parse(await readFile(new URL('../../../../services/api/app/data/bratislava-districts.geojson',import.meta.url)));
  const lines=districtBoundaryLines(data);
  assert.equal(data.features.length,17);
  assert.equal(lines.features.length,17);
  assert.equal(Object.keys(DISTRICT_INKS).length,17);
  for(let i=0;i<17;i++){
    const original=data.features[i],line=lines.features[i];
    assert.equal(line.geometry.type,'LineString');
    assert.equal(line.properties.id,original.properties.id);
    const rings=original.geometry.type==='Polygon'?original.geometry.coordinates:original.geometry.coordinates.flat();
    assert.deepEqual(line.geometry.coordinates,rings[0]);
    for(const ring of rings){assert.ok(ring.length>=4);assert.deepEqual(ring[0],ring.at(-1));}
  }
});

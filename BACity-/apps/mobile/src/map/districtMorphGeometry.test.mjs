import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import test from 'node:test';
import {districtBounds,morphRings,projectCoordinate,interpolateRingPath} from './districtMorphGeometry.ts';

const viewport={width:393,height:852,headerHeight:246};
const frame={anchor:[17.11,48.15],anchorPoint:[196,355],eastPoint:[225,355],northPoint:[196,313],mapOffset:[0,0],delta:.01};

test('all 17 official geometries produce finite geographic silhouettes and the same header shape',async()=>{
  const collection=JSON.parse(await readFile(new URL('../../../../services/api/app/data/bratislava-districts.geojson',import.meta.url)));
  assert.equal(collection.features.length,17);
  let endPath;
  for(const feature of collection.features){
    const shape=morphRings(feature,frame,viewport);
    assert.ok(shape,feature.properties.name);
    assert.equal(shape.source.length,48);
    assert.equal(shape.target.length,48);
    assert.ok(shape.source.every(point=>point.every(Number.isFinite)));
    assert.ok(shape.target.every(point=>point.every(Number.isFinite)));
    const [west,south,east,north]=districtBounds(feature);
    assert.ok(west<east&&south<north);
    const start=interpolateRingPath(shape.source,shape.target,0);
    const end=interpolateRingPath(shape.source,shape.target,1);
    assert.ok(start.startsWith('M')&&start.endsWith('Z'));
    assert.notEqual(start,end);
    if(endPath)assert.equal(end,endPath);
    endPath=end;
  }
});

test('projection uses the current map anchors and supports offscreen shapes',()=>{
  assert.deepEqual(projectCoordinate(frame.anchor,frame),[196,355]);
  const north=projectCoordinate([17.11,48.16],frame);
  assert.ok(Math.abs(north[1]-313)<.01);
  const artificial={geometry:{type:'MultiPolygon',coordinates:[
    [[[17.10,48.15],[17.101,48.15],[17.101,48.151],[17.10,48.15]]],
    [[[17.15,48.18],[17.20,48.18],[17.20,48.22],[17.15,48.22],[17.15,48.18]]],
  ]},properties:{id:'test',name:'Irregular',count:1,area_token:'',label_coordinates:[17.18,48.2]}};
  const shape=morphRings(artificial,frame,viewport);
  assert.ok(shape);
  assert.ok(shape.source.some(point=>point[0]>viewport.width));
  assert.deepEqual(shape.bounds,[17.10,48.15,17.20,48.22]);
});

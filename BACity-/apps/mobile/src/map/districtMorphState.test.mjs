import assert from 'node:assert/strict';
import test from 'node:test';
import {useDistrictMorph} from './districtMorphState.ts';

test('Back during the mounted forward morph reverses once and ignores late completion',()=>{
  const state=()=>useDistrictMorph.getState();
  state().cancel();
  const nonce=state().claim('stare-mesto');
  const entry={id:'stare-mesto',savedCamera:{centerCoordinate:[17.1,48.15],zoomLevel:10},savedBounds:{min_lat:48,max_lat:49,min_lng:17,max_lng:18}};
  assert.equal(state().start(nonce,entry),true);
  assert.equal(state().beginReturn(),false);
  state().markAreaMounted(nonce);
  assert.equal(state().beginReturn(),true);
  assert.equal(state().beginReturn(),true);
  state().areaVisible(nonce);
  assert.equal(state().phase,'returning');
  assert.equal(state().claim('ruzinov'),null);
  state().finishReturn();
  assert.equal(state().phase,'idle');
  assert.equal(state().entry,null);
  const next=state().claim('ruzinov');
  state().cancel(nonce);
  assert.equal(state().nonce,next);
  assert.equal(state().phase,'selecting');
  state().cancel(next);
});

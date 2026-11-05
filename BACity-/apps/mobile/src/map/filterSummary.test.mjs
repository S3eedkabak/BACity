import test from 'node:test';
import assert from 'node:assert/strict';
import { appliedFilterLabels, filterSummary } from './filterSummary.ts';
test('map filter control lists every applied filter, including search and end-only dates',()=>{
 const value={category:'Music',free_only:true,status:'fresh',starts_before:'2026-11-03T23:00:00Z',q:'  jazz  '};
 const labels=appliedFilterLabels(value);
 assert.equal(labels.length,5);
 assert.ok(labels.includes('Music')&&labels.includes('Free')&&labels.includes('Fresh listings')&&labels.includes('“jazz”'));
 assert.match(filterSummary(value),/Until/);
 assert.deepEqual(appliedFilterLabels({free_only:false,q:'   '}),[]);
 assert.equal(filterSummary({}),'Any time · All interests');
});

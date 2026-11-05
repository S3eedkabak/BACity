import test from 'node:test';
import assert from 'node:assert/strict';
import { motion, sheetTarget } from '../navigation/motion.ts';
test('geometry profiles cannot oscillate or overshoot their target',()=>{
 for(const profile of [motion.spring,motion.surfaceSpring,motion.badgeSpring,motion.sheet]){
  assert.ok(profile.damping >= 2*Math.sqrt(profile.stiffness*profile.mass));
  assert.equal(profile.overshootClamping,true);
 }
 assert.notDeepEqual(motion.sheet,motion.spring);
 assert.notDeepEqual(motion.surfaceSpring,motion.badgeSpring);
});
test('sheet release settles on a bounded detent in either direction',()=>{
 assert.equal(sheetTarget(280,0,[0,300,460]),300);
 assert.equal(sheetTarget(280,1000,[0,300,460]),460);
 assert.equal(sheetTarget(120,-1000,[0,300,460]),0);
});

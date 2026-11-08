import test from 'node:test';
import assert from 'node:assert/strict';
import { passwordGuidance, reviewError, formatCount, createActionGate, applySaved, notificationRoute } from './policy.ts';
import { darkColors, lightColors } from '../theme/colors.ts';

test('password guidance matches server length, whitespace, UTF-8 and Unicode policy without security claims', () => {
  assert.equal(passwordGuidance(' '.repeat(12)).valid, false);
  assert.equal(passwordGuidance('short').valid, false);
  assert.equal(passwordGuidance('🔑'.repeat(7)).valid, false);
  assert.equal(passwordGuidance('🔑'.repeat(8)).valid, true);
  assert.equal(passwordGuidance('ľúbim Bratislavu').valid, true);
  assert.equal(passwordGuidance('a'.repeat(4097)).valid, false);
  assert.equal(passwordGuidance('á'.repeat(2049)).valid, false);
  assert.match(passwordGuidance('long unique passphrase').text, /cannot guarantee/);
});
test('review validation keeps supported dimensions and bounds, including partial ratings', () => {
  assert.match(reviewError('event', 'tiny', {value: 4}), /10/);
  assert.match(reviewError('event', 'Good experience', {}), /at least/);
  assert.match(reviewError('event', 'Good experience', {atmosphere: 4}), /1 to 5/);
  assert.match(reviewError('event', 'Good experience', {value: 1.2}), /1 to 5/);
  assert.equal(reviewError('event', 'Good experience', {value: 4}), '');
});
test('optimistic rollback touches only its own event and prevents duplicate rows', () => {
  const a={id:'a'},b={id:'b'},c={id:'c'};
  let state=applySaved([a,b],a,false); state=applySaved(state,c,true); state=applySaved(state,a,true);
  assert.deepEqual(state.map(x=>x.id).sort(),['a','b','c']);
  assert.equal(applySaved(state,c,true).filter(x=>x.id==='c').length,1);
});
test('same-frame requests are locked per entity, independent operations remain possible', () => {
  const gate=createActionGate(); assert.equal(gate.enter('a'),true);assert.equal(gate.enter('a'),false);assert.equal(gate.enter('b'),true);gate.leave('a');assert.equal(gate.enter('a'),true);
});
test('localized counters handle decreases, zero and large numbers',()=>{
  assert.equal(formatCount(0,'sk-SK'),'0');assert.equal(formatCount(-10),'0');assert.equal(formatCount(123456,'en-US'),'123,456');assert.equal(formatCount(NaN),'0');
});
test('notification destinations are allowlisted and malformed targets never become routes',()=>{
  assert.equal(notificationRoute('message','../../account'),null);assert.equal(notificationRoute('unknown','123'),null);assert.equal(notificationRoute('privacy_request',null),'/privacy');
  assert.equal(notificationRoute('group','12345678-1234-1234-1234-123456789abc'),'/group/12345678-1234-1234-1234-123456789abc');
});
function luminance(hex) { const rgb=hex.slice(1).match(/../g).map(c=>parseInt(c,16)/255).map(c=>c<=.04045?c/12.92:((c+.055)/1.055)**2.4);return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722; }
function contrast(a,b) { const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05); }
test('brand primary preserved and key body/action pairs meet 4.5:1 in both palettes',()=>{
  for(const palette of [darkColors,lightColors]) {
    assert.equal(palette.primary,'#A93468');
    for(const [fg,bg] of [['text','background'],['text','surface'],['textMuted','surfaceAlt'],['primaryDark','primarySoft'],['white','primary'],['danger','dangerSurface'],['free','successSurface']])assert.ok(contrast(palette[fg],palette[bg])>=4.5,`${fg} on ${bg}: ${contrast(palette[fg],palette[bg])}`);
  }
});

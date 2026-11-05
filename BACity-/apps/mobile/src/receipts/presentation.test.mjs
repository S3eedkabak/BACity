import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { eveningReceipt, weekendReceipt, receiptTime, receiptDate, receiptVenue, stopNotice, sharePlan, feedPosition, printDuration, receiptIsComplete, verifiedPayment } from './presentation.ts';
import { loadingPresentation } from '../loading/registry.ts';

const event = (id, start, extra={}) => ({ id, title:'Fixture event '+id, start_time:start, end_time:null, start_precision:'time', venue:null, address:null, status:'fresh', ...extra });
const item = (e) => ({event:e,reasons:['From the existing planner']});
const plan = (items) => ({id:'original-result',explanation:'An existing result',strategy:'best_match',limited:false,items});

test('one stop and multiple stops preserve source references and intended engine order',()=>{
  const original=plan([item(event('b','2030-06-15T19:00:00Z')),item(event('a','2030-06-15T17:00:00Z'))]);
  const snapshot=JSON.stringify(original);const printed=eveningReceipt(original);
  assert.equal(printed.count,2);assert.equal(printed.days[0].stops[0].event,original.items[0].event);
  assert.equal(JSON.stringify(original),snapshot);assert.equal(eveningReceipt(plan([original.items[0]])).count,1);
});
test('midnight crossing groups Bratislava calendar days without removing events',()=>{
  const result=eveningReceipt(plan([item(event('a','2030-06-15T20:00:00Z')),item(event('b','2030-06-15T22:30:00Z'))]));
  assert.equal(result.days.length,2);assert.match(result.days[1].label,/16 Jun/);
});
test('weekend keeps server day grouping, empty days and repeated recurring occurrences',()=>{
  const first=event('same','2030-06-15T12:00:00Z',{identity_kind:'recurring'});
  const next=event('same','2030-06-16T12:00:00Z',{identity_kind:'recurring'});
  const result=weekendReceipt({id:'w',explanation:'Real engine order',days:[{date:'2030-06-15',day:'Saturday',items:[item(first)]},{date:'2030-06-16',day:'Sunday',items:[item(next)]},{date:'2030-06-17',day:'Empty fixture',items:[]}]});
  assert.equal(result.days.length,3);assert.equal(result.count,2);assert.equal(result.days[1].stops[0].event,next);
  assert.match(sharePlan(result),/No events safely fit this day/);
});
test('duplicate IDs are not mistaken for duplicate occurrences or lost as React keys',()=>{
  const e=event('same','2030-06-15T20:00:00Z');const result=eveningReceipt(plan([item(e),item(e)]));
  assert.equal(result.count,2);assert.notEqual(result.days[0].stops[0].key,result.days[0].stops[1].key);
});
test('date precision never displays the synthetic midnight as a known start time',()=>{
  assert.equal(receiptTime(event('a','2030-06-15T00:00:00Z',{start_precision:'date'})),'Time unconfirmed');
  assert.equal(receiptTime(event('a','invalid')),'Time unconfirmed');
  assert.equal(receiptDate('invalid'),'Date unconfirmed');
});
test('times use Bratislava summer/winter offsets and do not guess missing ends',()=>{
  assert.equal(receiptTime(event('a','2030-06-15T17:00:00Z')),'19:00 · end unconfirmed');
  assert.equal(receiptTime(event('a','2030-12-15T17:00:00Z',{end_time:'2030-12-15T19:00:00Z'})),'18:00 – 20:00');
  assert.match(receiptTime(event('a','2030-12-15T17:00:00Z',{end_time:'2030-12-15T16:00:00Z'})),/end unconfirmed/);
});
test('missing venue is honest; cancellation, recurrence and multi-day notices survive',()=>{
  const e=event('a','2030-06-15T17:00:00Z',{status:'cancelled',end_date:'2030-06-16',identity_kind:'recurring'});
  assert.equal(receiptVenue(e),'Location unconfirmed');assert.match(stopNotice(e),/cancelled/);assert.match(stopNotice(e),/Multi-day/);assert.match(stopNotice(e),/Recurring/);
});
test('sharing includes actual ordered content and does not imply bought admission',()=>{
  const text=sharePlan(eveningReceipt(plan([item(event('a','2030-06-15T17:00:00Z'))])));
  assert.match(text,/Fixture event a/);assert.match(text,/19:00/);assert.match(text,/Admission and reservations are not included/);
  assert.doesNotMatch(text,/EUR 0|Free|Booking confirmed/);
});
test('stepped feed is bounded, monotonic, paused and completes in bounded time',()=>{
  let previous=0;let pauses=0;
  for(let i=0;i<=1000;i++){const p=feedPosition(i/1000,true);assert.ok(p>=previous&&p<=1);if(p===previous)pauses++;previous=p;}
  assert.ok(pauses>100);assert.equal(feedPosition(1,true),1);assert.equal(feedPosition(.27,false),.27);
  assert.equal(feedPosition(-1,true),0);assert.equal(feedPosition(2,true),1);
  assert.ok(printDuration(100000)<=1850);assert.ok(printDuration(10)>=1250);
});
test('new alternatives and pending lookups cannot inherit an old completed receipt state',()=>{
  assert.equal(receiptIsComplete(false,'result-b','result-a'),false);
  assert.equal(receiptIsComplete(true,'result-a','result-a'),false);
  assert.equal(receiptIsComplete(false,null,null),false);
  assert.equal(receiptIsComplete(false,'result-a','result-a'),true);
});
test('only the two inline planning contexts opt out of the full-screen loading overlay',()=>{
  assert.equal(loadingPresentation('plan-generation'),'inline');assert.equal(loadingPresentation('weekend-generation'),'inline');
  for(const name of ['startup','event-details','saved','explore','search','map','bacity-plus'])assert.equal(loadingPresentation(name),'overlay');
});

const paid={receipt_id:'server-receipt',payment_status:'paid',verification_source:'provider_confirmed',product:'Fixture product',transaction_reference:'provider-ref',paid_at:'2030-06-15T17:00:00Z',amount_minor:1234,currency:'EUR',currency_exponent:2};
test('paid receipt seam requires authoritative transaction fields, not active entitlement or redirect',()=>{
  assert.equal(verifiedPayment({active:true,plus_active:true,billing:'success'}),null);
  for(const status of ['pending','cancelled','failed','refunded'])assert.equal(verifiedPayment({...paid,payment_status:status}),null);
  assert.equal(verifiedPayment({...paid,verification_source:'frontend_callback'}),null);
  assert.deepEqual(verifiedPayment(paid),paid);
});
test('malformed dates, missing amount, floats, bad currency and unsafe integer amounts fail closed',()=>{
  for(const extra of [{paid_at:'invalid'},{paid_at:'2030-06-15T17:00:00'},{amount_minor:undefined},{amount_minor:-1},{amount_minor:1.5},{amount_minor:Number.MAX_SAFE_INTEGER+1},{currency:'usd<script>'},{currency_exponent:8},{transaction_reference:''}])assert.equal(verifiedPayment({...paid,...extra}),null);
});
test('reopening a backend record is pure/idempotent and sensitive fields are excluded',()=>{
  const before=JSON.stringify(paid);const result=verifiedPayment({...paid,purchase_token:'secret',card_number:'secret',merchant_name:'Recorded seller'});
  assert.equal(result.merchant_name,'Recorded seller');assert.ok(!('purchase_token' in result));assert.ok(!('card_number' in result));
  assert.deepEqual(verifiedPayment(paid),verifiedPayment(paid));assert.equal(JSON.stringify(paid),before);
});
test('inline result integration retains real mutations and no standalone routes or lookup inside printer',()=>{
  const read=p=>readFileSync(new URL(p,import.meta.url),'utf8');
  for(const screen of ['evening-plan','weekend-plan']){
    const source=read(`../../app/${screen}.tsx`);assert.match(source,/PrintedPlanResult/);assert.match(source,/generation\.mutate/);assert.match(source,/submittedLock\.current/);assert.match(source,/fallback=/);assert.match(source,/generation\.submittedAt/);
  }
  const ui=read('../components/receipts/PrintedPlanResult.tsx');assert.doesNotMatch(ui,/apiRequest|generateEveningPlans|generateWeekendPlans|useMutation/);assert.match(ui,/useViewOnMap/);assert.match(ui,/Share\.share/);
  const animation=read('../components/receipts/ReceiptPrinterView.tsx');assert.match(animation,/cancelAnimation/);assert.match(animation,/reduceMotionChanged/);assert.match(animation,/AppState\.addEventListener/);assert.match(animation,/printed\.current\.has/);assert.match(animation,/scrollEnabled=\{complete/);
});

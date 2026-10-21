import assert from 'node:assert/strict';
import test from 'node:test';
import {layerSpec} from './layerSpec.ts';
import { readFile } from 'node:fs/promises';
import { areaRoute, clusterAction, areaBounds, dateRange, presetRange, parseFilters, sharedEventFilters } from './area.ts';

const properties={count:1207,id:null,area_token:'signed-query',area_name:'Events near this area',bounds:[17,48.1,17.2,48.2]};
test('cluster actions keep area context and filters, with a neutral geographic label',()=>{
  const filters={category:'Music',free_only:true,...presetRange('Weekend',new Date('2026-10-21T12:00:00Z'))};
  const route=areaRoute(properties.area_token,filters);
  assert.equal(route.pathname,'/area-events');
  assert.deepEqual(parseFilters(route.params.filters),filters);
  assert.equal(clusterAction(properties,12),'zoom');assert.equal(clusterAction(properties,16),'area');
  assert.equal(clusterAction({...properties,id:'one'},16),'event');
  assert.deepEqual(areaBounds(properties),{min_lng:17,min_lat:48.1,max_lng:17.2,max_lat:48.2});
});
test('date ranges preserve Bratislava days across DST and reject invalid dates',()=>{
  const spring=dateRange('2027-03-28','2027-03-28');
  assert.equal(Date.parse(spring.starts_before)-Date.parse(spring.starts_after)+1,23*3600000);
  const autumn=dateRange('2026-10-25','2026-10-25');
  assert.equal(Date.parse(autumn.starts_before)-Date.parse(autumn.starts_after)+1,25*3600000);
  assert.equal(dateRange('2027-02-30','2027-03-01'),null);
  assert.equal(dateRange('2027-01-02','2027-01-01'),null);
  assert.equal(presetRange('Tomorrow',new Date('2026-10-21T22:30:00Z')).starts_after,'2026-10-22T22:00:00.000Z');
});
test('both map surfaces use complete aggregation, native cluster actions, and bounded area lists',async()=>{
  const native=await readFile(new URL('./MapScreen.tsx',import.meta.url),'utf8');
  const web=await readFile(new URL('./MapLibre.web.tsx',import.meta.url),'utf8');
  const area=await readFile(new URL('../../app/area-events.tsx',import.meta.url),'utf8');
  assert.match(native,/clusterCamera/);assert.match(native,/setSelectedCluster/);
  assert.match(native,/mapClusters/);assert.match(native,/areaRoute/);assert.match(native,/signal/);assert.match(web,/latest.current.mapStyle/);assert.match(web,/queryRenderedFeatures/);
  assert.match(area,/useInfiniteQuery/);assert.match(area,/next_cursor/);assert.match(area,/EventCard/);assert.match(area,/onToggleSave/);assert.match(area,/router.back/);
});

test('web layers preserve native paint/layout and omit an absent optional filter',()=>{
  const fill=layerSpec('district','fill','city-districts',{fillColor:'#A93468',fillOpacity:.07});
  assert.equal(Object.hasOwn(fill,'filter'),false);
  assert.deepEqual(fill.paint,{'fill-color':'#A93468','fill-opacity':.07});
  const label=layerSpec('label','symbol','events',{textField:'E',textColor:'#fff',textFont:['Noto Sans Regular'],textHaloWidth:1},['==',['get','count'],1]);
  assert.equal(label.layout['text-field'],'E');assert.equal(label.paint['text-color'],'#fff');assert.equal(label.paint['text-halo-width'],1);
});

test('area filter edits propagate back without leaking district or GPS context into map filters',()=>{
  assert.deepEqual(sharedEventFilters({category:'Music',q:'jazz',district:'528595',near_lat:48.15,near_lng:17.1,radius_km:3}),
    {category:'Music',q:'jazz',free_only:undefined,starts_after:undefined,starts_before:undefined,status:undefined});
});

test('camera uses longitude/latitude content bounds with bounded progressive zoom', async()=>{
  const {clusterCamera}=await import('./area.ts');
  const feature={bounds:[17.10,48.14,17.12,48.16]};
  const target=clusterCamera(feature,12);
  assert.deepEqual(target.centerCoordinate,[17.11,48.15]);
  assert.equal(target.zoomLevel,14);
  assert.equal(clusterCamera({...feature,coincident:true},12),null);
  assert.equal(clusterCamera(feature,18),null);
  assert.equal(clusterCamera({bounds:[48.14,17.10,48.16,17.12]},12),null);
});

test('cards describe active ranges and query-specific next availability',async()=>{
  const {availabilityLabel}=await import('./eventAvailability.ts');
  const now=new Date('2026-10-21T12:00:00Z');
  assert.match(availabilityLabel({start_time:'2026-07-01T10:00:00Z',end_time:'2027-01-17T20:00:00Z'},now),/^On now/);
  assert.match(availabilityLabel({identity_kind:'recurring',start_time:'2026-10-21T15:00:00Z',next_occurrence_start:'2026-10-22T15:00:00Z'},now),/^Recurring · Selected dates/);
});

test('multi-day ranges, recurrence evidence, and missing dates are explicit',async()=>{
  const {availabilityLabel}=await import('./eventAvailability.ts');
  const now=new Date('2026-10-21T12:00:00Z');
  const range=availabilityLabel({start_time:'2026-11-12T19:00:00Z',end_date:'2026-11-15'},now);
  assert.match(range,/12/);assert.match(range,/15/);assert.match(range,/–/);
  assert.match(availabilityLabel({start_time:'2026-12-31T19:00:00Z',end_time:'2027-01-02T19:00:00Z'},now),/2026.*2027/);
  assert.match(availabilityLabel({identity_kind:'recurring',recurrence_label:'Every Friday',start_time:'2026-11-06T19:00:00Z'},now),/^Recurring · Every Friday/);
  assert.equal(availabilityLabel({start_time:'invalid'},now),'Schedule unavailable');
  assert.ok(!availabilityLabel({start_time:'2026-11-12T19:00:00Z'},now).includes('–'));
});

test('event localization rejects placeholders and swapped points and keeps longitude first',async()=>{
  const {eventCoordinates}=await import('./eventLocation.ts');
  const event={latitude:48.15,longitude:17.12,address:'Venue street 5',venue:null};
  assert.deepEqual(eventCoordinates(event),[17.12,48.15]);
  for(const point of [{latitude:17.12,longitude:48.15},{latitude:NaN},{latitude:null,longitude:null},{latitude:48.1486,longitude:17.1077}])assert.equal(eventCoordinates({...event,...point}),null);
  assert.equal(eventCoordinates({...event,venue:{name:'Various venues'}}),null);
  assert.deepEqual(eventCoordinates({...event,latitude:null,longitude:null,venue:{name:'Real Hall',latitude:48.16,longitude:17.13}}),[17.13,48.16]);
});

test('date-only listings never acquire an invented midnight clock',async()=>{
  const {availabilityLabel}=await import('./eventAvailability.ts');
  const event={start_time:'2027-01-01T23:00:00Z',start_precision:'date'};
  assert.ok(!availabilityLabel(event).includes('00:00'));
  assert.ok(!availabilityLabel({...event,identity_kind:'recurring'}).match(/00:00|12:00/));
  assert.match(availabilityLabel({...event,start_precision:'time'}),/00:00|12:00/);
});

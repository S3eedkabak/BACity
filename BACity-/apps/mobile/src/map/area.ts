import type { EventViewportBounds } from '../api/events';

export interface MapFilters {
  category?: string;
  q?: string;
  free_only?: boolean;
  starts_after?: string;
  starts_before?: string;
  status?: 'fresh' | 'stale';
  district?:string;
  near_lat?:number;
  near_lng?:number;
  radius_km?:number;
}
export interface MapProperties {
  count: number;
  coincident?: boolean;
  expansion_zoom?: number;
  point_count: number | null;
  point_count_abbreviated: string;
  id: string | null;
  area_token: string;
  area_name: string;
  bounds: [number, number, number, number];
}
export interface ClusterData extends GeoJSON.FeatureCollection<GeoJSON.Point, MapProperties> {
  total: number;
  clustered_events: number;
  individual_events: number;
  area_token: string;
  area_name: string;
}
export const EMPTY_MAP: ClusterData = { type:'FeatureCollection',features:[],total:0,clustered_events:0,individual_events:0,area_token:'',area_name:'Events near this area' };
export function areaRoute(token: string, filters: MapFilters) {
  return { pathname:'/area-events' as const, params:{ area:token, filters:JSON.stringify(filters) } };
}
export function clusterAction(properties: MapProperties, zoom: number): 'event' | 'zoom' | 'area' {
  if (properties.id) return 'event';
  return zoom < 14 ? 'zoom' : 'area';
}
export function areaBounds(properties: MapProperties): EventViewportBounds {
  const [min_lng,min_lat,max_lng,max_lat] = properties.bounds;
  return {min_lng,min_lat,max_lng,max_lat};
}
export function parseFilters(value?: string): MapFilters {
  try { const result = JSON.parse(value || '{}'); return result && typeof result==='object' && !Array.isArray(result) ? result : {}; } catch { return {}; }
}
// A local midnight in Europe/Bratislava, including both DST offsets.
function midnight(day: string): string {
  const target = Date.parse(day+'T00:00:00Z');
  const parts = new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Bratislava',hour:'2-digit',hourCycle:'h23'}).format(new Date(target));
  return new Date(target-Number(parts)*3600000).toISOString();
}
export function dateRange(from: string, to: string): Pick<MapFilters,'starts_after'|'starts_before'> | null {
  const valid = (s: string) => /^\d{4}-\d{2}-\d{2}$/.test(s) && Number.isFinite(Date.parse(s)) && new Date(s).toISOString().slice(0,10)===s;
  if (!valid(from)||!valid(to)||from>to) return null;
  const next = new Date(Date.parse(to+'T12:00:00Z')+86400000).toISOString().slice(0,10);
  return {starts_after:midnight(from),starts_before:new Date(Date.parse(midnight(next))-1).toISOString()};
}
export function presetRange(preset: 'Today'|'Tomorrow'|'Weekend', now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Bratislava',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now);
  const part = (type: string) => parts.find(p=>p.type===type)!.value;
  let day = new Date(`${part('year')}-${part('month')}-${part('day')}T12:00:00Z`);
  if (preset==='Tomorrow') day = new Date(+day+86400000);
  if (preset==='Weekend' && day.getUTCDay()!==0) day = new Date(+day+((6-day.getUTCDay()+7)%7)*86400000);
  const end = preset==='Weekend' && day.getUTCDay()===6 ? new Date(+day+86400000) : day;
  return dateRange(day.toISOString().slice(0,10),end.toISOString().slice(0,10))!;
}

export function clusterProperties(value: any): MapProperties {
  return {...value,bounds:typeof value.bounds==='string'?JSON.parse(value.bounds):value.bounds};
}

export function sharedEventFilters(value:MapFilters):MapFilters {
  const {category,q,free_only,starts_after,starts_before,status}=value;
  return {category,q,free_only,starts_after,starts_before,status};
}

// Use explicit native camera settings: fitting a server grid cell can move to
// empty geography, and zero-area fitBounds is unstable for coincident events.
export function clusterCamera(properties:MapProperties, zoom:number) {
  if(properties.coincident || zoom>=18)return null;
  const [west,south,east,north]=properties.bounds;
  if(![west,south,east,north].every(Number.isFinite)||west>east||south>north||west<16.9||east>17.35||south<48||north>48.35)return null;
  return {centerCoordinate:[(west+east)/2,(south+north)/2] as [number,number],zoomLevel:Math.min(18,zoom+2),animationDuration:450,animationMode:'easeTo' as const};
}

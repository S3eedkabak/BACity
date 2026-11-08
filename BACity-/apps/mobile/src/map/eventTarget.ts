import { create } from 'zustand';
import { router, useLocalSearchParams, usePathname, type Href } from 'expo-router';
import { eventCoordinates } from './eventLocation';
import { useDistrictMorph } from './districtMorphState';
import type { EventOut } from '../types/event';
export type EventTarget = {id:string;nonce:number;origin:Href};
export const useEventTarget = create<{target:EventTarget|null;setTarget:(target:EventTarget|null)=>void}>(set=>({target:null,setTarget:target=>set({target})}));
let sequence=0;
export function useViewOnMap() {
  const pathname=usePathname();
  const params=useLocalSearchParams();
  return (event:EventOut)=>{
    if(!eventCoordinates(event))return;
    const query={...params};
    for(const key of ['id','type']){const value=query[key];if(typeof value==='string'&&pathname.split('/').includes(value))delete query[key];}
    if (pathname === '/area-events') useDistrictMorph.getState().suspend();
    useEventTarget.getState().setTarget({id:event.id,nonce:++sequence,origin:{pathname,params:query} as Href});
    router.navigate('/(tabs)/map');
  };
}

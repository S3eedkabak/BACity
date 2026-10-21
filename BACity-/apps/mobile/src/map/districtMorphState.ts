import { create } from 'zustand';
import type { ScreenPoint } from './districtMorphGeometry';
import type { areaRoute } from './area';
import type { EventViewportBounds } from '../api/events';

export type MorphPhase = 'idle' | 'selecting' | 'morphing' | 'area-visible' | 'suspended' | 'returning';
export interface MorphViewport {width: number; height: number; originX: number; originY: number; headerHeight: number;}
export interface MorphCameraRestore {
  camera: {centerCoordinate: [number, number]; zoomLevel: number};
  bounds: EventViewportBounds;
}
export interface MorphEntry {
  id: string;
  name: string;
  count: number;
  source: ScreenPoint[];
  target: ScreenPoint[];
  route: ReturnType<typeof areaRoute>;
  savedCamera: {centerCoordinate: [number, number]; zoomLevel: number};
  savedBounds: EventViewportBounds;
}

interface MorphState {
  phase: MorphPhase;
  nonce: number;
  selectingId: string | null;
  entry: MorphEntry | null;
  restore: MorphCameraRestore | null;
  viewport: MorphViewport | null;
  areaMounted: boolean;
  setViewport: (viewport: MorphViewport) => void;
  markAreaMounted: (nonce: number) => void;
  claim: (id: string) => number | null;
  start: (nonce: number, entry: MorphEntry) => boolean;
  areaVisible: (nonce: number) => void;
  suspend: () => void;
  resume: () => void;
  beginReturn: () => boolean;
  finishReturn: () => void;
  cancel: (nonce?: number) => void;
  clearRestore: () => void;
}

export const useDistrictMorph = create<MorphState>((set, get) => ({
  phase: 'idle', nonce: 0, selectingId: null, entry: null, viewport: null, restore: null, areaMounted: false,
  markAreaMounted: nonce => {
    if (get().nonce === nonce && get().phase === 'morphing') set({areaMounted: true});
  },
  setViewport: viewport => {
    const old = get().viewport;
    if (old && Math.abs(old.width - viewport.width) < 1 && Math.abs(old.height - viewport.height) < 1 &&
        Math.abs(old.originX - viewport.originX) < 1 && Math.abs(old.originY - viewport.originY) < 1) return;
    set({viewport});
  },
  claim: id => {
    if (get().phase !== 'idle') return null;
    const nonce = get().nonce + 1;
    set({phase:'selecting', nonce, selectingId:id, entry:null, restore:null, areaMounted:false});
    return nonce;
  },
  start: (nonce, entry) => {
    if (get().phase !== 'selecting' || get().nonce !== nonce || get().selectingId !== entry.id) return false;
    set({phase:'morphing', entry});
    return true;
  },
  areaVisible: nonce => {
    if (get().nonce === nonce && get().phase === 'morphing') set({phase:'area-visible'});
  },
  suspend: () => {
    if (get().phase === 'area-visible') set({phase:'suspended'});
  },
  resume: () => {
    if (get().phase === 'suspended') set({phase:'area-visible'});
  },
  beginReturn: () => {
    if (get().phase !== 'area-visible') return false;
    set({phase:'returning'});
    return true;
  },
  finishReturn: () => {
    if (get().phase === 'returning') set({phase:'idle',selectingId:null,entry:null,areaMounted:false});
  },
  cancel: nonce => {
    if (nonce != null && get().nonce !== nonce) return;
    const entry = get().entry;
    set({phase:'idle', selectingId:null, entry:null, nonce:get().nonce + 1, areaMounted:false,
      restore:entry ? {camera:entry.savedCamera,bounds:entry.savedBounds} : null});
  },
  clearRestore: () => set({restore:null}),
}));

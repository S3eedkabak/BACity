import {create} from 'zustand';
import {sharedEventFilters,type MapFilters} from './area';
import {mapSession} from './session';

export const useMapFiltersStore=create<{filters:MapFilters;setFilters:(value:MapFilters)=>void}>(set=>({
  filters:mapSession.filters,
  setFilters:value=>{const filters=sharedEventFilters(value);mapSession.filters=filters;set(state=>JSON.stringify(state.filters)===JSON.stringify(filters)?state:{filters});},
}));

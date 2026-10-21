import type { MapFilters } from './area';
import type { EventViewportBounds } from '../api/events';

// In-memory navigation context; it survives detail/area routes, without storing GPS.
export const mapSession: {
  filters:MapFilters;bounds:EventViewportBounds|null;zoom:number;
  camera:{centerCoordinate:[number,number];zoomLevel:number}|null;selectedDistrict:string|null;
} = {filters:{},bounds:null,zoom:10,camera:null,selectedDistrict:null};

import type { DistrictData } from '../api/events';

/** MapLibre Native line layers require line geometry. Preserve every official ring. */
export function districtBoundaryLines(data: DistrictData): GeoJSON.FeatureCollection<GeoJSON.LineString> {
  return {type:'FeatureCollection',features:data.features.flatMap(feature=>{
    const rings=feature.geometry.type==='Polygon'
      ? feature.geometry.coordinates
      : feature.geometry.coordinates.flat();
    return rings.map(ring=>({type:'Feature' as const,properties:{id:feature.properties.id},
      geometry:{type:'LineString' as const,coordinates:ring}}));
  })};
}

// A single pink family keeps adjacent official territories legible over Liberty.
// The hues encode geography only; counts and categories stay independent.
export const DISTRICT_INKS: Record<string,string> = {
  '528595':'#DE6BA5','529311':'#D95599','529320':'#E47BAF',
  '529338':'#CA4F92','529346':'#E06EA8','529354':'#D85E9B',
  '529362':'#ED8BBC','529371':'#CE5795','529389':'#E579AD',
  '529397':'#D264A1','529401':'#EC82B5','529419':'#C94E8C',
  '529435':'#DE71A8','529427':'#D45B98','529443':'#E784B5',
  '529460':'#CC5894','529494':'#E175AD',
};

export const districtInkExpression = ['match',['get','id'],...Object.entries(DISTRICT_INKS).flat(), '#DE6BA5'];

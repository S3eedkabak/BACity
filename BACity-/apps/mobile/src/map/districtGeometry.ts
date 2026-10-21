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

// Alternating subdued inks distinguish adjacent territories without replacing
// the Liberty basemap or encoding event category as district color.
export const DISTRICT_INKS: Record<string,string> = {
  '528595':'#A93468','529311':'#6E8590','529320':'#777D60',
  '529338':'#A17863','529346':'#687F9D','529354':'#A98458',
  '529362':'#817496','529371':'#739080','529389':'#9B7368',
  '529397':'#7F7698','529401':'#A18064','529419':'#6F8D8A',
  '529435':'#8C7894','529427':'#77906C','529443':'#AA8068',
  '529460':'#6E8799','529494':'#7C8C72',
};

export const districtInkExpression = ['match',['get','id'],...Object.entries(DISTRICT_INKS).flat(), '#A93468'];

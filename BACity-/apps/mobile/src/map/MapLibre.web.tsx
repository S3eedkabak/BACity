import { layerSpec } from './layerSpec';
/** Web adapter for the original native map screen; uses its exact mapStyle. */
import React, { createContext, forwardRef, useContext, useEffect, useImperativeHandle, useRef, useState } from 'react';
import type { Map as GLMap, GeoJSONSource, MapGeoJSONFeature } from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';

const MapContext = createContext<{map:GLMap|null;revision:number;handlers:React.MutableRefObject<Map<string,(features:any[])=>void>>}>({map:null,revision:0,handlers:{current:new Map()}});
const SourceContext = createContext('');
export const UserTrackingMode = {Follow:'follow'};
export const OfflineManager = {setMaximumAmbientCacheSize:async (_size:number)=>undefined};

export const MapView = forwardRef<any,any>(function MapView(props,ref) {
  const host = useRef<HTMLDivElement>(null);
  const handlers = useRef(new Map<string,(features:any[])=>void>());
  const [map,setMap] = useState<GLMap|null>(null); const [revision,setRevision] = useState(0);
  const latest = useRef(props); latest.current=props;
  useImperativeHandle(ref,()=>({
    getVisibleBounds:async()=>{const b=map!.getBounds();return [[b.getEast(),b.getNorth()],[b.getWest(),b.getSouth()]];},
    getZoom:async()=>map!.getZoom(),
    getCenter:async()=>{const c=map!.getCenter();return [c.lng,c.lat];},
  }),[map]);
  useEffect(()=>{
    let cancelled=false;let loaded=false;let instance:GLMap|undefined;let timer:ReturnType<typeof setTimeout>;
    Promise.resolve(require('maplibre-gl') as typeof import('maplibre-gl')).then(({Map})=>{
      if(cancelled||!host.current)return;
      instance=new Map({container:host.current,style:latest.current.mapStyle,center:[17.1077,48.1486],zoom:12,
        attributionControl:{},dragRotate:false,pitchWithRotate:false,renderWorldCopies:false});
      instance.touchZoomRotate.disableRotation();
      instance.on('load',()=>{if(cancelled)return;loaded=true;setMap(instance!);latest.current.onDidFinishLoadingMap?.();});
      instance.on('idle',()=>{setRevision(v=>v+1);latest.current.onDidFinishRenderingFrameFully?.();});
      instance.on('click',event=>{
        const hits=instance!.queryRenderedFeatures([[event.point.x-10,event.point.y-10],[event.point.x+10,event.point.y+10]]).filter(f=>handlers.current.has(String(f.source)));
        const selected=hits.find(f=>f.geometry.type==='Point')||hits[0];
        if(selected)handlers.current.get(String(selected.source))?.([selected]);
      });
      instance.on('movestart',()=>latest.current.onRegionWillChange?.());
      instance.on('moveend',()=>{setRevision(v=>v+1);clearTimeout(timer);timer=setTimeout(()=>latest.current.onRegionDidChange?.(),latest.current.regionDidChangeDebounceTime??700);});
      instance.on('error',event=>{console.warn('[map:resource]',event.error?.message||'Map resource unavailable');if(!loaded)latest.current.onDidFailLoadingMap?.();});
    }).catch(()=>latest.current.onDidFailLoadingMap?.());
    return()=>{cancelled=true;clearTimeout(timer);instance?.remove();};
  },[]);
  return <div style={{position:'absolute',inset:0}}><div ref={host} aria-label="Bratislava map" style={{position:'absolute',inset:0}}/><MapContext.Provider value={{map,revision,handlers}}>{props.children}</MapContext.Provider></div>;
});

export const Camera = forwardRef<any,any>(function Camera(props,ref) {
  const {map}=useContext(MapContext);
  useEffect(()=>{if(map&&props.defaultSettings)map.jumpTo({center:props.defaultSettings.centerCoordinate,zoom:props.defaultSettings.zoomLevel});},[map]);
  useImperativeHandle(ref,()=>({
    setCamera:({centerCoordinate,zoomLevel,animationDuration=0}:any)=>map?.easeTo({center:centerCoordinate,zoom:zoomLevel,duration:animationDuration}),
    fitBounds:(ne:any,sw:any,padding=40,duration=350)=>map?.fitBounds([sw,ne],{padding,duration,maxZoom:19}),
  }),[map]);

  return null;
});

export function UserLocation(props:any) {
  const {map}=useContext(MapContext);const latest=useRef(props);latest.current=props;
  useEffect(()=>{
    if(!props.visible||!map||!navigator.geolocation)return;
    let marker:import('maplibre-gl').Marker|undefined;
    const watch=navigator.geolocation.watchPosition(position=>{
      latest.current.onUpdate?.({coords:position.coords});
      const location:[number,number]=[position.coords.longitude,position.coords.latitude];
      if(marker)marker.setLngLat(location);
      else {const {Marker}=require('maplibre-gl') as typeof import('maplibre-gl');marker=new Marker({color:'#4285F4'}).setLngLat(location).addTo(map);}
      map.easeTo({center:location,zoom:15,duration:700});
    },()=>undefined,{maximumAge:60000,timeout:10000});
    return()=>{navigator.geolocation.clearWatch(watch);marker?.remove();};
  },[props.visible,map]);
  return null;
}

export const ShapeSource = forwardRef<any,any>(function ShapeSource(props,ref) {
  const {map,revision,handlers}=useContext(MapContext);const [sourceMap,setSourceMap]=useState<GLMap|null>(null);
  const ready=map!==null&&sourceMap===map;
  const latest=useRef(props);latest.current=props;
  useImperativeHandle(ref,()=>({
    getClusterExpansionZoom:async(feature:any)=>(map?.getSource(props.id) as GeoJSONSource).getClusterExpansionZoom(feature.properties.cluster_id),
    features:async()=>({type:'FeatureCollection',features:map?.querySourceFeatures(props.id)||[]}),
  }),[map,props.id]);
  useEffect(()=>{
    if(!map)return;
    map.addSource(props.id,{type:'geojson',data:latest.current.shape,cluster:!!props.cluster,
      clusterRadius:props.clusterRadius,clusterMaxZoom:props.clusterMaxZoomLevel});
    setSourceMap(map);
    if(latest.current.onPress)handlers.current.set(props.id,features=>latest.current.onPress?.({features}));
    return()=>{
      handlers.current.delete(props.id);
      if(!map.getStyle())return;
      for(const layer of map.getStyle()?.layers||[])if('source' in layer&&layer.source===props.id)map.removeLayer(layer.id);
      if(map.getSource(props.id))map.removeSource(props.id);
    };
  },[map,props.id]);
  useEffect(()=>{if(ready)(map?.getSource(props.id) as GeoJSONSource)?.setData(props.shape);},[map,ready,props.shape,props.id]);
  // Keyboard/screen-reader hit targets mirror the existing GPU event features.
  const rendered=ready&&props.cluster?map!.queryRenderedFeatures().filter(f=>f.source===props.id):props.shape.features;
  const targets=props.onPress?Array.from(new Map<string,any>((ready?rendered:[]).filter((f:any)=>f.geometry.type==='Point').map((f:any)=>[String(f.properties.cluster_id??f.properties.id??f.id),f])).values()):[];
  return <SourceContext.Provider value={props.id}>{ready&&props.children}{targets.map((feature:any)=>{
    const point=map!.project(feature.geometry.coordinates);const count=feature.properties.count||feature.properties.point_count||1;
    if(point.x<0||point.y<0||point.x>map!.getCanvas().clientWidth||point.y>map!.getCanvas().clientHeight)return null;
    return <button key={`${props.id}:${feature.properties.cluster_id??feature.properties.id??feature.id}`} aria-label={props.id==='public-toilets'?(count>1?`Expand ${count} toilets`:`Open toilet ${feature.properties.name||''}`):count>1?`Browse ${count} events near this area`:'Open event'}
      style={{position:'absolute',left:point.x-22,top:point.y-22,width:44,height:44,opacity:0,cursor:'pointer',border:0}}
      onClick={event=>{event.stopPropagation();latest.current.onPress?.({features:[feature]});}}/>;
  })}</SourceContext.Provider>;
});

function Layer({id,filter,style,aboveLayerID,belowLayerID,type}:any) {
  const {map}=useContext(MapContext);const source=useContext(SourceContext);
  useEffect(()=>{
    if(!map||!map.getSource(source))return;
    const layers=map.getStyle().layers||[];
    const position=layers.findIndex(layer=>layer.id===aboveLayerID);
    const before=belowLayerID&&map.getLayer(belowLayerID)?belowLayerID:position>=0?layers[position+1]?.id:(type==='fill'||type==='line')?layers.find(layer=>layer.type==='symbol')?.id:undefined;
    map.addLayer(layerSpec(id,type,source,style,filter) as any,before);
    return()=>{if(map.getStyle()&&map.getLayer(id))map.removeLayer(id);};
  },[map,id,source,JSON.stringify(filter),JSON.stringify(style),aboveLayerID,belowLayerID,type]);
  return null;
}
export const CircleLayer=(props:any)=><Layer {...props} type="circle"/>;
export const SymbolLayer=(props:any)=><Layer {...props} type="symbol"/>;
export const FillLayer=(props:any)=><Layer {...props} type="fill"/>;
export const LineLayer=(props:any)=><Layer {...props} type="line"/>;

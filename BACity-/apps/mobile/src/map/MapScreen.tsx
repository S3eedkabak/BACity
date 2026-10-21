import { useEventTarget } from './eventTarget';
import { eventCoordinates } from './eventLocation';
import { EventCard } from '../components/EventCard';
import { useReducedMotion } from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';
import { Reveal } from '../components/motion/Motion';
import { useMapFiltersStore } from './filterStore';
import { loadClusterSnapshot, saveClusterSnapshot, type ClusterSnapshot } from './clusterCache';
import { mapSession } from './session';
import { OverflowMenu, ListItem } from '../components/SocialUI';
import { trimMapQueries } from './queryCache';
import { AppIcon } from "../components/AppIcon";
import type {
  CameraRef,
  MapViewRef,
  ShapeSourceRef,
} from "@maplibre/maplibre-react-native";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useIsFocused } from "@react-navigation/native";
import { ActivityIndicator, Dimensions, Platform, StyleSheet, Text, View } from "react-native";
import { AnimatedPressable as Pressable } from '../components/motion/Motion';
import { colors } from "../theme/colors";
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { fonts } from "../theme/fonts";
import { nearbyUtilities, utilitiesInViewport, type UtilityBounds } from "../api/utilities";
import { areaEvents, getEvent, mapClusters, mapDistricts } from "../api/events";
import type { Utility } from "../api/utilities";
import {
  boundsKey,
  containsBounds,
  expandAndSnapBounds,
  loadMapSnapshot,
  mergeViewportUtilities,
  updateMapSnapshot,
} from "./mapCache";
import { EMPTY_MAP, areaRoute, clusterProperties, clusterCamera, type MapFilters as Filters, type MapProperties } from './area';
import { MapFilters } from './MapFilters';
import { districtBoundaryLines, districtInkExpression } from './districtGeometry';
import { morphRings, type ProjectionFrame } from './districtMorphGeometry';
import { useDistrictMorph } from './districtMorphState';
import { useMajorTransition } from "../components/loading/LoadingExperience";

// Expo Router evaluates route modules while building its web route context. Avoid
// initializing the native MapLibre bridge during that discovery pass.
const nativeMapLibre = require('./MapLibre') as typeof import('@maplibre/maplibre-react-native');

const {
  Camera,
  CircleLayer,
  FillLayer,
  LineLayer,
  MapView,
  ShapeSource,
  SymbolLayer,
  UserLocation,
  UserTrackingMode,
  OfflineManager,
} = nativeMapLibre ?? ({} as typeof import("@maplibre/maplibre-react-native"));

const BRATISLAVA = {
  longitude: 17.1077,
  latitude: 48.1486,
};

const OPEN_FREE_MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const NEARBY_RADIUS_KM = 3;
const INITIAL_VIEWPORT: UtilityBounds = {
  min_lat: 48.105,
  max_lat: 48.205,
  min_lng: 17.035,
  max_lng: 17.185,
};
const INITIAL_BOUNDS = expandAndSnapBounds(INITIAL_VIEWPORT);
const MAP_DATA_STALE_MS = 5 * 60_000;
const MAP_QUERY_GC_MS = 30 * 60_000;
const AMBIENT_TILE_CACHE_BYTES = 75 * 1024 * 1024;
let ambientCacheConfigured = false;

type Coordinates = {
  latitude: number;
  longitude: number;
};

function distanceKm(a: Coordinates, b: Coordinates) {
  const earthRadiusKm = 6371;
  const lat1 = (a.latitude * Math.PI) / 180;
  const lat2 = (b.latitude * Math.PI) / 180;
  const deltaLat = ((b.latitude - a.latitude) * Math.PI) / 180;
  const deltaLng = ((b.longitude - a.longitude) * Math.PI) / 180;

  const haversine =
    Math.sin(deltaLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLng / 2) ** 2;

  return 2 * earthRadiusKm * Math.asin(Math.sqrt(haversine));
}

export default function MapScreen() {
  const queryClient = useQueryClient();
  const focused = useIsFocused();
  const target=useEventTarget(state=>state.target);
  const reducedMotion=useReducedMotion();
  const focusedEvent=useQuery({queryKey:['map-target',target?.id],queryFn:()=>getEvent(target!.id),enabled:!!target,staleTime:30000});
  const targetCameraApplied=useRef<number|null>(null);
  const [previewHeight,setPreviewHeight]=useState(0);
  const browseCamera=useRef<typeof mapSession.camera>(null);
  const targetPoint=focusedEvent.data?eventCoordinates(focusedEvent.data):null;

  const major = useMajorTransition();
  const insets = useSafeAreaInsets();
  const cameraRef = useRef<CameraRef>(null);
  const mapRef = useRef<MapViewRef>(null);
  const mapRootRef = useRef<View>(null);
  const eventSourceRef = useRef<ShapeSourceRef>(null);
  const utilitySourceRef = useRef<ShapeSourceRef>(null);
  const requestedBoundsRef = useRef(mapSession.bounds??INITIAL_BOUNDS);
  const cameraRequest = useRef(0);
  const utilityRequestedBounds=useRef(mapSession.bounds??INITIAL_BOUNDS);
  const [nearMeActive, setNearMeActive] = useState(false);
  const [showUtilities, setShowUtilities] = useState(false);
  const [utilityBounds,setUtilityBounds]=useState(mapSession.bounds??INITIAL_BOUNDS);
  const [mapBounds, setMapBounds] = useState(mapSession.bounds??INITIAL_BOUNDS);
  const [zoomLevel,setZoomLevel] = useState(mapSession.zoom);
  const filters=useMapFiltersStore(state=>state.filters);
  const setFilters=useMapFiltersStore(state=>state.setFilters);
  const [activeFilters,setActiveFilters] = useState<Filters>(mapSession.filters);
  const [selectedDistrict,setSelectedDistrict] = useState<string|null>(mapSession.selectedDistrict);
  const morphPhase=useDistrictMorph(state=>state.phase);
  const morphEntry=useDistrictMorph(state=>state.entry);
  const morphRestore=useDistrictMorph(state=>state.restore);
  const markerPressedAt=useRef(0);
  const districtNavigation=useRef<ReturnType<typeof setTimeout>|null>(null);
  const [filtersOpen,setFiltersOpen] = useState(false);
  const initialCamera = useRef(mapSession.camera);
  useEffect(()=>{mapSession.filters=filters;mapSession.selectedDistrict=selectedDistrict;if(!target){mapSession.bounds=mapBounds;mapSession.zoom=zoomLevel;}},[filters,mapBounds,zoomLevel,selectedDistrict,target]);
  const [selectedCluster,setSelectedCluster] = useState<MapProperties|null>(null);
  useEffect(()=>{setSelectedCluster(null);const t=setTimeout(()=>setActiveFilters(filters),300);return()=>clearTimeout(t);},[filters]);
  const [cachedUtilities, setCachedUtilities] = useState<Utility[]>([]);
  const [savedClusters,setSavedClusters]=useState<ClusterSnapshot|null>(null);
  const lastNormalShape=useRef<{filters:string;data:typeof EMPTY_MAP}|null>(null);
  const [cacheSavedAt, setCacheSavedAt] = useState(0);
  const [basemapUnavailable, setBasemapUnavailable] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [currentLocation, setCurrentLocation] = useState<Coordinates | null>(
    null
  );

  useEffect(()=>{
    if(!target||!focused||!mapReady||!targetPoint||targetCameraApplied.current===target.nonce)return;
    if(targetCameraApplied.current==null)browseCamera.current=mapSession.camera;
    targetCameraApplied.current=target.nonce;
    cameraRequest.current++;
    cameraRef.current?.setCamera({centerCoordinate:targetPoint,zoomLevel:17,animationDuration:reducedMotion?0:450,animationMode:'easeTo'});
  },[target,focused,mapReady,targetPoint?.[0],targetPoint?.[1],reducedMotion]);
  function closeTarget(returnToOrigin:boolean) {
    const origin=target?.origin;
    cameraRequest.current++;
    const previous=browseCamera.current;
    useEventTarget.getState().setTarget(null);
    targetCameraApplied.current=null;
    const restored=previous??{centerCoordinate:[BRATISLAVA.longitude,BRATISLAVA.latitude] as [number,number],zoomLevel:12};
    mapSession.camera=restored;
    cameraRef.current?.setCamera({...restored,animationDuration:returnToOrigin||reducedMotion?0:350,animationMode:'easeTo'});
    if(mapSession.bounds){requestedBoundsRef.current=mapSession.bounds;setMapBounds(mapSession.bounds);setZoomLevel(mapSession.zoom);}
    if(returnToOrigin&&origin){
      useDistrictMorph.getState().resume();
      router.navigate(origin);
    } else if (useDistrictMorph.getState().phase === 'suspended') {
      useDistrictMorph.getState().cancel();
    }
  }

  // The map remains mounted below Area Events. Restore its exact browsing view
  // behind the opaque morph surface so the reverse reveals the original city.
  useEffect(() => {
    if (morphPhase !== 'returning' || !morphEntry || morphEntry.id !== selectedDistrict) return;
    const previous = morphEntry.savedCamera;
    mapSession.camera = previous;
    mapSession.bounds = morphEntry.savedBounds;
    mapSession.zoom = previous.zoomLevel;
    requestedBoundsRef.current = morphEntry.savedBounds;
    setMapBounds(morphEntry.savedBounds);
    setZoomLevel(previous.zoomLevel);
    cameraRequest.current++;
    cameraRef.current?.setCamera({...previous,animationDuration:0});
  }, [morphPhase,morphEntry?.id,selectedDistrict]);

  useEffect(() => {
    if (morphPhase !== 'idle' || !morphRestore) return;
    mapSession.camera = morphRestore.camera;
    mapSession.bounds = morphRestore.bounds;
    mapSession.zoom = morphRestore.camera.zoomLevel;
    requestedBoundsRef.current = morphRestore.bounds;
    setMapBounds(morphRestore.bounds);
    setZoomLevel(morphRestore.camera.zoomLevel);
    cameraRequest.current++;
    cameraRef.current?.setCamera({...morphRestore.camera,animationDuration:reducedMotion?0:240,animationMode:'easeTo'});
    useDistrictMorph.getState().clearRestore();
  }, [morphPhase,morphRestore,reducedMotion]);

  useEffect(() => {
    if (focused && mapReady) major.finish('map');
  }, [focused, mapReady, major]);
  useEffect(() => {
    if (!focused || mapReady) return;
    // Never trap navigation if MapLibre/provider fails to emit a readiness event.
    const timer = setTimeout(() => major.finish('map'), 8_000);
    return () => clearTimeout(timer);
  }, [focused, mapReady, major]);
  useEffect(() => () => major.finish('map'), [major]);

  useEffect(() => {
    let active = true;
    void loadMapSnapshot().then((snapshot) => {
      if (!active) return;
      setCachedUtilities(snapshot.utilities);
      setCacheSavedAt(snapshot.savedAt);
    });
    return () => { active = false; };
  }, []);

  useEffect(()=>{let active=true;void loadClusterSnapshot().then(value=>{if(active&&value){setSavedClusters(value);setCacheSavedAt(value.savedAt);}});return()=>{active=false;};},[]);

  useEffect(() => {
    if (ambientCacheConfigured || !OfflineManager) return;
    ambientCacheConfigured = true;
    void OfflineManager.setMaximumAmbientCacheSize(AMBIENT_TILE_CACHE_BYTES).catch(() => {
      ambientCacheConfigured = false;
    });
  }, []);

  const roundedLocation = useMemo(() => currentLocation ? {
    latitude: Number(currentLocation.latitude.toFixed(3)),
    longitude: Number(currentLocation.longitude.toFixed(3)),
  } : null, [currentLocation]);

  const eventBounds = mapBounds;
  const eventFilters = nearMeActive && roundedLocation ? {...activeFilters,near_lat:roundedLocation.latitude,near_lng:roundedLocation.longitude,radius_km:NEARBY_RADIUS_KM} : activeFilters;
  const nearbySummary=useQuery({queryKey:['map-nearby-identities',roundedLocation,activeFilters],
    queryFn:({signal})=>mapClusters({min_lat:roundedLocation!.latitude-.03,max_lat:roundedLocation!.latitude+.03,
      min_lng:roundedLocation!.longitude-.045,max_lng:roundedLocation!.longitude+.045},0,eventFilters,signal),
    enabled:nearMeActive&&roundedLocation!=null,staleTime:2*60_000,gcTime:60000});
  const allCityQuery = useQuery({queryKey:['map-identities','all-city',eventFilters],
    queryFn:({signal})=>mapClusters({min_lat:48,max_lat:48.35,min_lng:16.9,max_lng:17.35},0,eventFilters,signal),
    enabled:filtersOpen&&!nearMeActive,staleTime:30000,gcTime:60000});
  const browseSummary=nearMeActive?nearbySummary:allCityQuery;
  const districtQuery = useQuery({queryKey:['map-district-identities',eventFilters],
    queryFn:({signal})=>mapDistricts(eventFilters,signal),enabled:zoomLevel<=14||selectedDistrict!=null,staleTime:30000,gcTime:60000,refetchInterval:focused?60000:false});
  const districtLines=useMemo(()=>districtQuery.data?districtBoundaryLines(districtQuery.data):null,[districtQuery.data]);
  useEffect(()=>()=>{if(districtNavigation.current)clearTimeout(districtNavigation.current);},[]);
  function openDistrict(properties:any) {
    router.push(areaRoute(properties.area_token,{...eventFilters,district:String(properties.id)}));
  }
  async function selectDistrict(properties:any,point?:{x:number;y:number}) {
    if(!properties?.id||zoomLevel>14||target)return;
    if(Platform.OS!=='web'&&useDistrictMorph.getState().phase!=='idle')return;
    const revision=cameraRequest.current;
    const markerLayers=targetPoint?['focused-event-point']:showUtilities?['toilet-points','toilet-clusters']:nearMeActive?['event-points','event-clusters']:[];
    if(Platform.OS!=='web'&&point&&mapRef.current&&markerLayers.length){
      try {
        const hits=await mapRef.current.queryRenderedFeaturesAtPoint([point.x,point.y],undefined,markerLayers);
        if(hits.features.length||revision!==cameraRequest.current)return;
      }catch{return;}
    }
    if(revision!==cameraRequest.current||Date.now()-markerPressedAt.current<100)return;
    if(districtNavigation.current)clearTimeout(districtNavigation.current);
    setSelectedDistrict(String(properties.id));
    if(Platform.OS!=='ios') {
      if(Platform.OS!=='web')void Haptics.selectionAsync().catch(()=>undefined);
      districtNavigation.current=setTimeout(()=>{
        districtNavigation.current=null;
        if(revision===cameraRequest.current)openDistrict(properties);
      },reducedMotion?0:230);
      return;
    }
    const morph=useDistrictMorph.getState();
    const nonce=morph.claim(String(properties.id));
    if(nonce==null)return;
    void Haptics.selectionAsync().catch(()=>undefined);
    const feature=districtQuery.data?.features.find(item=>String(item.properties.id)===String(properties.id));
    const window=Dimensions.get('window');
    const viewport=morph.viewport??{width:window.width,height:window.height,originX:0,originY:0,
      headerHeight:Math.min(260,Math.max(224,window.height*.29))};
    if(!morph.viewport)morph.setViewport(viewport);
    if(!feature||!mapRef.current||!mapRootRef.current){
      morph.cancel(nonce);openDistrict(properties);return;
    }
    try {
      const anchor=feature.properties.label_coordinates;
      const delta=.01;
      const map=mapRef.current;
      const [anchorPoint,eastPoint,northPoint,mapOrigin]=await Promise.all([
        map.getPointInView(anchor),map.getPointInView([anchor[0]+delta,anchor[1]]),
        map.getPointInView([anchor[0],anchor[1]+delta]),
        new Promise<[number,number]>(resolve=>{
          const node=mapRootRef.current;
          if(node)node.measureInWindow((x,y)=>resolve([x,y]));
          else resolve([0,0]);
        }),
      ]);
      if(revision!==cameraRequest.current||useDistrictMorph.getState().nonce!==nonce){morph.cancel(nonce);return;}
      const projection:ProjectionFrame={anchor,anchorPoint,eastPoint,northPoint,
        mapOffset:[mapOrigin[0]-viewport.originX,mapOrigin[1]-viewport.originY],delta};
      const geometry=morphRings(feature,projection,viewport);
      if(!geometry){morph.cancel(nonce);openDistrict(properties);return;}
      const savedCamera=mapSession.camera??{centerCoordinate:[BRATISLAVA.longitude,BRATISLAVA.latitude] as [number,number],zoomLevel};
      const route=areaRoute(properties.area_token,{...eventFilters,district:String(properties.id)});
      if(!morph.start(nonce,{id:String(properties.id),name:String(properties.name),count:Number(properties.count),
        source:geometry.source,target:geometry.target,route,savedCamera,savedBounds:mapBounds}))return;
      // Fetch before navigation; the shared-surface animation never waits for it.
      void queryClient.prefetchInfiniteQuery({queryKey:['area-events',route.params.area,{...eventFilters,district:String(properties.id)}],
        initialPageParam:undefined as string|undefined,
        queryFn:({pageParam,signal})=>areaEvents(route.params.area,{...eventFilters,district:String(properties.id)},pageParam,signal),
        getNextPageParam:(page:Awaited<ReturnType<typeof areaEvents>>)=>page.next_cursor||undefined,staleTime:30000}).catch(()=>undefined);
      const [west,south,east,north]=geometry.bounds;
      cameraRequest.current++;
      cameraRef.current?.setCamera({bounds:{ne:[east,north],sw:[west,south]},
        padding:{paddingTop:90,paddingRight:34,paddingBottom:110,paddingLeft:34},
        animationDuration:reducedMotion?0:640,animationMode:'easeTo'});
    } catch {
      morph.cancel(nonce);
      openDistrict(properties);
    }
  }
  const clusterKey=JSON.stringify([boundsKey(eventBounds),zoomLevel,eventFilters]);
  const eventViewport = useQuery({
    queryKey:['map-identities',boundsKey(eventBounds),zoomLevel,eventFilters],
    queryFn:({signal})=>mapClusters(eventBounds,zoomLevel,eventFilters,signal),
    enabled:!nearMeActive||roundedLocation!=null,staleTime:30000,gcTime:60000,refetchOnWindowFocus:false,refetchInterval:focused?60000:false,
    placeholderData:(previous,query)=>JSON.stringify(query?.queryKey[3])===JSON.stringify(eventFilters)?previous:undefined,
  });
  useEffect(()=>{
    if(!focused)return;
    if(!nearMeActive||roundedLocation)void eventViewport.refetch();
    if(zoomLevel<=14)void districtQuery.refetch();
  },[focused]);
  useEffect(()=>trimMapQueries(queryClient),[eventViewport.data,mapBounds,zoomLevel,activeFilters,queryClient]);
  useEffect(()=>{
    if(!nearMeActive&&eventViewport.data&&!eventViewport.isPlaceholderData){
      const snapshot=saveClusterSnapshot(clusterKey,eventViewport.data);
      setSavedClusters(snapshot);setCacheSavedAt(snapshot.savedAt);
      lastNormalShape.current={filters:JSON.stringify(activeFilters),data:eventViewport.data};
    }
  },[eventViewport.data,eventViewport.isPlaceholderData,clusterKey,nearMeActive,activeFilters]);
  const eventShape = useMemo(()=>{
    const fallback=!nearMeActive&&savedClusters?.key===clusterKey?savedClusters.data:EMPTY_MAP;
    const data=filters!==activeFilters||(nearMeActive&&!roundedLocation)?EMPTY_MAP:eventViewport.data??fallback;
    const context=nearMeActive&&lastNormalShape.current?.filters===JSON.stringify(activeFilters)
      ?lastNormalShape.current.data.features.filter(feature=>{
        const [lng,lat]=feature.geometry.coordinates;
        return !roundedLocation||lat<eventBounds.min_lat||lat>eventBounds.max_lat||lng<eventBounds.min_lng||lng>eventBounds.max_lng;
      }).map(feature=>({...feature,properties:{...feature.properties,nearby:false}})):[];
    return {...data,features:[...context,...data.features.map(feature=>({...feature,properties:{...feature.properties,
      nearby:nearMeActive||!!currentLocation&&distanceKm(currentLocation,{latitude:feature.geometry.coordinates[1],longitude:feature.geometry.coordinates[0]})<=NEARBY_RADIUS_KM}}))]};
  },[eventViewport.data,filters,activeFilters,currentLocation,nearMeActive,clusterKey,savedClusters]);
  const eventTotal=nearMeActive?(nearbySummary.data?.total??0):eventShape.total;
  const areaToken=nearMeActive?nearbySummary.data?.area_token:eventShape.area_token;
  const pins = eventShape.features;
  const nearbyPins = pins;

  const utilityViewport = useQuery({
    queryKey: ["map-utilities-viewport", boundsKey(utilityBounds)],
    queryFn: () => utilitiesInViewport(utilityBounds),
    enabled: showUtilities && !nearMeActive,
    staleTime: MAP_DATA_STALE_MS,
    gcTime: MAP_QUERY_GC_MS,
    placeholderData: (previous) => previous,
    refetchOnWindowFocus: false,
  });
  const utilityNearby = useQuery({
    queryKey: ["map-utilities-nearby", roundedLocation?.latitude, roundedLocation?.longitude, NEARBY_RADIUS_KM],
    queryFn: () => nearbyUtilities(roundedLocation!.latitude, roundedLocation!.longitude, NEARBY_RADIUS_KM),
    enabled: showUtilities && nearMeActive && roundedLocation != null,
    staleTime: 2 * 60_000,
    gcTime: MAP_QUERY_GC_MS,
    placeholderData: (previous) => previous,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!utilityViewport.data || utilityViewport.isPlaceholderData) return;
    setCachedUtilities((current) => {
      const merged = mergeViewportUtilities(current, utilityViewport.data, utilityBounds);
      const snapshot = updateMapSnapshot({ utilities: merged });
      setCacheSavedAt(snapshot.savedAt);
      return merged;
    });
  }, [utilityBounds, utilityViewport.data, utilityViewport.isPlaceholderData]);

  useEffect(() => {
    if (!utilityNearby.data || utilityNearby.isPlaceholderData) return;
    setCachedUtilities((current) => {
      const mergedById = new Map(current.map((item) => [item.id, item]));
      for (const item of utilityNearby.data) mergedById.set(item.id, item);
      const merged = Array.from(mergedById.values()).slice(-1_000);
      const snapshot = updateMapSnapshot({ utilities: merged });
      setCacheSavedAt(snapshot.savedAt);
      return merged;
    });
  }, [utilityNearby.data, utilityNearby.isPlaceholderData]);

  const cachedNearbyUtilities = useMemo(() => roundedLocation
    ? cachedUtilities.filter((utility) => distanceKm(roundedLocation, utility) <= NEARBY_RADIUS_KM)
    : [], [cachedUtilities, roundedLocation]);
  const utilities = nearMeActive
    ? utilityNearby.data ?? cachedNearbyUtilities
    : cachedUtilities.length ? cachedUtilities : utilityViewport.data ?? [];

  const utilityShape = useMemo(() => ({
    type: "FeatureCollection" as const,
    features: utilities.map((utility) => ({
      type: "Feature" as const,
      geometry: { type: "Point" as const, coordinates: [utility.longitude, utility.latitude] },
      properties: { id: utility.id, kind: utility.kind, name: utility.name, status: utility.operational_status },
    })),
  }), [utilities]);

  const activeUtilityQuery = nearMeActive ? utilityNearby : utilityViewport;
  const activeEventQuery = eventViewport;
  const isRefreshing = showUtilities ? activeUtilityQuery.isFetching : activeEventQuery.isFetching||filters!==activeFilters||(nearMeActive&&nearbySummary.isFetching);
  const dataUnavailable = showUtilities ? activeUtilityQuery.isError : activeEventQuery.isError;
  const hasCachedLayer = showUtilities ? utilities.length > 0 : pins.length > 0;
  const cacheIsOld = cacheSavedAt > 0 && Date.now() - cacheSavedAt > MAP_DATA_STALE_MS;

  const recenter = () => {
    if (nearMeActive && currentLocation) {
      cameraRef.current?.setCamera({
        centerCoordinate: [currentLocation.longitude, currentLocation.latitude],
        zoomLevel: 15,
        animationDuration: 700,
        animationMode: "easeTo",
      });
      return;
    }

    cameraRef.current?.setCamera({
      centerCoordinate: [BRATISLAVA.longitude, BRATISLAVA.latitude],
      zoomLevel: 12,
      animationDuration: 700,
      animationMode: "easeTo",
    });
  };

  const zoom = (direction: "in" | "out") => {
    cameraRef.current?.setCamera({
      zoomLevel: direction === "in" ? 14 : 10,
      animationDuration: 250,
      animationMode: "easeTo",
    });
  };

  const toggleNearMe = () => {
    const next = !nearMeActive;
    setNearMeActive(next);

    if (next && currentLocation) {
      cameraRef.current?.setCamera({
        centerCoordinate: [currentLocation.longitude, currentLocation.latitude],
        zoomLevel: 15,
        animationDuration: 700,
        animationMode: "easeTo",
      });
    }
  };

  const handleRegionDidChange = useCallback(async () => {
    if (!mapRef.current) return;
    const revision = ++cameraRequest.current;
    setSelectedCluster(null);
    try {
      const nextZoom=Math.max(0,Math.min(22,Math.floor(await mapRef.current.getZoom())));
      const zoomChanged=nextZoom!==zoomLevel;
      setZoomLevel(nextZoom);
      const [northEast, southWest] = await mapRef.current.getVisibleBounds();
      if (revision!==cameraRequest.current) return;
      if(!nearMeActive&&!target){const center=await mapRef.current.getCenter();if(revision!==cameraRequest.current)return;mapSession.camera={centerCoordinate:center as [number,number],zoomLevel:nextZoom};}
      const visibleBounds: UtilityBounds = {
        min_lat: southWest[1], max_lat: northEast[1],
        min_lng: southWest[0], max_lng: northEast[0],
      };
      if(!containsBounds(utilityRequestedBounds.current,visibleBounds)){
        const next=expandAndSnapBounds(visibleBounds);utilityRequestedBounds.current=next;setUtilityBounds(next);
      }
      if (!zoomChanged&&containsBounds(requestedBoundsRef.current, visibleBounds)) return;
      const nextBounds = expandAndSnapBounds(visibleBounds);
      if (boundsKey(nextBounds) === boundsKey(requestedBoundsRef.current)) return;
      requestedBoundsRef.current = nextBounds;
      setMapBounds(nextBounds);
    } catch {
      // A camera can disappear while an async native bounds request is resolving.
    }
  }, [nearMeActive,zoomLevel,target]);

  const toggleLayer = useCallback(async () => {
    if (showUtilities) {
      setShowUtilities(false);
      return;
    }
    if (!nearMeActive && mapRef.current) {
      try {
        const [northEast, southWest] = await mapRef.current.getVisibleBounds();
        const nextBounds = expandAndSnapBounds({
          min_lat: southWest[1], max_lat: northEast[1],
          min_lng: southWest[0], max_lng: northEast[0],
        });
        utilityRequestedBounds.current = nextBounds;
        setUtilityBounds(nextBounds);
      } catch {
        // Fall back to the last useful viewport while the native map settles.
      }
    }
    setShowUtilities(true);
  }, [nearMeActive, showUtilities]);

  const expandCluster = useCallback(async (
    feature: GeoJSON.Feature,
    sourceRef: React.RefObject<ShapeSourceRef>,
  ) => {
    try {
      if (feature.geometry.type !== "Point" || !sourceRef.current) return;
      const zoomLevel = await sourceRef.current.getClusterExpansionZoom(feature);
      cameraRef.current?.setCamera({
        centerCoordinate: feature.geometry.coordinates as [number, number],
        zoomLevel,
        animationDuration: 280,
        animationMode: "easeTo",
      });
    } catch {
      // The source can be replaced while the native cluster query is resolving.
    }
  }, []);

  return (
    <View ref={mapRootRef} style={styles.container}>
      <MapView
        ref={mapRef}
        style={StyleSheet.absoluteFillObject}
        mapStyle={OPEN_FREE_MAP_STYLE}
        compassEnabled={false}
        rotateEnabled={false}
        pitchEnabled={false}
        attributionEnabled
        logoEnabled
        regionDidChangeDebounceTime={700}
        onRegionWillChange={()=>{
          cameraRequest.current++;
          if(districtNavigation.current){clearTimeout(districtNavigation.current);districtNavigation.current=null;}
          const morph=useDistrictMorph.getState();
          if(morph.phase==='selecting'){morph.cancel(morph.nonce);setSelectedDistrict(null);}
        }}
        onRegionDidChange={handleRegionDidChange}
        onDidFinishLoadingMap={() => {
          setBasemapUnavailable(false);
          setMapReady(true);
        }}
        onDidFinishRenderingFrameFully={() => {
          setBasemapUnavailable(false);
          setMapReady(true);
        }}
        onDidFailLoadingMap={() => {
          setBasemapUnavailable(true);
          setMapReady(false);
          major.finish('map');
        }}
      >
        <Camera
          ref={cameraRef}
          defaultSettings={initialCamera.current??{
            centerCoordinate: [BRATISLAVA.longitude, BRATISLAVA.latitude],
            zoomLevel: 10,
            pitch: 0,
            heading: 0,
          }}
          followUserLocation={nearMeActive}
          followUserMode={UserTrackingMode.Follow}
          followZoomLevel={15}
        />

        <UserLocation
          visible={nearMeActive}
          animated
          showsUserHeadingIndicator
          onUpdate={(location) => {
            const next = {
              latitude: location.coords.latitude,
              longitude: location.coords.longitude,
            };
            setCurrentLocation((current) =>
              !current || distanceKm(current, next) >= 0.05 ? next : current
            );
          }}
        />

        {districtQuery.data&&<ShapeSource id="city-districts" shape={districtQuery.data} onPress={event=>{void selectDistrict(event.features[0]?.properties,event.point);}}>
          <FillLayer id="city-district-fill" belowLayerID="label_country_1" style={{fillOpacityTransition:{duration:reducedMotion?0:280,delay:0},fillColor:['case',['==',['get','id'],selectedDistrict??''],'#DE4D96',districtInkExpression],fillOpacity:['interpolate',['linear'],['zoom'],10,['case',['==',['get','id'],selectedDistrict??''],target?0.08:0.56,selectedDistrict?0.20:0.40],13,['case',['==',['get','id'],selectedDistrict??''],target?0.04:0.42,selectedDistrict?0.13:0.29],15,0]}}/>
        </ShapeSource>}
        {districtLines&&<ShapeSource id="city-district-boundaries" shape={districtLines}>
          <LineLayer id="city-district-boundary" belowLayerID="label_country_1" style={{lineColor:['case',['==',['get','id'],selectedDistrict??''],'#A52469','#C14D8A'],lineWidth:['case',['==',['get','id'],selectedDistrict??''],3,1.5],lineWidthTransition:{duration:reducedMotion?0:280,delay:0},lineOpacity:['interpolate',['linear'],['zoom'],10,target?0.48:0.9,15,0]}}/>
        </ShapeSource>}
        {districtQuery.data&&<ShapeSource id="district-labels" shape={{type:'FeatureCollection',features:districtQuery.data.features.filter(feature=>Array.isArray(feature.properties.label_coordinates)&&feature.properties.label_coordinates.length===2).map(feature=>({type:'Feature',properties:feature.properties,geometry:{type:'Point',coordinates:feature.properties.label_coordinates}}))}} onPress={event=>{void selectDistrict(event.features[0]?.properties,event.point);}}>
          <CircleLayer id="city-district-count-disc" belowLayerID="label_country_1" style={{circleColor:'#FFF6FB',circleRadius:['case',['>=',['get','count'],100],17,14],circleStrokeColor:'#BA4985',circleStrokeWidth:1.3,circleOpacity:['interpolate',['linear'],['zoom'],10,0.94,14,0.76,15,0]}}/>
          <SymbolLayer id="city-district-count" aboveLayerID="city-district-count-disc" style={{textField:['to-string',['get','count']],textColor:'#872956',textSize:10,textFont:['Noto Sans Regular'],textHaloColor:'#FFF6FB',textHaloWidth:.4,textAllowOverlap:false,textOpacity:['case',['==',['get','id'],morphPhase==='morphing'?selectedDistrict??'':''],0,1]}}/>
          <SymbolLayer id="city-district-name" aboveLayerID="city-district-count" style={{textField:['get','name'],textOffset:[0,-1.45],textColor:colors.black,textSize:['case',['==',['get','id'],selectedDistrict??''],15,12.5],textFont:['Noto Sans Regular'],textHaloColor:colors.white,textHaloWidth:2.5,textAllowOverlap:false,textOpacity:['case',['==',['get','id'],morphPhase==='morphing'?selectedDistrict??'':''],0,1]}}/>
        </ShapeSource>}
        {!showUtilities && nearMeActive && !target && <ShapeSource
          ref={eventSourceRef}
          id="map-events"
          shape={eventShape}
          hitbox={{ width: 46, height: 46 }}
          onPress={(event) => {
            markerPressedAt.current=Date.now();
            const feature = event.features[0];
            if (!feature) return;
            if (feature.properties?.point_count) {
              const selected = clusterProperties(feature.properties);
              const target=nearMeActive?null:clusterCamera(selected,zoomLevel);
              if(target){cameraRequest.current++;cameraRef.current?.setCamera(target);}
              else setSelectedCluster(selected);
              return;
            }
            const id = feature.properties?.id;
            if (id) router.push("/event/" + String(id));
          }}
        >
          <CircleLayer id="event-clusters" aboveLayerID="label_country_1" filter={[">", ["get", "count"], 1]} style={{ circleColor: colors.primary, circleRadius: ["interpolate",["linear"],["zoom"],10,10,12,14,14,21], circleOpacity:["interpolate",["linear"],["zoom"],10,.45,14,1], circleStrokeColor: colors.white, circleStrokeWidth: 2 }} />
          <SymbolLayer id="event-cluster-count" aboveLayerID="event-clusters" filter={[">", ["get", "count"], 1]} style={{ textField: ["get", "point_count_abbreviated"], textColor: colors.white, textSize: 11, textFont: ["Noto Sans Regular"] }} />
          <CircleLayer id="event-points" aboveLayerID="event-cluster-count" filter={["==", ["get", "count"], 1]} style={{
            circleColor: ["case", ["==", ["get", "nearby"], true], colors.primaryDark, colors.primary],
            circleOpacity: nearMeActive ? ["case", ["==", ["get", "nearby"], true], 1, 0.3] : 1,
            circleRadius: ["case", ["==", ["get", "nearby"], true], 16, 14],
            circleStrokeColor: colors.white,
            circleStrokeWidth: 3,
          }} />
          <SymbolLayer id="event-symbols" aboveLayerID="event-points" filter={["==", ["get", "count"], 1]} style={{
            // Native text labels avoid font-glyph UI icons; keep GPU-native points.
            textField: "E",
            textColor: ["case", ["==", ["get", "nearby"], true], colors.textInverse, colors.white],
            textSize: 10,
            textFont: ["Noto Sans Regular"],
            textOpacity: nearMeActive ? ["case", ["==", ["get", "nearby"], true], 1, 0.45] : 1,
          }} />
        </ShapeSource>}

        {showUtilities && <ShapeSource
          ref={utilitySourceRef}
          id="public-toilets"
          shape={utilityShape}
          cluster
          clusterRadius={48}
          clusterMaxZoomLevel={14}
          onPress={(event) => {
            const feature = event.features[0];
            if (!feature) return;
            if (feature.properties?.point_count) {
              void expandCluster(feature, utilitySourceRef);
              return;
            }
            const id = feature?.properties?.id;
            if (id) router.push({ pathname: "/utility/[id]", params: { id: String(id), kind: String(feature.properties?.kind ?? "toilet") } });
          }}
        >
          <CircleLayer id="toilet-clusters" aboveLayerID="label_country_1" filter={["has", "point_count"]} style={{ circleColor: colors.free, circleRadius: 20, circleStrokeColor: colors.white, circleStrokeWidth: 3 }} />
          <SymbolLayer id="toilet-cluster-count" aboveLayerID="toilet-clusters" filter={["has", "point_count"]} style={{ textField: ["get", "point_count_abbreviated"], textColor: colors.textInverse, textSize: 11, textFont: ["Noto Sans Regular"] }} />
          <CircleLayer id="toilet-points" aboveLayerID="toilet-cluster-count" filter={["!", ["has", "point_count"]]} style={{ circleColor: colors.free, circleRadius: 14, circleStrokeColor: colors.white, circleStrokeWidth: 3 }} />
          <SymbolLayer id="toilet-labels" aboveLayerID="toilet-points" filter={["!", ["has", "point_count"]]} style={{ textField: "WC", textColor: colors.textInverse, textSize: 8, textFont: ["Noto Sans Regular"] }} />
        </ShapeSource>}
        {target&&targetPoint&&focusedEvent.data&&<ShapeSource id="focused-event" shape={{type:'FeatureCollection',features:[{type:'Feature',properties:{id:focusedEvent.data.id},geometry:{type:'Point',coordinates:targetPoint}}]}} onPress={()=>{markerPressedAt.current=Date.now();router.push('/event/'+focusedEvent.data!.id);}}>
          <CircleLayer id="focused-event-halo" style={{circleRadius:24,circleColor:colors.primary,circleOpacity:.18}}/>
          <CircleLayer id="focused-event-point" aboveLayerID="focused-event-halo" style={{circleRadius:16,circleColor:colors.primaryDark,circleStrokeWidth:3,circleStrokeColor:colors.white}}/>
          <SymbolLayer id="focused-event-label" aboveLayerID="focused-event-point" style={{textField:'E',textColor:colors.white,textSize:12,textFont:['Noto Sans Regular'],textAllowOverlap:true}}/>
        </ShapeSource>}
      </MapView>
      {!target&&morphPhase==='idle'&&selectedDistrict&&zoomLevel<=14&&districtQuery.data?.features.filter(feature=>String(feature.properties.id)===selectedDistrict).map(feature=>(
        <Reveal key={selectedDistrict} style={{position:'absolute',bottom:insets.bottom+110,left:16,right:80,borderRadius:16,padding:14,backgroundColor:colors.surface,borderColor:colors.primary,borderWidth:1}}>
          <View style={{flexDirection:'row',justifyContent:'space-between',alignItems:'center'}}>
            <Text style={{color:colors.text,fontFamily:fonts.semibold}}>{feature.properties.name} · {feature.properties.count} {feature.properties.count===1?'event':'events'}</Text>
            <Pressable accessibilityRole="button" accessibilityLabel="Clear district selection" onPress={()=>setSelectedDistrict(null)}><AppIcon name="close" size={20} color={colors.text}/></Pressable>
          </View>
          <Pressable accessibilityRole="button" accessibilityLabel={`Explore ${feature.properties.name} events`} onPress={()=>{void selectDistrict(feature.properties);}}><Text style={{color:colors.primary,paddingTop:10}}>Explore events</Text></Pressable>
          <Text style={{color:colors.textMuted,fontSize:10,paddingTop:8}}>Boundaries: GKÚ Bratislava · CC BY 4.0</Text>
        </Reveal>
      ))}
      {target&&<Reveal key={target.nonce} style={{position:'absolute',bottom:insets.bottom+100,left:16,right:16,backgroundColor:colors.surface,borderRadius:16,padding:12}}>
        <View style={{flexDirection:'row',justifyContent:'space-between',alignItems:'center',marginBottom:8}}>
          <Pressable accessibilityRole="button" accessibilityLabel="Back to event source" onPress={()=>closeTarget(true)}><Text style={{color:colors.primary}}>‹ Back</Text></Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel="Close selected event" onPress={()=>closeTarget(false)}><AppIcon name="close" size={20} color={colors.text}/></Pressable>
        </View>
        <View onLayout={event=>setPreviewHeight(event.nativeEvent.layout.height)}>
        {focusedEvent.isLoading?<ActivityIndicator/>:focusedEvent.isError?<Pressable onPress={()=>focusedEvent.refetch()}><Text>Could not load event. Retry</Text></Pressable>:focusedEvent.data?<>
          {!targetPoint&&<Text>Exact map location unavailable</Text>}
          <EventCard event={focusedEvent.data} variant="map"/>
        </>:null}
        </View>
      </Reveal>}
      <OverflowMenu visible={filtersOpen} title="Map events" onClose={()=>setFiltersOpen(false)}>
        <MapFilters value={filters} onChange={setFilters}/>
        <ListItem icon="map-outline" title={filters!==activeFilters||browseSummary.isFetching?'Updating city events…':`Browse all ${browseSummary.data?.total??'city'} events`} onPress={()=>{if(filters===activeFilters&&!browseSummary.isFetching&&browseSummary.data?.area_token){setFiltersOpen(false);router.push(areaRoute(browseSummary.data!.area_token,eventFilters));}}}/>

        <ListItem icon="calendar-outline" title={filters!==activeFilters||eventViewport.isFetching?'Updating area events…':`Browse ${eventTotal} events in this area`} onPress={()=>{setFiltersOpen(false);if(filters===activeFilters&&!eventViewport.isFetching&&areaToken)router.push(areaRoute(areaToken,eventFilters));}}/>
      </OverflowMenu>
      <OverflowMenu visible={!!selectedCluster} title={`${selectedCluster?.count||0} events near this area`} onClose={()=>setSelectedCluster(null)}>
        <ListItem icon="calendar-outline" title="View events" onPress={()=>{if(selectedCluster)router.push(areaRoute(selectedCluster.area_token,eventFilters));setSelectedCluster(null);}}/>

      </OverflowMenu>

      <View pointerEvents="box-none" style={StyleSheet.absoluteFillObject}>
        <View style={[styles.topControls, { marginTop: Math.max(16, insets.top + 12) }]}>
          <Pressable accessibilityRole="button" accessibilityLabel="Search events" onPress={() => router.push('/(tabs)/explore')} style={styles.searchBar}>
            <AppIcon name="search" size={17} color={colors.primary} />
            <Text style={styles.searchText}>Find events</Text>
          </Pressable>

          <Pressable
            accessibilityLabel={nearMeActive ? "Show all events" : "Show events near me"}
            onPress={toggleNearMe}
            style={[styles.nearButton, nearMeActive && styles.nearButtonActive]}
          >
            <AppIcon
              name="navigate"
              size={17}
              color={nearMeActive ? colors.white : colors.primary}
            />
            <Text
              style={[
                styles.nearText,
                nearMeActive && styles.nearTextActive,
              ]}
            >
              {nearMeActive ? "Nearby" : "Near me"}
            </Text>
          </Pressable>
        </View>

        <View style={styles.layerTray}><View style={styles.countPill}>
          <View style={styles.countDot} />
          <Text style={styles.countText}>
            {nearMeActive
              ? (showUtilities ? utilities.length : eventTotal) + " nearby"
              : (showUtilities ? utilities.length + " toilets" : eventTotal + " events")}
          </Text>
          {isRefreshing && <ActivityIndicator size={9} color={colors.white} />}
        </View>

        <Pressable
          accessibilityLabel={showUtilities ? "Show event map layer" : "Show public toilet map layer"}
          onPress={() => { void toggleLayer(); }}
          style={[styles.layerButton, showUtilities && styles.layerButtonActive]}
        >
          <AppIcon name={showUtilities ? "calendar-outline" : "business-outline"} size={16} color={showUtilities ? colors.white : colors.free} />
          <Text style={[styles.layerText, showUtilities && styles.layerTextActive]}>{showUtilities ? "Events" : "Toilets"}</Text>
        </Pressable>
        <Pressable accessibilityLabel="Browse all city utilities" onPress={() => router.push("/utilities")} style={styles.allUtilitiesButton}>
          <AppIcon name="grid-outline" size={14} color={colors.textMuted} />
          <Text style={styles.allUtilitiesText}>All utilities</Text>
        </Pressable>
        {<Pressable accessibilityRole="button" accessibilityLabel="Map event filters and area events" onPress={()=>setFiltersOpen(true)} style={styles.allUtilitiesButton}><AppIcon name="options-outline" size={14} color={colors.textMuted}/><Text style={styles.allUtilitiesText}>Filters / Area</Text></Pressable>}
        </View>
        <View style={[styles.controls,target&&{bottom:insets.bottom+160+previewHeight}]}>
          <Pressable
            accessibilityLabel="Zoom in"
            onPress={() => zoom("in")}
            style={styles.controlButton}
          >
            <AppIcon name="add" size={20} color={colors.text} />
          </Pressable>
          <Pressable
            accessibilityLabel="Zoom out"
            onPress={() => zoom("out")}
            style={styles.controlButton}
          >
            <AppIcon name="remove" size={20} color={colors.text} />
          </Pressable>
          <Pressable
            accessibilityLabel="Recenter map"
            onPress={recenter}
            style={styles.controlButton}
          >
            <AppIcon name="locate" size={19} color={colors.primary} />
          </Pressable>
        </View>

        <View style={styles.statusPill}>
          <AppIcon
            name={dataUnavailable || basemapUnavailable ? "cloud-offline-outline" : nearMeActive ? "navigate" : "map-outline"}
            size={13}
            color={dataUnavailable || basemapUnavailable ? colors.textMuted : colors.primary}
          />
          <Text style={styles.statusText}>
            {basemapUnavailable
              ? "Basemap network unavailable · cached tiles may remain visible"
              : dataUnavailable && hasCachedLayer
                ? `Offline · showing ${cacheIsOld ? "saved" : "cached"} ${showUtilities ? "utilities" : "events"}`
                : dataUnavailable
                  ? `Unable to refresh ${showUtilities ? "utilities" : "events"}`
                  : isRefreshing && !hasCachedLayer
                    ? `Loading ${showUtilities ? "utilities" : "events"}…`
                  : nearMeActive&&!currentLocation
                    ? "Waiting for location to show nearby events"
                  : nearMeActive
              ? (showUtilities ? utilities.length : nearbyPins.length)
                ? (showUtilities ? utilities.length + " public toilets near you" : eventTotal + " events near you")
                : showUtilities ? "No nearby public toilets" : "No nearby events"
              : showUtilities
                ? utilities.length ? utilities.length + " public toilets in this area" : "No public toilets in this area"
              : pins.length
                ? eventShape.total + " events on the map"
                : "No mapped events yet"}
          </Text>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  layerTray: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8, paddingHorizontal: 16, marginTop: 12 },
  container: {
    flex: 1,
    backgroundColor: colors.mapWater,
  },
  topControls: {
    marginTop: 16,
    marginHorizontal: 16,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  searchBar: {
    flex: 1,
    height: 46,
    borderRadius: 16,
    paddingHorizontal: 14,
    backgroundColor: colors.mediaOverlay,
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    borderWidth: 1,
    borderColor: colors.border,
    shadowColor: colors.shadow,
    shadowOpacity: 0.1,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
  searchText: {
    color: colors.textMuted,
    fontFamily: fonts.medium,
    fontSize: 12,
  },
  nearButton: {
    height: 46,
    borderRadius: 16,
    paddingHorizontal: 13,
    backgroundColor: colors.mediaOverlay,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    shadowColor: colors.shadow,
    shadowOpacity: 0.1,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
  },
  nearButtonActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  nearText: {
    color: colors.text,
    fontFamily: fonts.semibold, fontWeight: '600',
    fontSize: 12,
  },
  nearTextActive: {
    color: colors.white,
  },
  countPill: {
    alignSelf: "flex-start",
    marginTop: 8,
    marginLeft: 0,
    height: 26,
    paddingHorizontal: 10,
    borderRadius: 13,
    backgroundColor: "rgba(39,35,41,0.9)",
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
  },
  countDot: {
    width: 5,
    height: 5,
    borderRadius: 3,
    backgroundColor: colors.primary,
  },
  countText: {
    color: colors.white,
    fontFamily: fonts.medium,
    fontSize: 12,
  },
  layerButton: {
    alignSelf: "flex-start",
    marginTop: 8,
    marginLeft: 0,
    height: 44,
    paddingHorizontal: 12,
    borderRadius: 17,
    backgroundColor: colors.mediaOverlay,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  allUtilitiesButton: {
    alignSelf: "flex-start",
    marginTop: 6,
    marginLeft: 0,
    height: 44,
    paddingHorizontal: 11,
    borderRadius: 16,
    backgroundColor: colors.mediaOverlay,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  allUtilitiesText: { color: colors.textMuted, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 },
  layerButtonActive: { backgroundColor: colors.successSurface, borderColor: colors.free },
  layerText: { color: colors.text, fontFamily: fonts.semibold, fontWeight: '600', fontSize: 12 },
  layerTextActive: { color: colors.white },
  controls: {
    position: "absolute",
    right: 16,
    bottom: 90,
    gap: 7,
  },
  controlButton: {
    width: 48,
    height: 48,
    borderRadius: 24,
    backgroundColor: colors.mediaOverlay,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: colors.shadow,
    shadowOpacity: 0.12,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
  },
  statusPill: {
    position: "absolute",
    left: 18,
    right: 18,
    bottom: 24,
    alignSelf: "center",
    minHeight: 34,
    paddingHorizontal: 12,
    borderRadius: 17,
    backgroundColor: colors.mediaOverlay,
    borderWidth: 1,
    borderColor: colors.border,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  statusText: {
    color: colors.textMuted,
    fontFamily: fonts.medium,
    fontSize: 12,
  },
});

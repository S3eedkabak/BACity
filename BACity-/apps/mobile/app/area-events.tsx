import { useMapFiltersStore } from '../src/map/filterStore';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, BackHandler, Dimensions, FlatList, Platform, Text, View } from 'react-native';
import Svg, { Path } from 'react-native-svg';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';
import { router, useLocalSearchParams } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useInfiniteQuery, useQuery } from '@tanstack/react-query';
import { areaEvents, getSavedEvents, saveEvent, unsaveEvent } from '../src/api/events';
import { EventCard } from '../src/components/EventCard';
import { EmptyState } from '../src/components/EmptyState';
import { IconButton } from '../src/components/SocialUI';
import { AppIcon } from '../src/components/AppIcon';
import { AnimatedPressable as Pressable } from '../src/components/motion/Motion';
import { MapFilters } from '../src/map/MapFilters';
import { parseFilters } from '../src/map/area';
import { DISTRICT_SURFACE } from '../src/map/DistrictMorphLayer';
import { districtHeaderHeight, headerSurfacePath } from '../src/map/districtMorphGeometry';
import { useDistrictMorph } from '../src/map/districtMorphState';
import { useAuthStore } from '../src/store/authStore';
import { colors } from '../src/theme/colors';
import { fonts } from '../src/theme/fonts';

export default function AreaEvents() {
  const params = useLocalSearchParams<{area:string;filters?:string;districtMorph?:string}>();
  const insets=useSafeAreaInsets();
  const morphEntry=useDistrictMorph(state=>state.entry);
  const morphViewport=useDistrictMorph(state=>state.viewport);
  const morphPhase=useDistrictMorph(state=>state.phase);
  const morphArea=Platform.OS==='ios'&&params.districtMorph==='1'&&!!morphEntry;
  // The shared morph renders the surface and identity until the page takes over.
  const morphOwnsHeader=morphArea&&(morphPhase==='morphing'||morphPhase==='returning');
  useEffect(()=>{
    if(morphArea)useDistrictMorph.getState().markAreaMounted(useDistrictMorph.getState().nonce);
  },[morphArea]);
  function goBack(){
    if(morphArea&&useDistrictMorph.getState().beginReturn())return;
    router.back();
  }
  useEffect(()=>{
    if(!morphArea)return;
    const subscription=BackHandler.addEventListener('hardwareBackPress',()=>{goBack();return true;});
    return()=>subscription.remove();
  },[morphArea]);
  useEffect(()=>()=>{
    const state=useDistrictMorph.getState();
    if(state.phase==='area-visible'&&params.districtMorph==='1')state.cancel(state.nonce);
  },[params.districtMorph]);
  const [filters,setFilters] = useState(()=>parseFilters(params.filters));
  const [active,setActive] = useState(filters);
  const shareFilters=useMapFiltersStore(state=>state.setFilters);
  useEffect(()=>{shareFilters(active);},[active,shareFilters]);
  const token = useAuthStore(s=>s.token);
  const [saveError,setSaveError] = useState(''); const [saving,setSaving] = useState<string|null>(null);
  useEffect(()=>{const t=setTimeout(()=>setActive(filters),300);return()=>clearTimeout(t);},[filters]);
  const query = useInfiniteQuery({queryKey:['area-events',params.area,active],initialPageParam:undefined as string|undefined,
    queryFn:({pageParam,signal})=>areaEvents(params.area,active,pageParam,signal),
    getNextPageParam:page=>page.next_cursor||undefined,staleTime:30000,gcTime:120000,retry:false});
  const saved = useQuery({queryKey:['area-saved',token],queryFn:getSavedEvents,enabled:!!token});
  const ids = useMemo(()=>new Set(saved.data?.map(e=>e.id)),[saved.data]);
  const items = query.data?.pages.flatMap(p=>p.items)||[];
  const refreshing = filters!==active || query.isFetching && !query.isFetchingNextPage;
  async function toggle(id:string) {
    if(!token){router.push('/auth');return;}
    setSaving(id);setSaveError('');
    try{if(ids.has(id))await unsaveEvent(id);else await saveEvent(id);await saved.refetch();}catch(e:any){setSaveError(e.message);}finally{setSaving(null);}
  }
  const count=query.data?.pages[0]?.total??morphEntry?.count??0;
  const window=Dimensions.get('window');
  const headerHeight=morphViewport?.headerHeight??districtHeaderHeight(window.height);
  const headerWidth=morphViewport?.width??window.width;
  return <SafeAreaView edges={['top']} style={{flex:1,backgroundColor:morphArea?DISTRICT_SURFACE:colors.background}}>
    {morphArea&&<StatusBar style="dark"/>}
    {morphArea?<View style={{height:Math.max(110,headerHeight-insets.top),backgroundColor:colors.background,overflow:'visible'}}>
      <Svg width={headerWidth} height={headerHeight} pointerEvents="none" style={{position:'absolute',top:-insets.top,left:0,opacity:morphOwnsHeader?0:1}}>
        <Path d={headerSurfacePath(headerWidth,headerHeight)} fill={DISTRICT_SURFACE}/>
      </Svg>
      <View accessibilityElementsHidden={morphOwnsHeader} style={{paddingHorizontal:22,opacity:morphOwnsHeader?0:1}}>
        <Pressable accessibilityRole="button" accessibilityLabel="Back to map" onPress={goBack} style={{width:44,height:44,justifyContent:'center'}}><AppIcon name="chevron-back" size={23} color={colors.black}/></Pressable>
        <Text style={{marginTop:4,fontFamily:fonts.black,fontSize:30,lineHeight:36,color:colors.black}} numberOfLines={1}>{query.data?.pages[0]?.name??morphEntry?.name}</Text>
        <Text accessibilityLiveRegion="polite" style={{marginTop:4,fontFamily:fonts.semibold,fontSize:13,lineHeight:18,color:colors.black}}>{count} {count===1?'event':'events'} in this area</Text>
      </View>
    </View>:<View style={{flexDirection:'row',alignItems:'center',paddingHorizontal:12}}><IconButton icon="chevron-back" label="Back to map" onPress={goBack}/><Text style={{fontFamily:fonts.semibold,color:colors.text,fontSize:18}}>Area events</Text></View>}
    <View style={{flex:1,backgroundColor:colors.background}}>
    <FlatList data={refreshing?[]:items} keyExtractor={e=>e.id} initialNumToRender={8} maxToRenderPerBatch={8} windowSize={7} contentContainerStyle={{width:'100%',maxWidth:760,alignSelf:'center',padding:18,paddingBottom:40+insets.bottom,gap:12}} keyboardShouldPersistTaps="handled"
      ListHeaderComponent={<View style={{gap:12}}>{!morphArea&&<><Text style={{fontFamily:fonts.black,fontSize:26,color:colors.text}}>{query.data?.pages[0]?.name||'Events near this area'}</Text><Text accessibilityLiveRegion="polite" style={{color:colors.textMuted}}>{refreshing?'Updating events…':`${count} ${count===1?'event':'events'} in this area`}</Text></>}<MapFilters value={filters} onChange={setFilters}/>{query.data?.pages[0]?.refreshed&&<Text style={{color:colors.textMuted}}>Events changed since the map loaded. This list shows the latest count.</Text>}{!!saveError&&<Text accessibilityRole="alert" style={{color:colors.danger}}>{saveError}</Text>}</View>}
      renderItem={({item})=><EventCard event={item} saved={ids.has(item.id)} saving={saving===item.id} onToggleSave={()=>void toggle(item.id)}/>}
      ListEmptyComponent={query.isPending||refreshing?<ActivityIndicator color={colors.primary}/>:!query.isError?<EmptyState title="No events in this area" subtitle="Try other dates or interests."/>:null}
      ListFooterComponent={query.isError?<EmptyState title="Area couldn’t load" subtitle={query.error.message} action="Refresh area" onAction={()=>void query.refetch()}/>:query.isFetchingNextPage?<ActivityIndicator color={colors.primary}/>:null}
      onEndReached={()=>{if(query.hasNextPage&&!query.isFetching&&!refreshing)void query.fetchNextPage();}} onEndReachedThreshold={0.5}/>
    </View>
  </SafeAreaView>;
}

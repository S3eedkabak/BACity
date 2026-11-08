import AsyncStorage from '@react-native-async-storage/async-storage';
import type { ClusterData } from './area';
const KEY='@bacity/map-cluster-snapshot-v2';
export interface ClusterSnapshot {key:string;data:ClusterData;savedAt:number;}
let memory:ClusterSnapshot|null=null;
export async function loadClusterSnapshot():Promise<ClusterSnapshot|null> {
  if(memory)return memory;
  try {
    const value=JSON.parse(await AsyncStorage.getItem(KEY)||'null');
    if(value?.data?.count_semantics!=='distinct_discoverable_events')return null;
    if(!value||typeof value.key!=='string'||typeof value.savedAt!=='number'||!Array.isArray(value.data?.features)||value.data.features.length>1100)return null;
    if(value.data.features.reduce((n:number,f:any)=>n+f.properties.count,0)!==value.data.total)return null;
    memory=value;return memory;
  } catch {return null;}
}
export function saveClusterSnapshot(key:string,data:ClusterData):ClusterSnapshot {
  memory={key,data,savedAt:Date.now()};
  void AsyncStorage.setItem(KEY,JSON.stringify(memory)).catch(()=>undefined);
  return memory;
}

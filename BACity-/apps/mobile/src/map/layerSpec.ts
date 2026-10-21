/** Translate native MapLibre layer style names without introducing undefined fields. */
export function layerSpec(id:string,type:string,source:string,style:Record<string,unknown>,filter?:unknown[]) {
  const paint:Record<string,unknown>={},layout:Record<string,unknown>={};
  for(const [key,value] of Object.entries(style||{})) {
    if(value===undefined)continue;
    const name=key.replace(/[A-Z]/g,char=>'-'+char.toLowerCase());
    const isLayout=type==='symbol'&&!['textColor','textOpacity','textHaloColor','textHaloWidth'].includes(key);
    (isLayout?layout:paint)[name]=value;
  }
  return {id,type,source,paint,layout,...(filter?{filter}:{})};
}

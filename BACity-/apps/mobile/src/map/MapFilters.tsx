import { useState } from 'react';
import { ScrollView, Text, TextInput, View } from 'react-native';
import { Chip } from '../components/CommunityUI';
import { colors } from '../theme/colors';
import { dateRange, presetRange, type MapFilters as Filters } from './area';

const categories = ['Music','Culture','Nightlife','Food & Drink','Markets','Workshops','Family','Arts','Theatre','Sports','Education','Community','Networking','Festivals','Student','Technology','Comedy','Exhibitions','Other'];
export function MapFilters({value,onChange}: {value:Filters;onChange:(value:Filters)=>void}) {
  const [from,setFrom] = useState(''); const [to,setTo] = useState(''); const [error,setError] = useState('');
  const input = {color:colors.text,backgroundColor:colors.surfaceAlt,borderRadius:12,padding:12,minHeight:44,flex:1};
  return <View style={{gap:8}}>
    <TextInput accessibilityLabel="Search events in area" placeholder="Search events" placeholderTextColor={colors.textMuted} value={value.q||''} onChangeText={q=>onChange({...value,q})} style={input}/>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{gap:8}}>
      <Chip title="All dates" active={!value.starts_after&&!value.starts_before} onPress={()=>onChange({...value,starts_after:undefined,starts_before:undefined})}/>
      {(['Today','Tomorrow','Weekend'] as const).map(p=><Chip key={p} title={p} active={value.starts_after===presetRange(p).starts_after&&value.starts_before===presetRange(p).starts_before} onPress={()=>onChange({...value,...presetRange(p)})}/>)}
      <Chip title="Free" active={!!value.free_only} onPress={()=>onChange({...value,free_only:!value.free_only})}/>
      <Chip title="Fresh only" active={value.status==='fresh'} onPress={()=>onChange({...value,status:value.status==='fresh'?undefined:'fresh'})}/>
    </ScrollView>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{gap:8}}><Chip title="All interests" active={!value.category} onPress={()=>onChange({...value,category:undefined})}/>{categories.map(category=><Chip key={category} title={category} active={value.category===category} onPress={()=>onChange({...value,category})}/>)}</ScrollView>
    {!!value.starts_after&&<Text style={{color:colors.textMuted}}>Dates: {new Date(value.starts_after).toLocaleDateString('en-GB',{timeZone:'Europe/Bratislava'})} – {value.starts_before?new Date(value.starts_before).toLocaleDateString('en-GB',{timeZone:'Europe/Bratislava'}):'onward'}</Text>}
    <View style={{flexDirection:'row',gap:8}}><TextInput accessibilityLabel="Start date YYYY-MM-DD" placeholder="From YYYY-MM-DD" placeholderTextColor={colors.textMuted} value={from} onChangeText={setFrom} style={input}/><TextInput accessibilityLabel="End date YYYY-MM-DD" placeholder="To YYYY-MM-DD" placeholderTextColor={colors.textMuted} value={to} onChangeText={setTo} style={input}/><Chip title="Apply" active={false} onPress={()=>{const range=dateRange(from,to);setError(range?'':'Use valid dates in order.');if(range)onChange({...value,...range});}}/></View>
    {!!error&&<Text accessibilityRole="alert" style={{color:colors.danger}}>{error}</Text>}
  </View>;
}

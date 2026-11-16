import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { createRequire } from 'node:module';
import ts from 'typescript';
import React from 'react';
import TestRenderer, { act } from 'react-test-renderer';
import * as QueryLib from '@tanstack/react-query';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
const require=createRequire(import.meta.url), root=path.resolve(import.meta.dirname,'..');
function environment(overrides={}) {
 const cache=new Map(), lifecycle=[], timings=[];let reduced=false;
 const native={FlatList:({data=[],ListHeaderComponent,ListEmptyComponent,ListFooterComponent,renderItem})=>React.createElement('List',null,ListHeaderComponent,data.length?data.map((item,index)=>React.createElement(React.Fragment,{key:item.id??index},renderItem({item,index}))):ListEmptyComponent,ListFooterComponent),KeyboardAvoidingView:'KeyboardAvoidingView',ScrollView:'ScrollView',Text:'Text',View:'View',Pressable:'Pressable',TextInput:'TextInput',ActivityIndicator:'ActivityIndicator',Modal:({visible,children})=>visible?React.createElement('Modal',null,children):null,Platform:{OS:'ios'},useWindowDimensions:()=>({width:390,height:844,fontScale:1}),Alert:{alert(){}},PixelRatio:{getFontScale:()=>1},StyleSheet:{create:x=>x,flatten:x=>Array.isArray(x)?Object.assign({},...x):x,absoluteFillObject:{},hairlineWidth:.5},AppState:{addEventListener:(_,cb)=>{lifecycle.push(cb);return {remove:()=>lifecycle.splice(lifecycle.indexOf(cb),1)};}},AccessibilityInfo:{isReduceMotionEnabled:async()=>reduced,addEventListener:()=>({remove(){}})}};
 const animated={View:'AnimatedView',Text:'AnimatedText',createAnimatedComponent:x=>x};
 const motion={default:animated,__esModule:true,useSharedValue:v=>React.useRef({value:v}).current,useAnimatedStyle:fn=>fn(),useAnimatedProps:fn=>fn(),Easing:{out:x=>x,cubic:x=>x,linear:x=>x},LinearTransition:{duration:()=>undefined},withTiming:(v,config)=>{timings.push({v,config});return v;},withSpring:v=>v,withSequence:(...v)=>v.at(-1),withRepeat:v=>v,withDelay:(_,v)=>v,cancelAnimation(){},interpolateColor:(_v,_range,c)=>c[0],useReducedMotion:()=>reduced};
 const externals={'@tanstack/react-query':QueryLib,'react':React,'react/jsx-runtime':require('react/jsx-runtime'),'react-native':native,'react-native-svg':{__esModule:true,default:'Svg',Circle:'Circle',Path:'Path'},'react-native-reanimated':motion,'@react-navigation/native':{useIsFocused:()=>true},'expo-router':{router:{push(){},canGoBack:()=>true}},'expo-haptics':{selectionAsync:async()=>{},notificationAsync:async()=>{},NotificationFeedbackType:{Success:'success'}},...overrides};
 function load(file) {
  file=path.resolve(file);if(cache.has(file))return cache.get(file);
  if(file===root+'/theme/appearance.ts')return {themedStyles:fn=>fn(),useThemeRevision:()=>0};
  if(file===root+'/components/AppIcon.tsx')return {AppIcon:p=>React.createElement('Icon',p)};
  if(file===root+'/components/interactions/useMotionPreference.ts')return {useMotionPreference:()=>reduced};
  if(overrides[file])return overrides[file];
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2020,esModuleInterop:true}}).outputText;
  const exports={};cache.set(file,exports);
  const localRequire=name=>{if(externals[name])return externals[name];if(name.startsWith('.')){let p=path.resolve(path.dirname(file),name);if(!path.extname(p))p=['.ts','.tsx','.js'].map(ext=>p+ext).find(p=>fs.existsSync(p));return load(p);}return require(name);};
  vm.runInNewContext(code,{exports,require:localRequire,setTimeout,clearTimeout,console,process:{env:{}},URLSearchParams,AbortController},{filename:file});return exports;
 }
 return {timings,load:name=>load(root+'/'+name),background:()=>lifecycle.forEach(cb=>cb('background')),setReduced:v=>{reduced=v;},listeners:()=>lifecycle.length};
}
function press(b){assert.ok(b,'button exists');if(!b.props.disabled)b.props.onPress?.({stopPropagation(){}});}
function button(tree,label){return tree.root.findAllByType('Pressable').find(n=>n.props.accessibilityLabel===label);}
function render(element){let tree;act(()=>{tree=TestRenderer.create(element);});return tree;}
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function waitForButton(tree,label){ for(let step=0;step<100;step++){const found=button(tree,label);if(found)return found;await act(async()=>{await tick();});}assert.fail(`Button did not settle: ${label}`); }

test('save control has checked/disabled semantics and stops card navigation',()=>{
 const e=environment(),{LikeAction}=e.load('components/interactions/LikeAction.tsx');let calls=0,stopped=0;
 const t=render(React.createElement(LikeAction,{active:false,onPress:()=>calls++}));act(()=>button(t,'Save event').props.onPress({stopPropagation(){stopped++;}}));assert.equal(calls,1);assert.equal(stopped,1);
 act(()=>t.update(React.createElement(LikeAction,{active:true,busy:true,onPress:()=>calls++})));const b=button(t,'Remove from saved events');assert.equal(b.props.accessibilityState.checked,true);press(b);assert.equal(calls,1);act(()=>t.unmount());
});
test('star input has five accessible values; read-only display cannot mutate',()=>{
 const e=environment(),{StarRating}=e.load('components/interactions/StarRating.tsx');let value;
 const t=render(React.createElement(StarRating,{value:0,label:'Worth attending',onChange:v=>value=v}));assert.equal(t.root.findAllByType('Pressable').length,5);act(()=>press(button(t,'Worth attending, 4 out of 5')));assert.equal(value,4);
 act(()=>t.update(React.createElement(StarRating,{value:4,label:'Worth attending'})));assert.equal(t.root.findAllByType('Pressable').length,0);act(()=>t.unmount());
});
test('early release/background cancel hold; completed hold fires once; unmount cleans listener',async()=>{
 const e=environment(),{HoldToConfirm}=e.load('components/interactions/HoldToConfirm.tsx');let calls=0,finish;
 const t=render(React.createElement(HoldToConfirm,{title:'Delete account',description:'Permanent',onConfirm:()=>{calls++;return new Promise(r=>finish=r);}})),b=button(t,'Hold for 1.2 seconds to delete account');
 act(()=>{b.props.onPressIn({nativeEvent:{pageX:0,pageY:0}});b.props.onPressOut();b.props.onLongPress();});assert.equal(calls,0);
 act(()=>{b.props.onPressIn({nativeEvent:{pageX:0,pageY:0}});e.background();b.props.onLongPress();});assert.equal(calls,0);
 act(()=>{b.props.onPressIn({nativeEvent:{pageX:0,pageY:0}});b.props.onLongPress();b.props.onLongPress();});assert.equal(calls,1);
 await act(async()=>{finish();await tick();});assert.equal(button(t,'Hold for 1.2 seconds to delete account').props.disabled,true);act(()=>t.unmount());assert.equal(e.listeners(),0);
});
test('non-gesture confirmation works with reduced motion and errors remain recoverable',async()=>{
 const e=environment();e.setReduced(true);const {HoldToConfirm}=e.load('components/interactions/HoldToConfirm.tsx');let calls=0;
 const t=render(React.createElement(HoldToConfirm,{title:'Delete account',description:'Permanent',onConfirm:async()=>{calls++;throw new Error('Server denied');}}));act(()=>press(button(t,'Confirm another way')));assert.equal(t.root.findAllByType('Modal').length,1);
 await act(async()=>{press(button(t,'Delete account'));await tick();});assert.equal(calls,1);assert.ok(t.root.findAllByProps({accessibilityRole:'alert'}).length);assert.equal(button(t,'Hold for 1.2 seconds to delete account').props.disabled,false);act(()=>t.unmount());
});
test('morph action renders loading, success and retry in both motion modes',()=>{
 for(const reduced of [true,false]){const e=environment();e.setReduced(reduced);const {MorphActionButton}=e.load('components/interactions/ActionButton.tsx');const t=render(React.createElement(MorphActionButton,{title:'Publish',onPress(){}}));
 for(const [state,label,disabled] of [['loading','Publish…',true],['success','Saved',true],['error','Retry · Publish',false]]){act(()=>t.update(React.createElement(MorphActionButton,{title:'Publish',state,onPress(){}})));assert.equal(button(t,label).props.disabled,disabled);}act(()=>t.unmount());}
});
test('password visibility is controlled and guidance never exposes password text',()=>{
 const e=environment(),{AppTextField}=e.load('components/interactions/AppTextField.tsx'),{PasswordStrengthIndicator}=e.load('components/interactions/PasswordStrengthIndicator.tsx');const secret='Unique test passphrase';
 const t=render(React.createElement(React.Fragment,null,React.createElement(AppTextField,{label:'Password',secure:true,value:secret}),React.createElement(PasswordStrengthIndicator,{password:secret})));
 assert.equal(t.root.findByType('TextInput').props.secureTextEntry,true);act(()=>press(button(t,'Show password')));assert.equal(t.root.findByType('TextInput').props.secureTextEntry,false);assert.ok(!t.root.findAllByType('Text').some(n=>n.children.join('').includes(secret)));act(()=>t.unmount());
});
test('ticker exposes final localized values without speaking intermediate animated digits',()=>{
 const e=environment(),{NumberTicker}=e.load('components/interactions/NumberTicker.tsx');const t=render(React.createElement(NumberTicker,{value:999,label:'reviews',locale:'en-US'}));
 for(const value of [1000,0,12000]){act(()=>t.update(React.createElement(NumberTicker,{value,label:'reviews',locale:'en-US'})));assert.equal(t.root.findByProps({accessible:true}).props.accessibilityLabel,`${value.toLocaleString('en-US')} reviews`);}act(()=>t.unmount());
});
test('feedback validates, keeps failed drafts, blocks duplicate taps and retries submission',async()=>{
 let calls=0,reject,resolve;const e=environment({[root+'/api/interactions.ts']:{publishReview:()=>{calls++;return new Promise((res,rej)=>{resolve=res;reject=rej;});}},[root+'/components/CommunityUI.tsx']:{Disclosure:({children})=>React.createElement('Disclosure',null,children)}});
 const {FeedbackComposer}=e.load('components/interactions/FeedbackComposer.tsx'),client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});const t=render(React.createElement(QueryClientProvider,{client},React.createElement(FeedbackComposer,{id:'event',kind:'event'})));
 act(()=>press(button(t,'Enjoyed it')));await act(async()=>{press(button(t,'Publish review'));await tick();});assert.equal(calls,0);
 act(()=>{t.root.findByType('TextInput').props.onChangeText('A good local experience.');press(button(t,'Worth attending, 4 out of 5'));});
 await act(async()=>{const b=button(t,'Publish review');press(b);press(b);await tick();});assert.equal(calls,1);
 await act(async()=>{reject(new Error('Network unavailable'));await tick();});await waitForButton(t,'Retry · Publish review');assert.equal(t.root.findByType('TextInput').props.value,'A good local experience.');
 await act(async()=>{press(button(t,'Retry · Publish review'));await tick();});assert.equal(calls,2);await act(async()=>{resolve({id:'persisted'});await tick();await tick();await tick();});await waitForButton(t,'Done');assert.ok(t.root.findAllByProps({accessibilityRole:'alert'}).some(n=>n.children.includes('Your review was published.')));act(()=>t.unmount());client.clear();
});

test('follow state is optimistic across screens, duplicate presses send one request, failure rolls back',async()=>{
 let following=false,calls=0,reject;
 const e=environment({[root+'/store/authStore.ts']:{useAuthStore:selector=>selector({token:'test',user:{id:'owner'}})},[root+'/api/client.ts']:{apiRequest:async()=>({id:following?'edge':null,following})},[root+'/api/community.ts']:{follow:()=>{calls++;return new Promise((_,r)=>reject=r);},unfollow:async()=>{following=false;}}});
 const {FollowAction}=e.load('components/interactions/FollowAction.tsx'),client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});let t;
 await act(async()=>{t=TestRenderer.create(React.createElement(QueryClientProvider,{client},React.createElement(React.Fragment,null,React.createElement(FollowAction,{type:'organizer',id:'arts'}),React.createElement(FollowAction,{type:'organizer',id:'arts'}))));await tick();await tick();});
 await act(async()=>{const b=button(t,'Follow');press(b);press(b);await tick();});assert.equal(calls,1);assert.equal(client.getQueryData(['follow-state','organizer','arts']).following,true);
 await act(async()=>{reject(new Error('Offline'));await tick();await tick();});assert.equal(client.getQueryData(['follow-state','organizer','arts']).following,false);assert.ok(t.root.findAllByProps({accessibilityRole:'alert'}).length);act(()=>t.unmount());client.clear();
});

test('save hooks synchronize shared library, roll back failure and keep concurrent event updates',async()=>{
 let calls=0,reject;
 const e=environment({[root+'/store/authStore.ts']:{useAuthStore:selector=>selector({token:'test'})},[root+'/loading/development.ts']:{withLoadingTestDelay:fn=>fn()},[root+'/api/events.ts']:{getSavedEvents:async()=>[{id:'b',title:'B'}],saveEvent:()=>{calls++;return new Promise((_,r)=>reject=r);},unsaveEvent:async()=>{}}});
 const {useToggleSaveEvent}=e.load('hooks/useEvents.ts');let action;
 function Probe(){action=useToggleSaveEvent();return null;}
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});client.setQueryData(['saved-events'],[{id:'b',title:'B'}]);
 const t=render(React.createElement(QueryClientProvider,{client},React.createElement(Probe)));
 await act(async()=>{action.mutate({id:'a',saved:false,event:{id:'a',title:'A'}});action.mutate({id:'a',saved:false,event:{id:'a',title:'A'}});await tick();});assert.equal(calls,1);assert.ok(client.getQueryData(['saved-events']).some(x=>x.id==='a'));
 client.setQueryData(['saved-events'],old=>[...old,{id:'c',title:'C'}]);
 await act(async()=>{reject(new Error('Offline'));await tick();});assert.deepEqual(client.getQueryData(['saved-events']).map(x=>x.id),['b','c']);act(()=>t.unmount());client.clear();
});

test('notification bell labels real unread count, unavailable state, and reduced-motion updates',()=>{
 let data;const e=environment({[root+'/hooks/useNotifications.ts']:{useNotificationSummary:()=>({data,isError:false})}}),{NotificationBell}=e.load('components/interactions/NotificationBell.tsx');
 const t=render(React.createElement(NotificationBell));assert.ok(button(t,'Notifications'));
 data={unread:120};act(()=>t.update(React.createElement(NotificationBell)));assert.ok(button(t,'Notifications, 120 unread'));assert.ok(t.root.findAllByProps({accessibilityLabel:'120 unread'}).length);
 e.setReduced(true);data={unread:0};act(()=>t.update(React.createElement(NotificationBell)));assert.ok(button(t,'Notifications, 0 unread'));act(()=>t.unmount());
});
test('settings groups hide empty role sections and retain navigable children',()=>{
 const e=environment(),{SettingsNavList}=e.load('components/interactions/NavListCard.tsx');const t=render(React.createElement(SettingsNavList,{title:'Tools'},false,null));assert.equal(t.toJSON(),null);
 act(()=>t.update(React.createElement(SettingsNavList,{title:'Account'},React.createElement('Pressable',{accessibilityLabel:'Privacy'}))));assert.ok(button(t,'Privacy'));act(()=>t.unmount());
});
test('login composition preserves its controlled fields and exposes one heading',()=>{
 const e=environment(),{LoginCard}=e.load('components/interactions/LoginCard.tsx');const t=render(React.createElement(LoginCard,{title:'Welcome',subtitle:'Sign in'},React.createElement('TextInput',{value:'existing'})));
 assert.equal(t.root.findByType('TextInput').props.value,'existing');assert.equal(t.root.findAllByProps({accessibilityRole:'header'}).length,1);act(()=>t.unmount());
});
test('undo uses desired saved state, so an already restored event is never toggled off',async()=>{
 let saves=0,unsaves=0;
 const e=environment({[root+'/store/authStore.ts']:{useAuthStore:selector=>selector({token:'test'})},[root+'/loading/development.ts']:{withLoadingTestDelay:fn=>fn()},[root+'/api/events.ts']:{getSavedEvents:async()=>[{id:'a',title:'A'}],saveEvent:async()=>{saves++;},unsaveEvent:async()=>{unsaves++;}}});
 const {UndoSaveToast}=e.load('components/interactions/UndoSaveToast.tsx'),client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});client.setQueryData(['saved-events'],[{id:'a',title:'A'}]);client.setQueryData(['saved-undo'],{id:'a',title:'A'});
 const t=render(React.createElement(QueryClientProvider,{client},React.createElement(UndoSaveToast)));
 await act(async()=>{press(button(t,'Undo'));await tick();await tick();});assert.equal(saves,1);assert.equal(unsaves,0);assert.equal(client.getQueryData(['saved-undo']),null);act(()=>t.unmount());client.clear();
});

test('motion preferences share one OS listener, ignore stale hydration and clean up on unmount',async()=>{
 let subscriptions=0,reads=0,removals=0,notify,resolve;const values={};
 const source=fs.readFileSync(root+'/components/interactions/useMotionPreference.ts','utf8'),exports={};
 const native={AccessibilityInfo:{addEventListener:(_event,listener)=>{subscriptions++;notify=listener;return {remove(){removals++;}};},isReduceMotionEnabled:()=>{reads++;return new Promise(r=>resolve=r);}}};
 vm.runInNewContext(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText,{exports,require:name=>name==='react'?React:native});
 function Probe({id}){values[id]=exports.useMotionPreference();return null;}
 const t=render(React.createElement(React.Fragment,null,React.createElement(Probe,{id:'a'}),React.createElement(Probe,{id:'b'})));
 assert.equal(subscriptions,1);assert.equal(reads,1);assert.equal(values.a,true);
 act(()=>notify(false));assert.equal(values.a,false);assert.equal(values.b,false);
 act(()=>notify(true));await act(async()=>{resolve(false);await tick();});assert.equal(values.a,true);act(()=>t.unmount());assert.equal(removals,1);
});
test('appearance persistence cannot overwrite a newer choice and themed styles update without losing drafts',async()=>{
 let mode='dark',resolveRead,onChange;let reads=0,removals=0;const writes=[];
 const native={StyleSheet:{create:fn=>fn},Appearance:{getColorScheme:()=>mode,addChangeListener:listener=>{onChange=listener;return {remove(){removals++;}};}}};
 const storage={getItem:()=>{reads++;return new Promise(resolve=>resolveRead=resolve);},setItem:async(_key,value)=>writes.push(value)};
 const exports={};const dependencies={'react':React,'react-native':native,'react-native-svg':{__esModule:true,default:'Svg',Circle:'Circle',Path:'Path'},'zustand':require('zustand'),'@react-native-async-storage/async-storage':{__esModule:true,default:storage},'./colors':{setColorMode:value=>{mode=value;},getColorMode:()=>mode}};
 vm.runInNewContext(ts.transpileModule(fs.readFileSync(root+'/theme/appearance.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,esModuleInterop:true}}).outputText,{exports,require:name=>dependencies[name]});
 const styles=exports.themedStyles(()=>({body:{color:mode}}));let snapshot,draft;
 function Probe(){exports.useAppearanceLifecycle();exports.useThemeRevision();const [value]=React.useState('unfinished review');draft=value;snapshot=styles.body.color;return null;}
 const t=render(React.createElement(Probe));assert.equal(reads,1);assert.equal(snapshot,'dark');
 act(()=>exports.useAppearance.getState().setMode('light'));assert.equal(snapshot,'light');assert.equal(draft,'unfinished review');
 await act(async()=>{resolveRead('dark');await tick();});assert.equal(exports.useAppearance.getState().mode,'light');assert.deepEqual(writes,['light']);
 act(()=>exports.useAppearance.getState().setMode('system'));act(()=>onChange({colorScheme:'dark'}));assert.equal(snapshot,'dark');act(()=>t.unmount());assert.equal(removals,1);
});

test('moving out of a destructive hold cancels it before confirmation',()=>{
 const e=environment(),{HoldToConfirm}=e.load('components/interactions/HoldToConfirm.tsx');let calls=0;
 const t=render(React.createElement(HoldToConfirm,{title:'Delete account',description:'Permanent',onConfirm:async()=>{calls++;}}));const b=button(t,'Hold for 1.2 seconds to delete account');
 act(()=>{b.props.onPressIn({nativeEvent:{pageX:100,pageY:100}});b.props.onTouchMove({nativeEvent:{pageX:140,pageY:100}});b.props.onLongPress();});assert.equal(calls,0);act(()=>t.unmount());
});
test('common long passwords stay weak, stale estimates clear, and secrets are not rendered',async()=>{
 const e=environment(),{PasswordStrengthIndicator}=e.load('components/interactions/PasswordStrengthIndicator.tsx');const secret='passwordpasswordpassword';
 const t=render(React.createElement(PasswordStrengthIndicator,{password:secret}));await act(async()=>{await new Promise(r=>setTimeout(r,160));});
 assert.ok(t.root.findAllByProps({accessible:true}).some(n=>n.props.accessibilityLabel.startsWith('Very weak.')));
 act(()=>t.update(React.createElement(PasswordStrengthIndicator,{password:'a new unfinished input'})));
 assert.ok(t.root.findAllByProps({accessible:true}).some(n=>n.props.accessibilityLabel.startsWith('Checking strength')));
 assert.ok(!JSON.stringify(t.toJSON()).includes(secret));act(()=>t.unmount());
});

test('neutral completion feedback survives account cache teardown without retaining owner content',()=>{
 const e=environment({'react-native-safe-area-context':{useSafeAreaInsets:()=>({top:0,bottom:0,left:0,right:0})}}),{ActionFeedbackProvider,useActionFeedback}=e.load('components/interactions/ActionFeedback.tsx');let notify;
 function Owner({name}){notify=useActionFeedback();return React.createElement('Text',null,name);}
 const t=render(React.createElement(ActionFeedbackProvider,null,React.createElement(Owner,{key:'account',name:'private owner draft'})));
 act(()=>notify('Account deleted.'));
 act(()=>t.update(React.createElement(ActionFeedbackProvider,null,React.createElement(Owner,{key:'guest',name:'Welcome'}))));
 assert.ok(t.root.findAllByProps({accessibilityRole:'alert'}).length);assert.ok(JSON.stringify(t.toJSON()).includes('Account deleted.'));assert.ok(!JSON.stringify(t.toJSON()).includes('private owner draft'));act(()=>t.unmount());
});

test('AppSheet renders its heading and all detents without undefined token references',()=>{
 for(const reduced of [false,true]){
  const gesture=new Proxy({}, {get:()=>()=>gesture});
  const e=environment({
   'react-native-gesture-handler':{Gesture:{Pan:()=>gesture},GestureDetector:({children})=>children,GestureHandlerRootView:'GestureRoot'},
   'react-native-safe-area-context':{useSafeAreaInsets:()=>({top:0,bottom:34,left:0,right:0})},
   'expo-status-bar':{StatusBar:()=>null},
  });
  e.setReduced(reduced);
  const {AppSheet}=e.load('components/sheets/AppSheet.tsx');let closed=0;
  const t=render(React.createElement(AppSheet,{visible:true,title:'Map events',onClose:()=>closed++},React.createElement('Text',null,'Events')));
  assert.equal(t.root.findByProps({accessibilityRole:'header'}).children.join(''),'Map events');
  act(()=>press(button(t,'Expand or collapse Map events')));
  act(()=>button(t,'Expand or collapse Map events').props.onAccessibilityAction({nativeEvent:{actionName:'increment'}}));
  act(()=>press(button(t,'Dismiss Map events')));assert.equal(closed,1);
  act(()=>t.update(React.createElement(AppSheet,{visible:false,title:'Map events',onClose:()=>closed++})));
  act(()=>t.unmount());
 }
});

test('page frame stays stationary and content entrances never replay on rerender or resume',()=>{
 const e=environment(), {TabScene,ContentEntrance,SectionTransition}=e.load('components/navigation/SceneMotion.tsx');
 const frame=render(React.createElement(TabScene,null,React.createElement('Text',null,'Home')));
 assert.equal(frame.root.findAllByType('AnimatedView').length,0);
 act(()=>frame.unmount());
 const t=render(React.createElement(ContentEntrance,{index:0},React.createElement('Text',null,'Content')));
 const started=e.timings.length;assert.ok(started>0);
 act(()=>t.update(React.createElement(ContentEntrance,{index:0},React.createElement('Text',null,'Updated'))));
 e.setReduced(true);act(()=>t.update(React.createElement(ContentEntrance,{index:0})));
 e.setReduced(false);act(()=>t.update(React.createElement(ContentEntrance,{index:0})));
 assert.equal(e.timings.length,started);
 act(()=>t.unmount());
 const section=render(React.createElement(SectionTransition,{identity:'events'}));
 const before=e.timings.length;
 act(()=>section.update(React.createElement(SectionTransition,{identity:'places'})));
 assert.equal(e.timings.length,before+1);
 act(()=>section.update(React.createElement(SectionTransition,{identity:'places'})));
 assert.equal(e.timings.length,before+1);act(()=>section.unmount());
});

test('changing a saved review reaction applies the chosen rating and retains the review draft',async()=>{
 let submitted;
 const e=environment({
  [root+'/api/interactions.ts']:{publishReview:async(kind,id,body,ratings)=>{submitted={body,ratings};return {id:'existing'};}},
  [root+'/components/CommunityUI.tsx']:{Disclosure:({children})=>React.createElement('Disclosure',null,children)}
 });
 const {FeedbackComposer}=e.load('components/interactions/FeedbackComposer.tsx');
 const client=new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}});
 const t=render(React.createElement(QueryClientProvider,{client},React.createElement(FeedbackComposer,{id:'event',kind:'event',ownReview:{id:'existing',body:'Existing detailed review.',dimensions:{worth_attending:5,crowd:3}}})));
 act(()=>press(button(t,'Enjoyed it')));
 assert.equal(button(t,'Worth attending, 4 out of 5').props.accessibilityState.checked,true);
 assert.equal(t.root.findByType('TextInput').props.value,'Existing detailed review.');
 await act(async()=>{press(button(t,'Update review'));await tick();await tick();});
 assert.equal(submitted.ratings.worth_attending,4);assert.equal(submitted.ratings.crowd,3);
 act(()=>t.unmount());client.clear();
});

test('legacy community redirects wait for the root navigator instead of crashing on cold links',()=>{
 let navigation,section='collections';const destinations=[];
 const e=environment({
  'expo-router':{router:{replace:route=>destinations.push(route)},useLocalSearchParams:()=>({section}),useRootNavigationState:()=>navigation},
  [root+'/components/LoadingState.tsx']:{LoadingState:()=>'Loading'},
 });
 const Screen=e.load('../app/community.tsx').default;
 const t=render(React.createElement(Screen));assert.deepEqual(destinations,[]);
 navigation={key:'mounted-root'};act(()=>t.update(React.createElement(Screen)));
 assert.deepEqual(destinations,['/collections']);
 section='notifications';act(()=>t.update(React.createElement(Screen)));
 assert.deepEqual(destinations,['/collections','/notifications']);act(()=>t.unmount());
});

test('entry waits for hydration and a mounted navigator without a guessed timer',()=>{
 let navigation,state={isLoading:true,token:null,user:null};const destinations=[];
 const e=environment({
  'expo-router':{router:{replace:route=>destinations.push(route)},useRootNavigationState:()=>navigation},
  [root+'/store/authStore.ts']:{useAuthStore:selector=>selector(state)},
  [root+'/components/AppLoadingScreen.tsx']:{AppLoadingScreen:()=>'Loading'},
 });
 const Screen=e.load('../app/index.tsx').default;
 const t=render(React.createElement(Screen));assert.deepEqual(destinations,[]);
 navigation={key:'mounted-root'};act(()=>t.update(React.createElement(Screen)));assert.deepEqual(destinations,[]);
 state={isLoading:false,token:'fixture',user:{id:'owner'}};act(()=>t.update(React.createElement(Screen)));
 assert.deepEqual(destinations,['/(tabs)/discover']);act(()=>t.unmount());
});

test('premium deep links wait for navigation and session restoration before enforcing access',()=>{
 let navigation,restoring=true,entitlements={authenticated:false,isPending:false,isError:false,plus:null,refresh(){}},gate;
 const pushes=[];let allowed=0;
 const e=environment({
  'expo-router':{router:{push:route=>pushes.push(route)},useRootNavigationState:()=>navigation},
  [root+'/store/authStore.ts']:{useAuthStore:selector=>selector({isLoading:restoring})},
  [root+'/hooks/useEntitlements.ts']:{useEntitlements:()=>entitlements},
 });
 const {usePlusGate}=e.load('plus/usePlusGate.tsx');
 function Probe(){gate=usePlusGate();return null;}
 const t=render(React.createElement(Probe));
 act(()=>gate.run('event_chains',()=>allowed++));
 assert.equal(gate.decision,'loading');assert.equal(pushes.length,0);
 navigation={key:'mounted-root'};act(()=>t.update(React.createElement(Probe)));assert.equal(gate.decision,'loading');
 restoring=false;entitlements={...entitlements,authenticated:true,plus:{active:true}};
 act(()=>t.update(React.createElement(Probe)));assert.equal(gate.decision,'allow');
 act(()=>gate.run('event_chains',()=>allowed++));assert.equal(allowed,1);assert.equal(pushes.length,0);
 entitlements={...entitlements,plus:{active:false}};act(()=>t.update(React.createElement(Probe)));
 act(()=>gate.run('event_chains',()=>allowed++));assert.equal(pushes[0].pathname,'/plus');
 act(()=>t.unmount());
});

function memberEnvironment({ user = { id: 'viewer' }, getProfile, getProfileHistory }) {
 return environment({
  'expo-router': { useLocalSearchParams: () => ({ id: 'member' }), router: { push() {} } },
  [root+'/store/authStore.ts']: { useAuthStore: selector => selector({ user }) },
  [root+'/api/community.ts']: { getProfile, getProfileHistory },
  [root+'/api/client.ts']: { apiRequest() {} },
  [root+'/components/CommunityUI.tsx']: { Chip: 'Chip' },
  [root+'/components/SocialUI.tsx']: Object.fromEntries(['Avatar','IconButton','ListItem','OverflowMenu','ScreenHeader','Stat','SkeletonList'].map(name => [name, props => name === 'OverflowMenu' && !props.visible ? null : React.createElement(name, props)])),
  [root+'/components/navigation/ContentSafeArea.tsx']: { SafeAreaView: 'SafeAreaView' },
  [root+'/components/EmptyState.tsx']: { EmptyState: props => React.createElement('EmptyState',props) },
  [root+'/components/interactions/FollowAction.tsx']: { FollowAction: 'FollowAction' },
  [root+'/components/interactions/SegmentedControl.tsx']: { SegmentedControl: 'SegmentedControl' },
 });
}
test('guest member links show sign-in without making protected requests or spinning forever',async()=>{
 let calls=0; const e=memberEnvironment({user:null,getProfile:async()=>{calls++;},getProfileHistory:async()=>{calls++;}});
 const {default:Member}=e.load('../app/member/[id].tsx');
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});
 const t=render(React.createElement(QueryClientProvider,{client},React.createElement(Member)));
 await act(async()=>{await tick();});
 assert.equal(t.root.findByType('EmptyState').props.title,'Sign in to view this profile');
 assert.equal(t.root.findAllByType('SkeletonList').length,0); assert.equal(calls,0);
 act(()=>t.unmount());client.clear();
});
test('failed member profile stops loading and retry loads real profile activity',async()=>{
 let fail=true;const e=memberEnvironment({getProfile:async()=>{if(fail)throw Error('Profile unavailable');return {id:'member',display_name:'Member'};},getProfileHistory:async()=>[]});
 const {default:Member}=e.load('../app/member/[id].tsx'),client=new QueryClient({defaultOptions:{queries:{retry:false}}});
 const t=render(React.createElement(QueryClientProvider,{client},React.createElement(Member)));
 for(let i=0;i<5;i++)await act(async()=>{await tick();});
 assert.equal(t.root.findByType('EmptyState').props.title,"Profile couldn't load");
 assert.equal(t.root.findAllByType('SkeletonList').length,0);
 fail=false;await act(async()=>{t.root.findByType('EmptyState').props.onAction();await tick();});
 for(let i=0;i<5;i++)await act(async()=>{await tick();});
 assert.equal(t.root.findByType('EmptyState').props.title,'No public contributions');
 act(()=>t.unmount());client.clear();
});
test('late member activity responses cannot overwrite a newer selected section',async()=>{
 let finishOld;const e=memberEnvironment({getProfile:async()=>({id:'member',display_name:'Member'}),getProfileHistory:async(_id,tab)=>tab==='contributions'?new Promise(resolve=>finishOld=resolve):[{id:'review',body:'Review body',target_name:'Reviewed event'}]});
 const {default:Member}=e.load('../app/member/[id].tsx'),client=new QueryClient({defaultOptions:{queries:{retry:false}}});
 const t=render(React.createElement(QueryClientProvider,{client},React.createElement(Member)));
 for(let i=0;i<5;i++)await act(async()=>{await tick();});
 await act(async()=>{t.root.findByType('SegmentedControl').props.onChange('reviews');await tick();});
 for(let i=0;i<5;i++)await act(async()=>{await tick();});
 await act(async()=>{finishOld([{id:'stale',title:'Old contribution'}]);await tick();});
 assert.deepEqual(t.root.findAllByType('ListItem').map(n=>n.props.title),['Reviewed event']);
 act(()=>t.unmount());client.clear();
});

test('pull refresh stays still during background updates and coalesces explicit gestures',async()=>{
 const e=environment(),{usePullRefresh}=e.load('hooks/usePullRefresh.ts');let control,calls=0,finish;
 function Probe({revision}) { control=usePullRefresh(()=>{calls++;return new Promise(resolve=>finish=resolve);});return React.createElement('Refresh',{refreshing:control.refreshing,revision}); }
 const t=render(React.createElement(Probe,{revision:0}));
 act(()=>t.update(React.createElement(Probe,{revision:1})));
 assert.equal(control.refreshing,false);assert.equal(calls,0);
 let first,second;await act(async()=>{first=control.onRefresh();second=control.onRefresh();await tick();});
 assert.equal(first,second);assert.equal(calls,1);assert.equal(control.refreshing,true);
 await act(async()=>{finish();await first;});assert.equal(control.refreshing,false);
 act(()=>t.unmount());
});
test('cached screens resolve stable safe insets and preserve spacing instead of relaying native layout changes',()=>{
 let name='profile';
 const e=environment({'@react-navigation/native':{useRoute:()=>({name})},'expo-router':{useLocalSearchParams:()=>({})},'react-native-safe-area-context':{SafeAreaView:'NativeSafeArea',useSafeAreaInsets:()=>({top:59,bottom:34,left:0,right:0})}});
 const {SafeAreaView}=e.load('components/navigation/ContentSafeArea.tsx');
 const t=render(React.createElement(SafeAreaView,{edges:['top','bottom'],style:{paddingVertical:8}}));
 assert.equal(t.root.findByType('View').props.style[1].paddingTop,67);
 assert.equal(t.root.findByType('View').props.style[1].paddingBottom,42);
 act(()=>t.update(React.createElement(SafeAreaView,{edges:['top','bottom'],style:{paddingVertical:8}})));
 assert.equal(t.root.findByType('View').props.style[1].paddingTop,67);
 name='event/[id]';act(()=>t.update(React.createElement(SafeAreaView,{edges:['top','bottom'],style:{paddingTop:8}})));
 assert.equal(t.root.findByType('View').props.style[1].paddingTop,8);
 name='profile';act(()=>t.update(React.createElement(SafeAreaView,{edges:{bottom:'maximum'},mode:'margin',style:{marginBottom:48}})));
 assert.equal(t.root.findByType('View').props.style[1].marginBottom,48);
 act(()=>t.unmount());
});
test('Login retains its native safe-area boundary and header-owned top inset',()=>{
 const e=environment({'@react-navigation/native':{useRoute:()=>({name:'auth'})},'expo-router':{useLocalSearchParams:()=>({})},'react-native-safe-area-context':{SafeAreaView:'NativeSafeArea',useSafeAreaInsets:()=>({top:59,bottom:34,left:0,right:0})}});
 const {SafeAreaView}=e.load('components/navigation/ContentSafeArea.tsx');const style={flex:1};
 const t=render(React.createElement(SafeAreaView,{style,edges:['top','bottom']}));
 assert.equal(t.root.findByType('NativeSafeArea').props.style,style);
 assert.equal(t.root.findByType('NativeSafeArea').props.edges.top,'off');assert.equal(t.root.findByType('NativeSafeArea').props.edges.bottom,'additive');
 act(()=>t.unmount());
});

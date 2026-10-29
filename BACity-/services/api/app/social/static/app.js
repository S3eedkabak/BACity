'use strict';
let identity=null,csrf='',section='dashboard',noticeTimer,sessionRecovery=null,lastActivity=Date.now();
const permissions={OWNER:['read','propose','approve','review','publish','staff','audit','access','emergency'],SOCIAL_ADMIN:['read','propose','approve','review','publish','audit'],SOCIAL_EDITOR:['read','propose','review'],SOCIAL_REVIEWER:['read','review'],SOCIAL_VIEWER:['read']};
const $=selector=>document.querySelector(selector);
const can=name=>(permissions[identity?.role]||[]).includes(name);
const titles={dashboard:['Overview','','Daily discoveries, ready for your review.'],publishers:['Publishers','','Add a source. Review it. Approve to start daily checks.'],candidates:['Events to review','','Check the event details before publishing.'],instagram:['Daily checks','','Once a day. Up to two posts per publisher.'],settings:['Settings','','Team, security and advanced controls.'],health:['Check history','','Recent checks and their results.'],staff:['Team access','','Manage who can use this panel.'],audit:['Activity log','','A record of changes made by your team.'],security:['Passkeys & sessions','','Manage your sign-in and backup passkeys.'],diagnostics:['Technical details','','Provider budgets and collection diagnostics.']};
function element(tag,text='',className=''){const n=document.createElement(tag);if(text!==null)n.textContent=String(text);if(className)n.className=className;return n;}
function button(text,action,kind='secondary'){const b=element('button',text,kind);b.type='button';b.addEventListener('click',()=>Promise.resolve(action()).catch(error=>notify(error.message,true)));return b;}
function badge(state){return element('span',String(state||'unknown').replaceAll('_',' '),'badge '+String(state||''));}
function notify(message,error=false){const n=$('#notice');n.textContent=message;n.className=error?'error':'';n.hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>n.hidden=true,7000);}
function showLogin(){identity=null;csrf='';$('#workspace').hidden=true;$('#login').hidden=false;}
async function api(path,{method='GET',body,recover=true}={}){
  const headers={};if(body!==undefined)headers['Content-Type']='application/json';if(method!=='GET')headers['X-CSRF-Token']=csrf;
  const response=await fetch('/api'+path,{method,headers,body:body===undefined?undefined:JSON.stringify(body),credentials:'same-origin',redirect:'error'});
  let data;try{data=await response.json();}catch{throw new Error('The service is unavailable. Your form is still here; try again.');}
  if(!response.ok){
    const detail=typeof data.detail==='string'?data.detail:'Please check the form and try again.';
    const needsIdentity=response.status===401||(response.status===403&&/reauthenticate|recent passkey/i.test(detail));
    if(needsIdentity&&recover&&identity&&!path.startsWith('/auth/')){
      await restoreSession(response.status===403);return api(path,{method,body,recover:false});
    }
    throw new Error(detail);
  }
  return data;
}
const decode=value=>Uint8Array.from(atob(value.replaceAll('-','+').replaceAll('_','/')),c=>c.charCodeAt(0));
const encode=value=>btoa(String.fromCharCode(...new Uint8Array(value))).replaceAll('+','-').replaceAll('/','_').replace(/=+$/,'');
function publicOptions(options){const out={...options,challenge:decode(options.challenge)};if(out.user)out.user={...out.user,id:decode(out.user.id)};for(const key of ['allowCredentials','excludeCredentials'])if(out[key])out[key]=out[key].map(c=>({...c,id:decode(c.id)}));return out;}
function credentialJSON(credential){const r=credential.response,out={id:credential.id,rawId:encode(credential.rawId),type:credential.type,response:{clientDataJSON:encode(r.clientDataJSON)},clientExtensionResults:credential.getClientExtensionResults()};for(const key of ['attestationObject','authenticatorData','signature','userHandle'])if(r[key])out.response[key]=encode(r[key]);if(r.getTransports)out.response.transports=r.getTransports();return out;}
async function passkey(reauth=false,preserve=false){
  if(!window.PublicKeyCredential)throw new Error('Use a browser with passkey support.');
  const options=await api('/auth/'+(reauth?'reauth':'login')+'/options',{method:'POST'});
  const credential=await navigator.credentials.get({publicKey:publicOptions(options)});
  const result=await api('/auth/login/verify',{method:'POST',body:{credential:credentialJSON(credential)}});csrf=result.csrf;
  if(preserve){const previous=identity?.id;identity=await api('/auth/session');csrf=identity.csrf;if(previous&&identity.id!==previous)throw new Error('You signed in as another person. Review your form and submit again.');}else await enter();
}
async function enter(){identity=await api('/auth/session');csrf=identity.csrf;$('#login').hidden=true;$('#workspace').hidden=false;$('#staff-name').textContent=identity.name;$('#staff-role').textContent=identity.role.replaceAll('_',' ');document.querySelectorAll('[data-permission]').forEach(n=>n.hidden=!can(n.dataset.permission));await navigate(section);}
function panel(title,description=''){const root=element('section',null,'panel'),head=element('div',null,'panel-head'),info=element('div');info.append(element('h2',title));if(description)info.append(element('p',description));head.append(info);root.append(head);return {root,head};}
function empty(title,message,action){const n=element('div',null,'empty');n.append(element('span','◎','empty-icon'),element('h3',title),element('p',message));if(action)n.append(action);return n;}
function table(columns,rows){const wrap=element('div',null,'table-wrap'),t=element('table'),head=element('thead'),tr=element('tr'),body=element('tbody');for(const text of columns)tr.append(element('th',text));head.append(tr);for(const cells of rows){const row=element('tr');for(const cell of cells){const td=element('td');td.append(cell instanceof Node?cell:document.createTextNode(String(cell??'—')));row.append(td);}body.append(row);}t.append(head,body);wrap.append(t);return wrap;}
function date(value){if(!value)return 'Not yet';const d=typeof value==='number'?new Date(value*1000):new Date(value);return Number.isNaN(d.getTime())?'Unknown':new Intl.DateTimeFormat('en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Bratislava'}).format(d);}
function labelled(primary,secondary){const n=element('div');n.append(element('strong',primary),element('small',secondary));return n;}
function link(url,text='View original ↗'){const a=element('a',text);a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}
function dialog(title){$('#modal-title').textContent=title;$('#modal-body').replaceChildren();if(!$('#modal').open)$('#modal').showModal();return $('#modal-body');}
function close(){if($('#modal').open)$('#modal').close();}
function field(form,name,label,type='text',value='',options){const l=element('label',label),n=element(options?'select':type==='textarea'?'textarea':'input');n.name=name;if(options){for(const [v,t] of options){const o=element('option',t);o.value=v;n.append(o);}}else if(type!=='textarea')n.type=type;n.value=value??'';l.append(n);form.append(l);return n;}
function submit(form,label,handler){const b=element('button',label,'primary');b.type='submit';form.append(b);form.addEventListener('submit',async event=>{event.preventDefault();b.disabled=true;try{await handler(new FormData(form));}catch(error){notify(error.message,true);}finally{b.disabled=false;}});}
function finish(message){close();notify(message);return navigate(section);}
async function navigate(next){section=next;const [title,eyebrow,description]=titles[next];$('#page-title').textContent=title;$('#section-eyebrow').textContent=eyebrow;$('#page-description').textContent=description;document.querySelectorAll('[data-section]').forEach(n=>{if(n.dataset.section===next)n.setAttribute('aria-current','page');else n.removeAttribute('aria-current');});const content=$('#content');content.replaceChildren(element('p','Loading your workspace…'));try{await ({instagram:instagram,dashboard:dashboard,publishers:publishers,candidates:candidates,health:health,staff:staff,audit:audit,security:security,settings:settingsPage,diagnostics:providerDiagnostics}[next])(content);}catch(error){content.replaceChildren(empty('Unable to load this section',error.message,button('Try again',()=>navigate(next))));}}
function jobTable(jobs){return table(['Publisher','Result','When','New posts'],jobs.map(j=>[j.publisher_name||'Publisher',labelled(humanStatus(j.state),j.error?friendlyError(j.error):''),date(j.finished||j.created),j.metrics?.new_observations??'—']));}
async function dashboard(content){
  const d=await api('/dashboard');content.replaceChildren();
  const banner=element('div',null,'mode-banner'),copy=element('div');
  copy.append(element('h3',d.emergency_stop?'All checks are paused':d.collection_enabled?'Daily checks are on':'Daily checks are paused'),element('p','Add a publisher, review it, then approve to start. Up to two posts per daily check.'));
  banner.append(copy);if(can('propose'))banner.append(button('Add publisher',()=>publisherForm(),'primary'));content.append(banner);
  const stats=element('div',null,'stats');
  for(const [label,value,note] of [['Awaiting approval',d.pending,'Review new publishers'],['Active publishers',d.enabled,'Checked automatically each day'],['Events to review',d.awaiting_review,'Check details before publishing']]){
    const card=element('div',null,'stat');card.append(element('span',label),element('strong',value),element('small',note));stats.append(card);
  }
  content.append(stats);const history=panel('Latest checks','A completed check can find posts without finding an event.');
  history.root.append(d.recent_jobs.length?jobTable(d.recent_jobs):empty('No checks yet','Approve your first publisher to start automatic checks.',button('View publishers',()=>navigate('publishers'))));content.append(history.root);
  if(!d.publication_enabled)content.append(element('p','Events stay private here while publishing is switched off.','fine'));
}
async function publishers(content){
  const toolbar=element('form',null,'toolbar');toolbar.setAttribute('role','search');
  const q=element('input');q.placeholder='Search publishers';q.setAttribute('aria-label','Search publishers');
  toolbar.append(q,button('Search',load));if(can('propose'))toolbar.append(button('＋ Add publisher',()=>publisherForm(),'primary'));
  const results=element('div');content.replaceChildren(toolbar,results);
  toolbar.addEventListener('submit',event=>{event.preventDefault();load().catch(e=>notify(e.message,true));});
  async function load(){
    const data=await api('/publishers?q='+encodeURIComponent(q.value));const list=panel('Your publishers',data.total+' publishers · Daily checks · Up to 2 posts each');
    list.root.append(data.items.length?table(['Publisher','Status','Last check',''],data.items.map(p=>[
      labelled(p.name,p.platform==='instagram'?'@'+p.external_id:'Event page'),publisherStatus(p),
      labelled(date(p.last_attempt),p.last_error?friendlyError(p.last_error):p.last_success?'Completed':'Not checked yet'),
      button(p.approval==='pending'&&can('approve')?'Review →':'View →',()=>publisherDetail(p.id))
    ])):empty('Add your first publisher','Paste a profile link and a few details. Nothing is checked until you approve it.'));
    results.replaceChildren(list.root);
  }
  await load();
}
function publisherForm(existing){
  const body=dialog(existing?'Edit publisher':'Add publisher'),form=element('form');
  body.append(element('p','Add a source for event discovery. We will wait for your approval before checking it.'),form);
  const url=field(form,'url','Instagram profile or event-page link','text',existing?.url||'');url.required=true;url.maxLength=1024;if(existing)url.readOnly=true;
  const name=field(form,'name','Publisher name','text',existing?.name||'');name.required=true;name.maxLength=160;
  field(form,'publisher_type','Type','text',existing?.publisher_type||'venue',[['venue','Venue'],['organizer','Organizer'],['promoter','Promoter'],['artist','Artist'],['cultural_institution','Cultural institution'],['community','Community'],['other','Other']]);
  const relevance=field(form,'relevance','What events do they share?','textarea',existing?.relevance||'');relevance.required=true;relevance.minLength=10;relevance.maxLength=500;relevance.placeholder='For example: concerts and club nights in Bratislava';
  const details=element('details');details.append(element('summary','Venue details (optional)'));form.append(details);
  field(details,'venue_name','Venue name','text',existing?.venue_name||'');field(details,'address','Venue address','text',existing?.address||'');
  body.append(element('p','Daily checks · Up to 2 posts · Approval required before starting','schedule-note'));
  submit(form,existing?'Save for review':'Add for review',async data=>{
    const payload=Object.fromEntries(data);for(const key of ['venue_name','address'])payload[key]=payload[key]||null;
    if(existing){payload.latitude=existing.latitude;payload.longitude=existing.longitude;}
    const saved=await api('/publishers'+(existing?'/'+existing.id:''),{method:existing?'PATCH':'POST',body:payload});
    await finish('Publisher saved. Waiting for approval.');if(can('approve'))await publisherDetail(saved.id);
  });
}
async function publisherDetail(id){
  const data=await api('/publishers/'+id),p=data.publisher,body=dialog(p.name);
  body.append(publisherStatus(p));const details=element('dl',null,'review-details');
  for(const [label,value] of [['Source',p.url],['Type',humanStatus(p.publisher_type)],['About',p.relevance],['Venue',p.venue_name],['Address',p.address],['Location',p.latitude!=null&&p.longitude!=null?p.latitude+', '+p.longitude:null],['Schedule','Once a day · Up to 2 posts']]){
    if(value){details.append(element('dt',label),element('dd',value));}
  }
  body.append(details,link(p.url,'Open original source ↗'));
  const actions=element('div',null,'actions main-actions');
  if(can('approve')){
    if(p.enabled)actions.append(button('Pause checks',async()=>{await api('/publishers/'+p.id+'/monitoring',{method:'POST',body:{enabled:false}});await finish('Checks paused.');},'secondary'));
    else if(!['blocked','unsupported','rate_limited'].includes(p.eligibility)){
      const form=element('form',null,'approval-form'),label=element('label',null,'check-label'),check=element('input');check.type='checkbox';check.name='confirmed';check.required=true;
      label.append(check,document.createTextNode('I reviewed this source and approve its public content for BACity event discovery.'));form.append(label);
      submit(form,p.approval==='pending'?'Approve & start daily checks':'Start daily checks',async()=>{
        await api('/publishers/'+p.id+'/approve-and-start',{method:'POST',body:{confirmed:true,reviewed_updated:p.updated}});await finish('Approved. The first check will start shortly.');
      });body.append(form);
    }else body.append(element('p','This source needs an owner to review an access problem before checks can restart.','missing'));
  }
  if(can('propose'))actions.append(button('Edit details',()=>publisherForm(p)));
  body.append(actions,element('p','Last check: '+date(p.last_attempt)+' · Next check: '+(nextCheck(p)),'fine'));
  if(p.last_error)body.append(element('p',friendlyError(p.last_error),'missing'));
  const history=element('details');history.append(element('summary','Recent checks & collected posts'));
  history.append(data.jobs.length?jobTable(data.jobs):element('p','No checks yet. Approval starts the first check automatically.'));
  for(const o of data.observations){const item=element('article',null,'collected-post');item.append(element('h3',date(o.observed)));if(o.filter_reason)item.append(element('p',o.filter_reason==='giveaway'?'Giveaway · no confirmed event schedule. Draw and deadline dates are not party dates.':'No standalone event found in this caption.','fine'));if(o.has_images)item.append(postGallery(o.id));item.append(element('pre',o.caption),link(o.source_url));history.append(item);}body.append(history);
  if(can('approve')||can('access')){
    const more=element('details',null,'advanced-details'),row=element('div',null,'actions');more.append(element('summary','More options'));
    if(can('approve')){row.append(button('Reject publisher',()=>decisionForm(p,'rejected')),button('Suspend publisher',()=>decisionForm(p,'suspended'),'danger'));}
    if(can('access'))row.append(button('Advanced access settings',()=>accessForm(p)));
    if(can('propose'))row.append(button('Add a post manually',()=>evidenceForm(p)));
    more.append(row);body.append(more);
  }
}
function decisionForm(p,decision){const body=dialog(decision==='suspended'?'Suspend publisher':'Reject publisher'),form=element('form');body.append(element('p','This stops automatic checks for this publisher.'),form);const note=field(form,'note','Reason','textarea');note.required=true;note.minLength=10;submit(form,'Confirm',async data=>{await api('/publishers/'+p.id+'/decision',{method:'POST',body:{decision,note:data.get('note')}});await finish('Publisher updated.');});}
function accessForm(p){const body=dialog('Collection access'),form=element('form');body.append(element('p','Only record permission you have verified. This setting cannot override robots rules, login walls, rate limits or platform restrictions.'),form);field(form,'eligibility','Technical access','text',p.eligibility==='rate_limited'?'blocked':p.eligibility,[['authorization_required','Authorization required'],['available','Available with verified permission'],['unsupported','Unsupported'],['blocked','Blocked']]);field(form,'method','Acquisition method','text',p.method==='submission'&&p.platform==='instagram'&&p.target_type==='profile'?(p.default_provider||'apify'):p.method,[['submission','Permitted evidence submission'],['http','Lightweight public HTTP'],['browser','Isolated browser'],...(p.platform==='instagram'&&p.target_type==='profile'?[['apify','Apify · latest items'],['scrapingant','ScrapingAnt · public feed']]:[])]);const basis=field(form,'permission_basis','Evidence of platform permission and permitted purpose','textarea',p.permission_basis);basis.required=true;basis.minLength=10;const expires=field(form,'expires','Permission expiry (within 90 days)','date');expires.required=true;submit(form,'Record access review',async data=>{await api('/publishers/'+p.id+'/access',{method:'POST',body:{eligibility:data.get('eligibility'),method:data.get('method'),permission_basis:data.get('permission_basis'),permission_expires:new Date(data.get('expires')+'T00:00:00Z').getTime()/1000}});await finish('Access review saved. Monitoring remains paused until enabled.');});}
function evidenceForm(p){const body=dialog('Submit permitted post evidence'),form=element('form');body.append(element('p','Provide the original post text you are permitted to process. BACity extracts candidates automatically; this is submitted evidence, not a live collection result.'),form);field(form,'source_url','Direct original post URL','url',p.target_type==='post'?p.url:'').required=true;field(form,'caption','Original caption or announcement','textarea').required=true;field(form,'published_at','Original publication timestamp (optional, with timezone)','text','');const attest=field(form,'permission_attestation','Why may BACity process this evidence?','textarea');attest.required=true;attest.minLength=20;submit(form,'Stage evidence privately',async data=>{const source=await api('/publishers/preview',{method:'POST',body:{url:data.get('source_url')}});await api('/publishers/'+p.id+'/evidence',{method:'POST',body:{source_url:source.url,external_id:source.external_id,caption:data.get('caption'),published_at:data.get('published_at')||null,permission_attestation:data.get('permission_attestation')}});await finish('Evidence staged. Extracted candidates remain private.');});}
async function candidates(content,all=false){const data=await api('/candidates?view='+(all?'all':'active'));content.replaceChildren();const controls=element('div',null,'actions');controls.append(button(all?'Back to review queue':'Show past decisions',()=>candidates(content,!all)));content.append(controls);if(!data.items.length){const p=panel('Event review queue');p.root.append(empty('Nothing awaiting your judgment.','Collected posts appear in Publishers. Giveaways, entry instructions and repeated announcements do not become separate events.'));content.append(p.root);return;}const cards=element('div',null,'cards');for(const c of data.items){const card=element('article',null,'candidate'),top=element('div',null,'candidate-top');top.append(badge(c.method),badge(c.status));card.append(top,element('h2',c.fields.title||'Untitled announcement'));const dl=element('dl');for(const [k,v]of [['When',c.fields.start_time?date(c.fields.start_time):(c.fields.event_date||'Date unknown')+' · time unconfirmed'],['Where',c.fields.venue_name||'Venue unconfirmed'],['Source',c.fields.evidence?.method==='local_poster_ocr_v1'?'Text read from the poster':c.method==='user_submission'?'Staff-submitted evidence':'Post caption']])dl.append(element('dt',k),element('dd',v));card.append(dl,link(c.source_url));if(c.media?.length)card.append(postGallery(c.observation_id));if(c.missing.length)card.append(element('p','Needs checking: '+c.missing.map(v=>v.replaceAll('_',' ')).join(', '),'missing'));const evidence=element('details');evidence.append(element('summary','Read original evidence'),element('pre',c.caption),element('p','Original publication: '+date(c.published_at),'fine'));card.append(evidence);const actions=element('div',null,'actions'),extra=element('details'),extraActions=element('div',null,'actions');extra.append(element('summary','More options'),extraActions);extraActions.append(button('Compare existing events',async()=>{const result=await api('/candidates/'+c.id+'/matches');const body=dialog('Similar events');body.append(element('p',result.classification.replaceAll('_',' ')));for(const match of result.matches)body.append(element('p',match.title+' · '+match.reason));if(!result.matches.length)body.append(element('p',result.scope||'Insufficient evidence for comparison.'));}));if(can('propose'))actions.append(button('Edit event details',()=>candidateEdit(c)));if(can('review')&&['needs_review','qualified'].includes(c.status))actions.append(button('Review event',()=>candidateReview(c),'primary'));if(can('publish')&&c.status==='approved')actions.append(button('Publish event',async()=>{await api('/candidates/'+c.id+'/publish',{method:'POST'});await finish('Publication queued after independent review.');},'primary'));card.append(actions,extra);cards.append(card);}content.append(cards);}
function candidateEdit(c){const body=dialog('Correct candidate metadata'),form=element('form');body.append(element('p','Keep corrections tied to the original evidence. Editing resets approval; a different person must review it.'),form);field(form,'title','Event title','text',c.fields.title).required=true;const start=c.fields.start_time?new Date(c.fields.start_time):null;const local=start?new Date(start-start.getTimezoneOffset()*60000).toISOString().slice(0,16):'';field(form,'start_time','Start time · your device time zone','datetime-local',local).required=true;field(form,'venue_name','Verified venue','text',c.fields.venue_name).required=true;field(form,'address','Verified address','text',c.fields.address).required=true;for(const key of ['latitude','longitude']){const f=field(form,key,key,'number',c.fields[key]);f.step='any';f.required=true;}const note=field(form,'note','Evidence for this correction','textarea');note.required=true;note.minLength=10;submit(form,'Save for independent review',async data=>{const payload=Object.fromEntries(data);payload.start_time=new Date(payload.start_time).toISOString();payload.latitude=Number(payload.latitude);payload.longitude=Number(payload.longitude);await api('/candidates/'+c.id,{method:'PATCH',body:payload});await finish('Metadata saved. Approval was reset.');});}
function candidateReview(c){const body=dialog('Review event'),form=element('form');body.append(element('p','Verify the date, venue and original evidence. Approval keeps the event private until a different authorized person requests publication.'),form);field(form,'decision','Decision','text','approved',[['approved','Approve event'],['rejected','Reject candidate']]);const note=field(form,'note','Review rationale','textarea');note.required=true;note.minLength=10;submit(form,'Record review',async data=>{await api('/candidates/'+c.id+'/review',{method:'POST',body:Object.fromEntries(data)});await finish('Review recorded.');});}
async function health(content){const data=await api('/health'),p=panel('Collection history','No successful collection is inferred from approval, an HTTP shell or a login wall.');p.head.append(badge(data.publication_mode));p.root.append(data.jobs.length?jobTable(data.jobs):empty('No collection attempts.','Monitoring begins only for an enabled, approved publisher with current technical access.'));const metrics=table(['Platform','Collections','Received content','Candidates','Published'],data.platforms.map(x=>[x.platform,x.successful_collections+' / '+x.collections,x.observations,x.event_candidates,x.published_events]));content.replaceChildren(p.root,metrics);}
async function staff(content){const data=await api('/staff'),p=panel('Your staff team','No public administrator registration or consumer entitlement grants.');p.head.append(button('Invite staff member',staffForm,'primary'));p.root.append(table(['Person','Role','Status','Passkeys',''],data.map(s=>[labelled(s.name,s.email),badge(s.role),s.active?'Active':'Suspended',s.authenticators,button('Manage',()=>manageStaff(s))])));content.replaceChildren(p.root);}
function staffForm(){const body=dialog('Invite a staff member'),form=element('form');body.append(element('p','Use a personal identity. The one-use enrollment invitation expires after 15 minutes and must be delivered privately.'),form);field(form,'name','Full name').required=true;field(form,'email','Individual email address','email').required=true;field(form,'role','Role','text','SOCIAL_EDITOR',Object.keys(permissions).map(v=>[v,v.replaceAll('_',' ')]));submit(form,'Create invitation',async data=>{const result=await api('/staff',{method:'POST',body:Object.fromEntries(data)});showInvitation(result.invitation);});}
function showInvitation(value){const body=dialog('One-use enrollment invitation');body.append(element('p','Deliver this privately to the intended staff member. They enter it under “Joining the team?” and register their own passkey. Do not add it to a URL.'));const token=element('textarea',value,'token');token.readOnly=true;token.setAttribute('aria-label','One-use invitation');body.append(token,element('p','Expires in 15 minutes. This value is shown only now.','fine'));}
function manageStaff(s){const body=dialog('Manage '+s.name),form=element('form');body.append(element('p','Access changes immediately revoke this person’s existing sessions and invitations.'),form);field(form,'role','Role','text',s.role,Object.keys(permissions).map(v=>[v,v.replaceAll('_',' ')]));field(form,'active','Account status','text',String(s.active),[['true','Active'],['false','Suspended']]);submit(form,'Update and revoke sessions',async data=>{await api('/staff/'+s.id,{method:'PATCH',body:{role:data.get('role'),active:data.get('active')==='true'}});await finish('Staff access updated. Existing sessions were revoked.');});body.append(element('h3','Lost authenticators?'),element('p','First verify this person’s identity through your established staff process. Recovery revokes every old passkey and session.','fine'),button('Issue recovery invitation',async()=>{const result=await api('/staff/'+s.id+'/recover',{method:'POST'});showInvitation(result.invitation);},'danger'));}
async function audit(content){const data=await api('/audit'),p=panel('Privileged activity','Append-only records with a hash chain. Protected off-process exports are operated on the private host.');p.root.append(data.length?table(['When','Actor','Action','Result','Record'],data.map(x=>[date(x.timestamp),x.actor?.slice(0,12)||'Unknown',x.action,badge(x.result),labelled('#'+x.sequence,x.digest.slice(0,16)+'…')])):empty('No audit events.','Staff authentication and privileged changes appear here.'));content.replaceChildren(p.root);}
async function security(content){const keys=await api('/auth/credentials'),p=panel('Personal authenticators','Register at least two authenticators. Revoking a passkey also revokes its sessions.');p.root.append(table(['Authenticator','Registered',''],keys.map(k=>[k.label,date(k.created),button('Revoke',async()=>{await api('/auth/credentials/'+encodeURIComponent(k.id),{method:'DELETE'});await navigate('security');})])));const actions=element('div',null,'detail-section');actions.append(element('div',null,'actions'));actions.firstChild.append(button('Reverify identity',()=>passkey(true),'primary'),button('Register backup passkey',async()=>{const options=await api('/auth/register/options',{method:'POST',body:{}});const credential=await navigator.credentials.create({publicKey:publicOptions(options)});const label=credential.authenticatorAttachment==='platform'?'Device passkey':'Backup security key';const result=await api('/auth/register/verify',{method:'POST',body:{credential:credentialJSON(credential),label}});csrf=result.csrf;await enter();notify('Backup authenticator registered.');}),button('Sign out all devices',async()=>{await api('/auth/logout-all',{method:'POST'});showLogin();}));p.root.append(actions);content.replaceChildren(p.root);}
function emergencyForm(stopped){const body=dialog(stopped?'Release emergency stop':'Pause all Level 4 activity'),form=element('form');body.append(element('p',stopped?'Releasing the stop does not re-enable publishers. Review each source before resuming.':'This immediately disables monitoring, cancels jobs and withdraws pending publication requests. Levels 1–3 continue unchanged.'),form);const note=field(form,'note','Reason','textarea');note.required=true;note.minLength=10;submit(form,stopped?'Release stop':'Stop Level 4',async data=>{await api('/emergency',{method:'POST',body:{stopped:!stopped,note:data.get('note')}});await finish('Emergency control updated.');});}
$('#sign-in').addEventListener('click',()=>passkey().catch(error=>notify(error.name==='NotAllowedError'?'Passkey sign-in was cancelled or unavailable.':error.message,true)));
$('#enroll').addEventListener('submit',async event=>{event.preventDefault();const form=event.currentTarget,b=form.querySelector('button');b.disabled=true;try{const data=new FormData(form),options=await api('/auth/register/options',{method:'POST',body:{invitation:data.get('invitation')}});const credential=await navigator.credentials.create({publicKey:publicOptions(options)});const result=await api('/auth/register/verify',{method:'POST',body:{credential:credentialJSON(credential),label:data.get('label')}});csrf=result.csrf;form.reset();await enter();}catch(error){notify(error.message,true);}finally{b.disabled=false;}});
$('#close-modal').addEventListener('click',close);$('#modal').addEventListener('close',()=>{if(!$('#modal').open)$('#modal-body').replaceChildren();});$('#refresh').addEventListener('click',()=>navigate(section));$('#logout').addEventListener('click',()=>api('/auth/logout',{method:'POST'}).then(showLogin).catch(error=>notify(error.message,true)));document.querySelectorAll('[data-section]').forEach(n=>n.addEventListener('click',()=>navigate(n.dataset.section)));enter().catch(showLogin);

async function providerDiagnostics(content){
  const data=await api('/instagram-collection');
  const summary=panel('Instagram collection','Only approved profiles with current permission are checked. A successful check does not imply an event was found.');
  summary.head.append(badge(data.configured||data.apify.configured?'Configured':'Not configured'),badge((data.enabled||data.apify.enabled)&&data.collection_enabled?'Acquisition enabled':'Acquisition disabled'));
  const stats=element('div',null,'stats');
  for(const [title,value,note] of [
    ['Active profiles',data.active_profiles+' / '+data.max_profiles,'At most one attempt every '+data.interval_hours+' hours'],
    ['ScrapingAnt credits left',data.needs_sync?'Not verified':data.remaining_budget,'After your '+data.credit_reserve+' credit reserve'],
    ['ScrapingAnt credits used',data.accounted_credits,data.precision.replaceAll('_',' ')],
    ['Event candidates',data.event_candidates,'Private; existing review rules apply']]){
    const card=element('div',null,'stat');card.append(element('span',title),element('strong',value),element('small',note));stats.append(card);
  }
  const summaryBody=element('div',null,'detail-section');summary.root.append(summaryBody);
  summaryBody.append(stats,element('p','ScrapingAnt billing period: '+date(data.period_start)+' — '+date(data.period_end),'fine'),
    element('p','ScrapingAnt last scheduled check: '+date(data.last_scheduled_run)+' · Usage last verified: '+date(data.last_usage_sync),'fine'),
    element('p','ScrapingAnt requests: '+data.requests+' content + '+data.usage_requests+' account checks · Provider-reported credits: '+data.reported_credits+' · Estimated: '+data.estimated_credits+' · In flight: '+data.reserved_credits,'fine'));
  if(data.suspension_reason)summaryBody.append(element('p','ScrapingAnt attention: '+data.suspension_reason.replaceAll('_',' '),'missing'));
  if(can('propose'))summaryBody.append(button('Add Instagram publisher',()=>publisherForm(),'primary'));
  const sources=panel('Monitored publishers','Pause to remove a publisher from active monitoring. Suspension requires approval before reactivation.');
  sources.root.append(data.publishers.length?table(['Publisher','Provider / limit','Approval','Monitoring','Eligibility','Last attempt / success','Latest error',''],data.publishers.map(p=>[
    labelled(p.name,p.external_id),p.method+' / '+p.posts_per_profile,badge(p.approval),p.enabled?'Active':'Paused',badge(p.eligibility),labelled(date(p.last_attempt),date(p.last_success)),p.last_error||'None',button('Manage',()=>publisherDetail(p.id))
  ])):empty('No Instagram profiles configured.','Add a profile, approve it, review collection permission and enable monitoring.'));
  const history=panel('Recent checks','Discovery counts cover at most the 50 latest checks. Feed windows are bounded; not every historical post is fetched.');
  history.root.append(data.jobs.length?table(['When','Outcome','Posts / Reels found','New posts / Reels','Candidates','Error'],data.jobs.map(j=>[
    date(j.finished||j.created),badge(j.state),(j.metrics.posts_discovered??0)+' / '+(j.metrics.reels_discovered??0),
    (j.metrics.new_posts??0)+' / '+(j.metrics.new_reels??0),j.metrics.new_candidates??0,j.error||'None'
  ])):empty('No collection attempts.','Checks are spread across the day. The permitted test action can start the first check sooner.'));
  const ap=panel('Apify · official Instagram Scraper','One shared registry and daily schedule. No automatic second-provider fallback.');
  const a=data.apify,body=element('div',null,'detail-section');ap.root.append(body);
  ap.head.append(badge(a.configured?'Token configured':'Token missing'),badge(a.enabled?'Provider enabled':'Provider disabled'));
  const usd=v=>'$'+(v/1000000).toFixed(4);
  body.append(element('p','Actor: '+a.actor+' · Preferred provider for new profiles: '+data.default_provider),
    element('p','Monthly ceiling '+usd(a.budget_micro_usd)+' · Reserve '+usd(a.reserve_micro_usd)+' · Accounted '+usd(a.spent_micro_usd)+' · In flight '+usd(a.reserved_micro_usd)),
    element('p','Remaining internal budget: '+(a.needs_sync?'Not verified':usd(a.remaining_micro_usd))+' · Billing period '+date(a.period_start)+' — '+date(a.period_end)),
    element('p','Estimated charges / safety allowance: '+usd(a.estimated_micro_usd)+' · Last billing sync '+date(a.last_sync),'fine'),
    element('p',a.coverage,'fine'),element('p','Daily checks collect up to two posts per publisher. Posts outside that window may be missed.','fine'));
  if(a.suspension_reason)body.append(element('p','Attention: '+a.suspension_reason.replaceAll('_',' '),'missing'));
  if(data.apify_runs.length)body.append(table(['Batch','State','Actor status','Billing','Error'],data.apify_runs.map(r=>[
    date(r.created),badge(r.state),r.provider_status||'Not launched',r.cost_kind?(r.cost_kind.replaceAll('_',' ')+' · '+(r.cost===null?'unknown':usd(r.cost))):'reserved '+usd(r.reservation),r.error||'None'
  ])));
  content.replaceChildren(ap.root,summary.root,sources.root,history.root);
}


function humanStatus(value){return ({queued:'Waiting to start',running:'Checking now',success:'Completed',empty:'Completed · no new posts',partial:'Needs review',failed:'Check failed',cancelled:'Stopped',pending:'Awaiting approval',approved:'Approved',needs_review:'Needs review',qualified:'Ready to review',authorization_required:'Awaiting approval',blocked:'Needs attention',rate_limited:'Temporarily limited',suspended:'Suspended',venue:'Venue',organizer:'Organizer',other:'Other'})[value]||String(value||'').replaceAll('_',' ');}
function publisherStatus(p){
  const state=p.approval==='pending'?'pending':p.approval!=='approved'?p.approval:['blocked','unsupported','rate_limited'].includes(p.eligibility)?'blocked':p.enabled?'success':'paused';
  const b=badge(state);b.textContent=state==='success'?'Daily checks on':state==='paused'?'Paused':humanStatus(state);return b;
}
function friendlyError(value){return ({budget_exhausted:'Checks paused: the spending limit has been reached.',billing_unverified:'Waiting for the provider to verify the available budget.',usage_unverified:'Waiting for the provider to verify the available budget.',no_items_unverified:'No recent posts could be confirmed.',older_item_skipped:'No newer posts found.',pinned_item_skipped:'Pinned posts skipped.',access_denied:'The source is not allowing collection.',login_required:'This source requires a login and cannot be checked.',provider_auth:'The owner needs to check the provider connection.',network_error:'Connection problem. Results already saved will be retried.',worker_timeout:'The check took too long.',cancelled:'Checks stopped.',rate_limit:'The provider asked us to wait.'})[value]||'Check needs attention. See Settings → Technical details ('+String(value).replaceAll('_',' ')+').';}
async function instagram(content){
  const d=await api('/instagram-collection'),list=panel('Daily checks','Automatic after approval · Up to two posts per publisher · Spending limits remain active');
  if(!d.collection_enabled)list.root.append(element('p','Automatic checks are switched off. Ask the owner to review Settings.','missing'));
  list.root.append(d.publishers.length?table(['Publisher','Status','Last check','Next check'],d.publishers.map(p=>[
    button(p.name,()=>publisherDetail(p.id),'text-button'),publisherStatus(p),labelled(date(p.last_attempt),p.last_error?friendlyError(p.last_error):p.last_success?'Completed':'Not checked yet'),nextCheck(p)
  ])):empty('No publishers yet','Add a profile and approve it to begin.',button('Add publisher',()=>publisherForm(),'primary')));
  const recent=panel('Recent results','Collected posts appear in each publisher. Extracted events appear in Events to review.');recent.root.append(d.jobs.length?jobTable(d.jobs):empty('Waiting for the first check','Approved sources are picked up automatically.'));
  content.replaceChildren(list.root,recent.root);
}
async function settingsPage(content){
  const cards=element('div',null,'settings-grid');
  for(const [target,title,description,permission] of [['staff','Team access','Invite your cofounder and manage roles.','staff'],['security','Passkeys & sessions','Backup passkeys and device access.','read'],['audit','Activity log','See who changed what.','audit'],['diagnostics','Technical details','Provider budgets and service status.','read'],['health','Full check history','Inspect previous collection results.','read']]){
    if(!can(permission))continue;const card=element('section',null,'setting-card');card.append(element('h2',title),element('p',description),button('Open →',()=>navigate(target)));cards.append(card);
  }
  content.replaceChildren(cards);
  if(can('emergency')){const d=await api('/dashboard'),p=panel('Pause all checks','Use this if the whole collection system needs to stop.');p.root.append(button(d.emergency_stop?'Review system pause':'Pause all checks',()=>emergencyForm(d.emergency_stop),'danger'));content.append(p.root);}
}
function restoreSession(reauth){
  if(sessionRecovery)return sessionRecovery;
  sessionRecovery=new Promise((resolve,reject)=>{
    const modal=$('#session-modal'),action=$('#session-continue'),cancel=$('#session-cancel'),error=$('#session-error');error.textContent='';
    const cleanup=()=>{action.onclick=null;cancel.onclick=null;modal.oncancel=null;modal.close();sessionRecovery=null;};
    action.onclick=async()=>{action.disabled=true;try{await passkey(reauth,true);cleanup();resolve();}catch(e){error.textContent=e.name==='NotAllowedError'?'Verification cancelled. Your form is still saved on screen.':e.message;}finally{action.disabled=false;}};
    const abort=()=>{cleanup();reject(new Error('Your changes are still in the form. Submit again when you are ready.'));};cancel.onclick=abort;modal.oncancel=e=>{e.preventDefault();abort();};modal.showModal();
  });return sessionRecovery;
}
for(const event of ['pointerdown','keydown','input','scroll'])document.addEventListener(event,()=>{lastActivity=Date.now();},{passive:true});
setInterval(async()=>{
  if(!identity||document.visibilityState!=='visible'||Date.now()-lastActivity>120000)return;
  try{await api('/auth/session',{recover:false});}catch{/* Submission restores identity without clearing the form. */}
},120000);

function nextCheck(p){if(!p.enabled)return p.approval==='pending'?'After approval':'Paused';const due=Math.max(p.next_due,(p.last_attempt||0)+86400);return due<=Date.now()/1000?'Starting shortly':date(due);}
setInterval(()=>{if(identity&&document.visibilityState==='visible'&&Date.now()-lastActivity<120000&&!$('#modal').open&&!$('#session-modal').open&&['dashboard','instagram'].includes(section))navigate(section);},15000);

function postGallery(observationId){
  const root=element('section',null,'post-gallery');root.setAttribute('aria-label','Post images');
  let checks=0;
  async function load(){
    if(!root.isConnected)return;
    try{
      const data=await api('/observations/'+encodeURIComponent(observationId)+'/images');root.replaceChildren();
      let processing=!data.images.length&&data.has_images;
      for(const asset of data.images){
        const figure=element('figure',null,'post-image');
        if(asset.url){
          const a=link(asset.url,'');a.setAttribute('aria-label','Open post image');
          const img=element('img');img.src=asset.url;img.alt='Image from the original post';img.loading='lazy';img.decoding='async';img.referrerPolicy='no-referrer';img.width=asset.width;img.height=asset.height;
          img.addEventListener('error',()=>{a.replaceChildren(element('p','Image unavailable. You can still open the original post.','fine'));},{once:true});a.append(img);figure.append(a);
        }
        if(asset.ocr_text){const text=element('details');text.append(element('summary','Text read from this image'),element('pre',asset.ocr_text),element('p','Automatically read from the poster. Check names, dates and times before approving.','fine'));figure.append(text);}
        else if(asset.state==='ready')figure.append(element('figcaption',asset.ocr_status==='no_text'?'No readable text found in this image.':'Poster text could not be read. The image and caption are still available.','fine'));
        else if(['queued','running'].includes(asset.state)){processing=true;figure.append(element('p','Preparing image and reading poster text…','fine'));}
        else figure.append(element('p','This image could not be retrieved. The original post and caption are still available.','fine'));
        root.append(figure);
      }
      if(!data.images.length&&data.has_images)root.append(element('p','Preparing post images…','fine'));
      if(processing&&++checks<60)setTimeout(load,5000);
    }catch{root.replaceChildren(element('p','Post images are temporarily unavailable. Your caption is still saved.','fine'));}
  }
  setTimeout(load,0);return root;
}

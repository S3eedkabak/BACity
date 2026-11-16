"""Render the real exported app with isolated, explicitly synthetic API fixtures."""
import argparse
import functools
import json
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[3]
STAFF = ROOT/'services/api/app/social/static'
USER = dict(id='11111111-1111-4111-8111-111111111111',email='design-fixture@example.test',display_name='Alex · design fixture',interests=['Culture','Music'],role='USER',email_verified=True,identity_verified=False,reputation=0,bio='Finding a little more of Bratislava, one weekend at a time.',city='Bratislava',neighborhood='Staré Mesto',avatar_url=None,public_profile=True,allow_general_messages=False)
EVENTS=[]
for i,(title,category,venue,price) in enumerate([
 ('Along the Danube at golden hour','Culture','Danube riverfront',0),
 ('An evening of contemporary jazz','Music','Old Town studio',14),
 ('Design market at the old refinery','Markets','Jurkovič heating plant',0),
 ('A slower Sunday: ceramics workshop','Workshops','Creative courtyard',28),
 ('New perspectives: an exhibition of contemporary photography and the city we share','Arts','City gallery',None),
]):
 EVENTS.append(dict(id=f'22222222-2222-4222-8222-{i+1:012}',title=title,description='Synthetic event for design review. Explore a different side of the city with a small local gathering. This is fixture content, not a real listing.',start_time=f'2026-11-{21+i:02}T18:00:00+01:00',end_time=f'2026-11-{21+i:02}T21:00:00+01:00',timezone='Europe/Bratislava',address='Bratislava, Slovakia',latitude=48.143+i*.003,longitude=17.106+i*.002,category=category,tags=['design-fixture'],price=price,currency='EUR',image_url='http://127.0.0.1:18742/fixture-city.jpg' if i==0 else None,source_url='https://example.test/design-fixture',language='en',status='fresh',extraction_confidence=1,source_reliability=1,venue=dict(id=f'33333333-3333-4333-8333-{i+1:012}',name=venue,address='Bratislava',latitude=48.143+i*.003,longitude=17.106+i*.002),created_at='2026-11-14T09:00:00Z',updated_at='2026-11-14T09:00:00Z'))

class Handler(SimpleHTTPRequestHandler):
 def do_GET(self):
  if self.path=='/fixture-city.jpg':
   data=(ROOT/'apps/mobile/assets/video/bratislava-poster.jpg').read_bytes()
   self.send_response(200);self.send_header('Content-Type','image/jpeg');self.end_headers();self.wfile.write(data);return
  if self.path.startswith('/staff/'):
   self.path='/'+self.path.removeprefix('/staff/')
   self.directory=str(STAFF)
  elif self.path.startswith('/assets/') and (STAFF/self.path.split('/')[-1]).is_file():
   self.path='/'+self.path.split('/')[-1];self.directory=str(STAFF)
  elif not (Path(self.directory)/urlsplit(self.path).path.lstrip('/')).is_file():self.path='/index.html'
  super().do_GET()
 def log_message(self,*_):pass

def response(path,method,query,saved,mode):
 if path=='/users/me':return USER
 if path=='/auth/login':return dict(access_token='design-review-fixture',token_type='bearer')
 if path=='/auth/oauth/status':return dict(google=False,apple=False)
 if path=='/users/me/entitlements':return dict(bacity_plus=dict(active=False,expires_at=None,management_channel=None))
 if path=='/users/me/saved-events':return [e for e in EVENTS if e['id'] in saved]
 if path.endswith('/save'):
  event_id=path.split('/')[-2]
  saved.add(event_id) if method=='POST' else saved.discard(event_id)
  return dict(event_id=event_id,saved=event_id in saved)
 if path=='/events':
  items=EVENTS
  if mode=='empty':items=[]
  if 'category' in query:items=[e for e in items if e['category']==query['category'][0]]
  if query.get('free_only')==['true']:items=[e for e in items if e['price']==0]
  return dict(total=len(items),items=items)
 if path=='/events/search':return [e for e in EVENTS if query.get('q',[''])[0].lower() in e['title'].lower()]
 if path=='/recommendations/query':return [dict(event=e,reasons=['Because you enjoy local culture'],saved=e['id'] in saved) for e in (EVENTS if mode!='empty' else [])]
 if path=='/events/map/clusters':return dict(type='FeatureCollection',features=[],total=len(EVENTS),truncated=False)
 if path=='/events/map/districts':return dict(type='FeatureCollection',features=[],source='synthetic-design-fixture',outside_districts=0)
 if path=='/events/map/area':return dict(name='Bratislava',total=len(EVENTS),items=EVENTS,has_more=False,next_cursor=None,refreshed=False)
 if path.startswith('/events/'):
  return next((e for e in EVENTS if e['id']==path.split('/')[2]),EVENTS[0])
 if path.startswith('/community/profiles/') and len(path.split('/'))==4:
  return USER|dict(contributions_count=0,reviews_count=0,followers=0,following=0,reputation_level='Contributor')
 if 'review-summary' in path:return dict(count=0,dimensions={})
 if 'notification-summary' in path:return dict(unread=0,messages=0)
 if 'follow-state' in path:return dict(following=False,follow_id=None)
 return []

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--export',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);parser.add_argument('--phase',required=True);parser.add_argument('--quick',action='store_true');parser.add_argument('--staff-only',action='store_true');parser.add_argument('--staff-dir',type=Path);parser.add_argument('--only');args=parser.parse_args();
 global STAFF
 if args.staff_dir:STAFF=args.staff_dir.resolve()
 args.out.mkdir(parents=True,exist_ok=True)
 server=ThreadingHTTPServer(('127.0.0.1',18742),functools.partial(Handler,directory=str(args.export)));threading.Thread(target=server.serve_forever,daemon=True).start()
 report=dict(phase=args.phase,data='synthetic design fixtures; no live API',screens=[],errors=[],unhandled=[])
 with sync_playwright() as pw:
  browser=pw.chromium.launch(args=['--enable-webgl','--use-angle=swiftshader','--enable-unsafe-swiftshader'])
  for theme in ([] if args.staff_only else ['dark','light']):
   context=browser.new_context(viewport=dict(width=390,height=844),color_scheme=theme,reduced_motion='reduce')
   context.add_init_script("sessionStorage.setItem('bratislava_events_token','design-review-fixture');localStorage.setItem('bacity.appearance.v1', '"+theme+"');")
   saved={EVENTS[1]['id']};mode='normal'
   def bridge(route):
    u=urlsplit(route.request.url);path=u.path
    if u.port!=18741:return route.continue_()
    if mode=='guest' and path=='/users/me':return route.fulfill(status=401,json={'detail':'Synthetic guest'},headers={'Access-Control-Allow-Origin':'*'})
    if mode=='error' and path in ['/events','/recommendations/query']:return route.fulfill(status=503,json={'detail':'Synthetic design review: retry this request.'},headers={'Access-Control-Allow-Origin':'*'})
    route.fulfill(json=response(path,route.request.method,parse_qs(u.query),saved,mode),headers={'Access-Control-Allow-Origin':'*'})
   context.route('**/*',bridge);page=context.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
   routes=[('home','/discover'),('explore','/explore'),('detail','/event/'+EVENTS[0]['id']),('saved','/saved'),('profile','/profile'),('account','/account'),('auth','/auth?mode=register'),('map','/map')]
   if args.only:routes=[item for item in routes if item[0]==args.only]
   if args.quick:routes=routes[:2]
   for name,path in routes:
    mode='guest' if name=='auth' else 'normal'
    page.goto('http://127.0.0.1:18742'+path,wait_until='networkidle');page.wait_for_timeout(2600)
    shot=f'{args.phase}-{name}-{theme}.png';page.screenshot(path=str(args.out/shot))
    geometry=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')
    report['screens'].append(dict(file=shot,route=path,theme=theme,viewport=dict(width=390,height=844),geometry=geometry))
    print(shot,geometry,flush=True)
   if not args.quick:
    for width,height in [(320,780),(768,1024)]:
     page.set_viewport_size(dict(width=width,height=height));page.goto('http://127.0.0.1:18742/explore',wait_until='networkidle');page.wait_for_timeout(2600);shot=f'{args.phase}-explore-{theme}-{width}.png';page.screenshot(path=str(args.out/shot));report['screens'].append(dict(file=shot,route='/explore',theme=theme,viewport=dict(width=width,height=height),geometry=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')))
   if not args.quick:
    page.set_viewport_size(dict(width=390,height=844))
    for state in ['empty','error']:
     mode=state;page.goto('http://127.0.0.1:18742/explore',wait_until='networkidle');page.wait_for_timeout(2600)
     shot=f'{args.phase}-explore-{theme}-{state}.png';page.screenshot(path=str(args.out/shot));report['screens'].append(dict(file=shot,route='/explore',state=state,theme=theme,viewport=dict(width=390,height=844),geometry=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')))
    mode='normal';page.goto('http://127.0.0.1:18742/account',wait_until='networkidle');page.wait_for_timeout(2600)
    draft=page.get_by_role('textbox',name='Display name',exact=True);draft.fill('Preserved design draft');assert draft.input_value()=='Preserved design draft'
    page.get_by_role('button',name='Save preferences',exact=True).count()
    shot=f'{args.phase}-account-{theme}-draft.png';page.screenshot(path=str(args.out/shot));report['screens'].append(dict(file=shot,route='/account',state='draft',theme=theme,viewport=dict(width=390,height=844),geometry=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')))
   context.close()
  if not args.quick:
   context=browser.new_context(viewport=dict(width=1440,height=1000))
   def staff_api(route):
    path=urlsplit(route.request.url).path
    if path=='/api/auth/session':data=dict(id='fixture',name='Design review fixture',role='OWNER',csrf='synthetic')
    elif path=='/api/dashboard':data=dict(emergency_stop=False,collection_enabled=True,publication_enabled=False,pending=3,enabled=12,awaiting_review=2,recent_jobs=[dict(publisher_name='City culture fixture',state='succeeded',finished=1794650400,created=1794650300,metrics=dict(new_observations=2))])
    elif path.startswith('/api/candidates'):data=dict(items=[dict(id='fixture',fields=dict(title='Contemporary jazz at the Old Town studio',start_time='2026-11-21T18:00:00+01:00',venue_name='Old Town studio'),method='user_submission',status='needs_review',missing=[],media=[],source_url='https://example.test/design-fixture',caption='Synthetic design review fixture. An intimate live performance in Bratislava. Please verify the date and venue before publishing.',published_at='2026-11-14T09:00:00Z')],total=1)
    else:data=dict(items=[],total=0)
    route.fulfill(json=data)
   context.route('**/api/**',staff_api);page=context.new_page();page.on('pageerror',lambda e:report['errors'].append(str(e)))
   page.goto('http://127.0.0.1:18742/staff/index.html',wait_until='networkidle')
   for width,height in [(1440,1000),(390,844)]:
    page.set_viewport_size(dict(width=width,height=height))
    for name,label in [('overview','Overview'),('review','Events to review')]:
     page.get_by_role('button',name=label,exact=True).click();page.wait_for_timeout(200)
     shot=f'{args.phase}-staff-{name}-{width}.png';page.screenshot(path=str(args.out/shot),full_page=True)
     report['screens'].append(dict(file=shot,route='/staff/'+name,theme='dark',viewport=dict(width=width,height=height),geometry=page.evaluate('({width:innerWidth,scroll:document.documentElement.scrollWidth})')))
   context.close()
  browser.close()
 server.shutdown();(args.out/f'{args.phase}-capture.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(screens=len(report['screens']),errors=report['errors'])),flush=True)

if __name__=='__main__':main()

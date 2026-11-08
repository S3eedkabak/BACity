"""Complete SQL grid aggregation and query-bound keyset pagination.

The grid bounds the number of features, never the number of represented events.
Area tokens preserve the viewport intersection (including half-open grid edges).
"""
import base64
import hashlib
import hmac
import json
import math
import time
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import String, and_, cast, column, func, or_, select, table
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.models.event import Event, EventStatus

TOKEN_TTL = 86400
AREA_NAME = 'Events near this area'


def pack(value):
    data = base64.urlsafe_b64encode(json.dumps(value, separators=(',', ':'), sort_keys=True).encode()).decode().rstrip('=')
    signature = hmac.new(get_settings().jwt_secret.encode(), data.encode(), hashlib.sha256).hexdigest()
    return data + '.' + signature


def unpack(token):
    try:
        data, signature = token.split('.')
        expected = hmac.new(get_settings().jwt_secret.encode(), data.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        value = json.loads(base64.urlsafe_b64decode(data + '='*(-len(data)%4)))
        if value['expires'] < time.time():
            raise HTTPException(409, 'Area expired; refresh the map')
        return value
    except (ValueError, KeyError, TypeError):
        raise HTTPException(422, 'Invalid area or cursor')


def predicate(bounds, filters, cell=None, dialect="postgresql"):
    # Shared verbatim by clusters, area totals, and every page.
    from app.crud.event_identity import discoverable
    conditions = [discoverable(), Event.latitude.between(max(48., bounds['min_lat']), min(48.35, bounds['max_lat'])),
                  Event.longitude.between(max(16.9, bounds['min_lng']), min(17.35, bounds['max_lng'])),
                  Event.status.in_([EventStatus.fresh, EventStatus.stale])]
    if filters.get('district'):
        from app.crud.districts import expression
        if dialect=='postgresql':
            districts_table=table('map_districts',column('id'),column('geometry'))
            geometry=select(districts_table.c.geometry).where(districts_table.c.id==filters['district']).scalar_subquery()
            point=func.ST_SetSRID(func.ST_MakePoint(Event.longitude,Event.latitude),4326)
            conditions.append(func.ST_Covers(geometry,point))
            conditions.append(or_(func.ST_Contains(geometry,point),expression(dialect)==filters['district']))
        else:
            conditions.append(expression(dialect)==filters['district'])
    if filters.get('near_lat') is not None:
        lat,lng=filters['near_lat'],filters['near_lng']
        if dialect=='postgresql':
            distance=func.ST_DistanceSphere(func.ST_MakePoint(Event.longitude,Event.latitude),func.ST_MakePoint(lng,lat))/1000
        else:
            a=func.pow(func.sin(func.radians(Event.latitude-lat)/2),2)+func.cos(func.radians(lat))*func.cos(func.radians(Event.latitude))*func.pow(func.sin(func.radians(Event.longitude-lng)/2),2)
            distance=6371*2*func.asin(func.sqrt(a))
        conditions.append(distance<=filters.get('radius_km',3))
    if filters.get('category'): conditions.append(Event.category == filters['category'])
    if filters.get('status'): conditions.append(Event.status == filters['status'])
    if filters.get('free_only'): conditions.append(Event.price == 0)
    if filters.get('starts_after') or filters.get('starts_before'):
        from app.crud.event_identity import date_window
        conditions.append(date_window(*(datetime.fromisoformat(filters[key]) if filters.get(key) else None for key in ('starts_after','starts_before'))))
    if filters.get('q'):
        term = '%' + filters['q'].replace('\\','\\\\').replace('%','\\%').replace('_','\\_') + '%'
        conditions.append(or_(Event.title.ilike(term, escape='\\'), Event.description.ilike(term, escape='\\')))
    if cell:
        size, x, y = cell
        conditions.extend([func.floor(Event.longitude / size) == x, func.floor(Event.latitude / size) == y])
    return and_(*conditions)


def revision(count, updated):
    return f'{count}:{updated.isoformat() if updated else "empty"}'


def clusters(db, bounds, zoom, filters):
    from app.crud.districts import prepare
    prepare(db)
    # At most ~33x33 cells even for a continent-sized viewport; no Python event scan.
    width = max(0, min(17.35,bounds['max_lng'])-max(16.9,bounds['min_lng']))
    height = max(0, min(48.35,bounds['max_lat'])-max(48.,bounds['min_lat']))
    size = max(360 / 2**zoom / 4, width/32, height/32, .000001)
    x, y = func.floor(Event.longitude/size), func.floor(Event.latitude/size)
    rows = db.execute(select(x.label('x'), y.label('y'), func.count().label('count'),
        func.avg(Event.latitude).label('lat'), func.avg(Event.longitude).label('lng'),
        func.min(Event.latitude).label('min_lat'),func.max(Event.latitude).label('max_lat'),
        func.min(Event.longitude).label('min_lng'),func.max(Event.longitude).label('max_lng'),
        func.min(cast(Event.id,String)).label('event_id'), func.max(Event.updated_at).label('updated'))
        .where(predicate(bounds,filters,dialect=db.bind.dialect.name)).group_by(x,y).order_by(x,y)).all()
    expires = int(time.time())+TOKEN_TTL
    features = []
    for row in rows:
        cell = [size, int(row.x), int(row.y)]
        area = pack({'bounds':bounds,'filters':filters,'cell':cell,'revision':revision(row.count,row.updated),'expires':expires})
        # Camera bounds describe actual contents, never the mostly empty grid cell.
        extent = [row.min_lng,row.min_lat,row.max_lng,row.max_lat]
        center = [row.lng,row.lat]
        coincident = row.max_lng-row.min_lng < .00045 and row.max_lat-row.min_lat < .0003
        features.append({'type':'Feature','id':f'{size}:{row.x}:{row.y}',
            'geometry':{'type':'Point','coordinates':center},
            'properties':{'count':row.count,'point_count':row.count if row.count>1 else None,
                          'point_count_abbreviated':str(row.count),'id':row.event_id if row.count==1 else None,
                          'area_token':area,'area_name':AREA_NAME,
                          'bounds':extent,'coincident':coincident,'expansion_zoom':min(22,zoom+2)}})
    return {'type':'FeatureCollection','features':features,'count_semantics':'distinct_discoverable_events','total':sum(r.count for r in rows),
            'clustered_events':sum(r.count for r in rows if r.count>1),
            'individual_events':sum(r.count for r in rows if r.count==1),'area_name':AREA_NAME,
            'area_token':pack({'bounds':bounds,'filters':filters,'expires':expires})}


def area_events(db, area_token, cursor, limit, filters=None):
    from app.crud.districts import prepare
    prepare(db)
    area = unpack(area_token)
    active = area['filters'] if filters is None else filters
    if area.get('district'):
        active = {**active,'district':area['district']}
    condition = predicate(area['bounds'],active,area.get('cell'),db.bind.dialect.name)
    # One database snapshot per response, with changes between pages detected.
    # PostgreSQL transaction defaults are READ COMMITTED; use REPEATABLE READ
    # for this read-only route before any SELECT on its own Session.
    total, updated = db.execute(select(func.count(),func.max(Event.updated_at)).where(condition)).one()
    version = revision(total,updated)
    query_key = hashlib.sha256(json.dumps([area['bounds'],area.get('cell'),active],sort_keys=True).encode()).hexdigest()
    stmt = select(Event).where(condition)
    if cursor:
        page = unpack(cursor)
        if page.get('query') != query_key:
            raise HTTPException(422,'Cursor belongs to a different area or filter')
        if page['revision'] != version:
            raise HTTPException(409,'Events changed; refresh this area to continue')
        start = datetime.fromisoformat(page['start'])
        from uuid import UUID
        last_id = UUID(page['id'])
        stmt = stmt.where(or_(Event.start_time>start,and_(Event.start_time==start,Event.id>last_id)))
    items = list(db.scalars(stmt.options(selectinload(Event.venue)).order_by(Event.start_time,Event.id).limit(limit+1)))
    from app.crud.event_identity import annotate_availability
    annotate_availability(db,items,*(datetime.fromisoformat(active[key]) if active.get(key) else None for key in ("starts_after","starts_before")))
    more = len(items)>limit
    items = items[:limit]
    continuation = None
    if more:
        last = items[-1]
        continuation = pack({'query':query_key,'revision':version,'start':last.start_time.isoformat(),
                             'id':str(last.id),'expires':area['expires']})
    return {'name':area.get('name',AREA_NAME),'count_semantics':'distinct_discoverable_events','total':total,'items':items,'has_more':more,'next_cursor':continuation,
            'refreshed':active==area['filters'] and 'revision' in area and area['revision']!=version}


def districts(db, filters):
    from app.crud.districts import collection,expression,prepare,SOURCE_URL
    prepare(db)
    active={k:v for k,v in filters.items() if k!='district'}
    bounds=dict(min_lat=48.,max_lat=48.35,min_lng=16.9,max_lng=17.35)
    if db.bind.dialect.name=='postgresql':
        region=table('map_districts',column('id'),column('geometry'))
        point=func.ST_SetSRID(func.ST_MakePoint(Event.longitude,Event.latitude),4326)
        belongs=and_(func.ST_Covers(region.c.geometry,point),
            or_(func.ST_Contains(region.c.geometry,point),expression('postgresql')==region.c.id))
        rows=db.execute(select(region.c.id,func.count(Event.id),func.max(Event.updated_at))
            .select_from(region.outerjoin(Event.__table__,and_(belongs,predicate(bounds,active))))
            .group_by(region.c.id)).all()
        total=db.scalar(select(func.count()).select_from(Event).where(predicate(bounds,active))) or 0
        outside=total-sum(count for _,count,_ in rows)
    else:
        district=expression('sqlite')
        rows=db.execute(select(district,func.count(),func.max(Event.updated_at))
            .where(predicate(bounds,active,dialect='sqlite')).group_by(district)).all()
        outside=sum(count for key,count,_ in rows if key is None)
    counts={key:(count,updated) for key,count,updated in rows if key}
    features=[]
    for feature in collection()['features']:
        properties=feature['properties'];identifier=properties['id'];count,updated=counts.get(identifier,(0,None))
        selected={**active,'district':identifier}
        token=pack({'bounds':bounds,'filters':selected,'district':identifier,'name':properties['name'],'revision':revision(count,updated),'expires':int(time.time())+TOKEN_TTL})
        features.append({**feature,'properties':{**properties,'count':count,'area_token':token}})
    return {'type':'FeatureCollection','features':features,'source':SOURCE_URL,'boundary_rule':'lowest_official_id','outside_districts':outside}

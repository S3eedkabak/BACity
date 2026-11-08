"""Official city geometry; clusters never imply district membership."""
import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import String, func, literal_column

SOURCE_URL = 'https://geoportal.bratislava.sk/hSite/rest/services/Hosted/Administrat%C3%ADvne_hranice_mestsk%C3%BDch_%C4%8Dast%C3%AD_Bratislavy/FeatureServer/0'


@lru_cache(maxsize=1)
def collection():
    return json.loads((Path(__file__).resolve().parents[1]/'data/bratislava-districts.geojson').read_text())


def _ring_contains(ring,x,y):
    inside=False
    for a,b in zip(ring,ring[1:]):
        ax,ay=a[:2];bx,by=b[:2]
        cross=(x-ax)*(by-ay)-(y-ay)*(bx-ax)
        if abs(cross)<1e-12 and min(ax,bx)-1e-12<=x<=max(ax,bx)+1e-12 and min(ay,by)-1e-12<=y<=max(ay,by)+1e-12:
            return 2  # Covered boundary, matching ST_Covers.
        if (ay>y)!=(by>y) and x<(bx-ax)*(y-ay)/(by-ay)+ax:inside=not inside
    return int(inside)


def membership(lat,lng):
    if lat is None or lng is None:return None
    covered=[]
    for feature in collection()['features']:
        geometry=feature['geometry']
        polygons=[geometry['coordinates']] if geometry['type']=='Polygon' else geometry['coordinates']
        for polygon in polygons:
            exterior=_ring_contains(polygon[0],lng,lat)
            holes=[_ring_contains(ring,lng,lat) for ring in polygon[1:]]
            if exterior and (exterior==2 or 2 in holes or not any(holes)):
                covered.append(feature['properties']['id']);break
    return min(covered) if covered else None


def prepare(db):
    if db.bind.dialect.name=='sqlite':
        db.connection().connection.dbapi_connection.create_function('bacity_district',2,membership,deterministic=True)


def expression(dialect):
    if dialect=='sqlite':
        from app.models.event import Event
        return func.bacity_district(Event.latitude,Event.longitude)
    # Lowest official ID owns a shared boundary; all counts/lists use this rule.
    return literal_column('(SELECT min(d.id) FROM map_districts d WHERE ST_Covers(d.geometry,ST_SetSRID(ST_MakePoint(events.longitude,events.latitude),4326)))',type_=String)

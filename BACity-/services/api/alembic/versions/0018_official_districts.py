"""Verified Bratislava district polygons and published point GiST index."""
import json
from pathlib import Path
from alembic import op
from sqlalchemy import text

revision='0018'
down_revision='0017'
branch_labels=None
depends_on=None


def upgrade():
    op.execute('CREATE TABLE map_districts (id VARCHAR(16) PRIMARY KEY,name TEXT NOT NULL,geometry geometry(MultiPolygon,4326) NOT NULL)')
    source=Path(__file__).resolve().parents[2]/'app/data/bratislava-districts.geojson'
    for feature in json.loads(source.read_text())['features']:
        op.get_bind().execute(text('INSERT INTO map_districts VALUES(:id,:name,ST_Multi(ST_MakeValid(ST_SetSRID(ST_GeomFromGeoJSON(:geometry),4326))))'),
            {'id':feature['properties']['id'],'name':feature['properties']['name'],'geometry':json.dumps(feature['geometry'])})
    op.execute('CREATE INDEX ix_map_districts_geometry ON map_districts USING gist (geometry)')
    op.execute("CREATE INDEX ix_events_map_point ON events USING gist (ST_SetSRID(ST_MakePoint(longitude,latitude),4326)) WHERE latitude IS NOT NULL AND longitude IS NOT NULL AND status IN ('fresh','stale')")


def downgrade():
    op.drop_index('ix_events_map_point',table_name='events')
    op.drop_table('map_districts')

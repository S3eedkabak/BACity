from datetime import datetime
from unittest.mock import Mock

from app.config import get_settings
from app.core.utilities import OFFICIAL_TOILET_SOURCE
from app.models.community import CityUtility
from app.utility_import import normalize_feature, sync_bratislava_toilets


FEATURE = {
    'type': 'Feature',
    'geometry': {'type': 'Point', 'coordinates': [17.10902, 48.14468]},
    'properties': {
        'objectid': 1,
        'miesto_nazov': '  Bezbarierová verejná toaleta Uršulínska  ',
        'otvaracia_doba': 'PO - NE, 9:00 - 21:00',
        'cena': 'platené: 0,70 EUR',
    },
}


class Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {'features': [FEATURE]}


class Client:
    def get(self, *args, **kwargs):
        return Response()


def test_city_toilet_normalization_and_idempotent_sync(db_session):
    normalized = normalize_feature(FEATURE)
    assert normalized['name'] == 'Bezbarierová verejná toaleta Uršulínska'
    assert normalized['wheelchair_accessible'] is True
    assert normalized['free'] is False and normalized['fee'] == .7

    assert sync_bratislava_toilets(db_session, Client()) == {
        'received': 1, 'created': 1, 'updated': 0, 'skipped': 0, 'missing': 0,
    }
    assert sync_bratislava_toilets(db_session, Client()) == {
        'received': 1, 'created': 0, 'updated': 1, 'skipped': 0, 'missing': 0,
    }
    item = db_session.query(CityUtility).one()
    assert item.kind == 'toilet' and item.latitude == 48.14468


def test_maintenance_handles_multiple_imported_toilets(db_session, monkeypatch):
    from app import worker
    from tests.conftest import TestingSessionLocal

    for object_id in (1, 2):
        db_session.add(CityUtility(
            kind='toilet', name=f'Official WC {object_id}', latitude=48.14,
            longitude=17.11, source_url=f'{OFFICIAL_TOILET_SOURCE}?objectid={object_id}',
            updated_at=datetime.utcnow(),
        ))
    db_session.commit()

    sync = Mock()
    monkeypatch.setattr(worker, 'SessionLocal', TestingSessionLocal)
    monkeypatch.setattr(worker, 'sync_bratislava_toilets', sync)
    monkeypatch.setattr(worker, '_last_utility_sync_attempt', None)
    monkeypatch.setattr(get_settings(), 'utility_sync_enabled', True)
    worker.tick()
    sync.assert_not_called()

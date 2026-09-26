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
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class Client:
    def get(self, *args, **kwargs):
        if kwargs['params'].get('returnCountOnly'):
            return Response({'count': 1})
        return Response({'features': [FEATURE]})


def test_city_toilet_normalization_and_idempotent_sync(db_session):
    normalized = normalize_feature(FEATURE)
    assert normalized['name'] == 'Bezbarierová verejná toaleta Uršulínska'
    assert normalized['wheelchair_accessible'] is True
    assert normalized['free'] is False and normalized['fee'] == .7

    assert sync_bratislava_toilets(db_session, Client()) == {
        'upstream_total': 1, 'fetched': 1, 'received': 1, 'accepted': 1,
        'created': 1, 'updated': 0, 'skipped': 0, 'skip_reasons': {}, 'missing': 0,
    }
    assert sync_bratislava_toilets(db_session, Client()) == {
        'upstream_total': 1, 'fetched': 1, 'received': 1, 'accepted': 1,
        'created': 0, 'updated': 1, 'skipped': 0, 'skip_reasons': {}, 'missing': 0,
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


def _feature(object_id):
    return {
        **FEATURE,
        'id': object_id,
        'properties': {**FEATURE['properties'], 'objectid': object_id},
    }


def test_sync_fetches_all_pages_when_count_exceeds_first_page(db_session):
    class PagedClient:
        offsets = []

        def get(self, *args, **kwargs):
            params = kwargs['params']
            if params.get('returnCountOnly'):
                return Response({'count': 3})
            self.offsets.append(params['resultOffset'])
            assert params['resultRecordCount'] == 1000
            assert params['orderByFields'] == 'objectid ASC'
            pages = {0: [_feature(1), _feature(2)], 2: [_feature(3)]}
            return Response({'features': pages[params['resultOffset']]})

    client = PagedClient()
    result = sync_bratislava_toilets(db_session, client)
    assert client.offsets == [0, 2]
    assert result['upstream_total'] == result['fetched'] == result['received'] == 3
    assert result['accepted'] == result['created'] == 3


def test_sync_honors_exceeded_transfer_limit_and_refreshes_changed_count(db_session):
    class LimitedClient:
        count_calls = 0
        offsets = []

        def get(self, *args, **kwargs):
            params = kwargs['params']
            if params.get('returnCountOnly'):
                self.count_calls += 1
                return Response({'count': 2 if self.count_calls == 1 else 3})
            self.offsets.append(params['resultOffset'])
            if params['resultOffset'] == 0:
                return Response({
                    'features': [_feature(1), _feature(2)],
                    'properties': {'exceededTransferLimit': True},
                })
            return Response({'features': [_feature(3)]})

    client = LimitedClient()
    result = sync_bratislava_toilets(db_session, client)
    assert client.offsets == [0, 2]
    assert client.count_calls == 2
    assert result['upstream_total'] == result['fetched'] == result['received'] == result['accepted'] == 3


def test_sync_reports_skip_reasons(db_session):
    invalid = {
        'type': 'Feature', 'id': 2, 'geometry': None,
        'properties': {'objectid': 2, 'miesto_nazov': 'Planned WC'},
    }

    class SkipClient:
        def get(self, *args, **kwargs):
            if kwargs['params'].get('returnCountOnly'):
                return Response({'count': 2})
            return Response({'features': [FEATURE, invalid]})

    result = sync_bratislava_toilets(db_session, SkipClient())
    reason = 'Public-toilet feature is missing its ID or coordinates'
    assert result['upstream_total'] == result['fetched'] == result['received'] == 2
    assert result['accepted'] == 1 and result['skipped'] == 1
    assert result['skip_reasons'] == {reason: 1}

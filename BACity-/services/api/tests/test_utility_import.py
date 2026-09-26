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

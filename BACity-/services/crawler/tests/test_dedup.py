import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.items import NormalizedEvent
from crawler.processing.dedup import score_duplicate, find_duplicate_groups


def _event(title, start_time, venue_name="Fuga"):
    return NormalizedEvent(
        title=title, start_time=start_time, end_time=None, timezone="Europe/Bratislava",
        description=None, venue_name=venue_name, address=None, price=None, currency=None,
        image_url=None, category="Nightlife", tags=[], language="en",
        source_url="https://example.com", extraction_confidence=0.9,
    )


def test_same_event_different_wording_is_duplicate():
    a = _event("Techno Friday", "2026-08-29T22:00:00+02:00")
    b = _event("Friday Techno Night", "2026-08-29T22:15:00+02:00")
    result = score_duplicate(a, b)
    assert result.is_duplicate


def test_different_events_same_title_different_day_not_duplicate():
    a = _event("Weekly Jam Session", "2026-08-29T20:00:00+02:00")
    b = _event("Weekly Jam Session", "2026-09-05T20:00:00+02:00")
    result = score_duplicate(a, b)
    assert not result.is_duplicate


def test_completely_different_events_not_duplicate():
    a = _event("Techno Night", "2026-08-29T22:00:00+02:00")
    b = _event("Jazz Under the Stars", "2026-08-30T19:00:00+02:00", venue_name="Stará Tržnica")
    result = score_duplicate(a, b)
    assert not result.is_duplicate


def test_find_duplicate_groups_merges_correctly():
    events = [
        _event("Techno Friday", "2026-08-29T22:00:00+02:00"),
        _event("Friday Techno Night", "2026-08-29T22:10:00+02:00"),
        _event("Jazz Evening", "2026-08-30T19:00:00+02:00", venue_name="Stará Tržnica"),
    ]
    groups = find_duplicate_groups(events)
    assert len(groups) == 2
    sizes = sorted(len(g) for g in groups)
    assert sizes == [1, 2]

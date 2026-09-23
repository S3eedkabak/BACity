from crawler.extraction.goout_extractor import extract_goout_events


def test_extract_goout_feeder_shape():
    data = {
        "events": [
            {
                "title": "Example Concert",
                "startDate": "2026-10-10T20:00:00+02:00",
                "endDate": "2026-10-10T22:00:00+02:00",
                "location": {
                    "name": "A4",
                    "address": "Karpatská 2, Bratislava",
                },
            }
        ]
    }
    events = extract_goout_events(data, "https://goout.net/services/feeder/v1/events.json")
    assert len(events) == 1
    assert events[0].title == "Example Concert"
    assert events[0].venue_name == "A4"
    assert events[0].address == "Karpatská 2, Bratislava"

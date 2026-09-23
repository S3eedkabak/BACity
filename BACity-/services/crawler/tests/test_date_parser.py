from crawler.extraction.date_parser import parse_event_datetime


def test_parse_slovak_named_month_range():
    parsed = parse_event_datetime("2. – 4. október", reference_year=2026)
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 10
    assert parsed.day == 2


def test_parse_slovak_dot_datetime():
    parsed = parse_event_datetime("24. 9. 2026, 19:00")
    assert parsed is not None
    assert parsed.year == 2026
    assert parsed.month == 9
    assert parsed.day == 24
    assert parsed.hour == 19

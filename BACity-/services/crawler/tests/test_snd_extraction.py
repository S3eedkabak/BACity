from crawler.extraction.snd_extractor import extract_snd_events


def test_extract_snd_program_entry():
    html_text = """
    Názov: Celé zle
    Umelecký súbor: činohra,
    Miesto konania: nová budova SND - Štúdio
    Stav: Vypredané
    Dátum predstavenia Štvrtok 24.09.2026 19.00 h 22.00 h
    Súčasná britská komédia
    """
    events = extract_snd_events(html_text, "https://snd.sk/program")
    assert len(events) == 1
    event = events[0]
    assert event.title == "Celé zle"
    assert event.start_raw == "24.09.2026 19:00"
    assert event.end_raw == "24.09.2026 22:00"
    assert event.venue_name.endswith("Štúdio")
    assert event.address == "Pribinova 17, 811 09 Bratislava"

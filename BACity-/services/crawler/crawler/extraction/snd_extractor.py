"""Parser for the Slovak National Theatre's text-based monthly programme."""
import re

from crawler.items import RawEvent

_PERFORMANCE_RE = re.compile(
    r"Názov:\s*(?P<title>.+?)\s+"
    r"Umelecký súbor:.*?"
    r"Miesto konania:\s*(?P<venue>.+?)\s+"
    r"Stav:.*?"
    r"Dátum predstavenia\s+"
    r"(?P<date>\d{1,2}\.\d{1,2}\.\d{4})\s+"
    r"(?P<start>\d{1,2}[.:]\d{2})\s+h\s+"
    r"(?P<end>\d{1,2}[.:]\d{2})\s+h"
)


def extract_snd_events(text: str, source_url: str) -> list[RawEvent]:
    cleaned = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    results: list[RawEvent] = []

    for match in _PERFORMANCE_RE.finditer(cleaned):
        title = match.group("title").strip(" ,")
        venue = match.group("venue").strip(" ,")
        date = match.group("date")
        start = match.group("start").replace(".", ":")
        end = match.group("end").replace(".", ":")

        results.append(
            RawEvent(
                title=title,
                start_raw=f"{date} {start}",
                end_raw=f"{date} {end}",
                venue_name=venue,
                address="Pribinova 17, 811 09 Bratislava",
                source_url=source_url,
                extraction_method="snd_program",
                extraction_confidence=0.95,
            )
        )

    return results

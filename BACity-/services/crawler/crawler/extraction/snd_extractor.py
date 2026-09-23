"""Parser for the Slovak National Theatre's text-based monthly programme."""
import re

from crawler.items import RawEvent

_PERFORMANCE_RE = re.compile(
    r"Názov:\s*(?P<title>.+?)\s+"
    r"Umelecký súbor:.*?"
    r"Miesto konania:\s*(?P<venue>.+?)\s+"
    r"Stav:.*?"
    r"Dátum predstavenia\s+"
    r"(?:\S+\s+)?"
    r"(?P<date>\d{1,2}\.\d{1,2}\.\d{4})\s+"
    r"(?P<start>\d{1,2}[.:]\d{2})\s+h\s+"
    r"(?P<end>\d{1,2}[.:]\d{2})\s+h",
    re.IGNORECASE,
)


def extract_snd_events(text: str, source_url: str) -> list[RawEvent]:
    cleaned = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    results: list[RawEvent] = []

    for match in _PERFORMANCE_RE.finditer(cleaned):
        results.append(
            RawEvent(
                title=match.group("title").strip(" ,"),
                start_raw=f"{match.group('date')} {match.group('start').replace('.', ':')}",
                end_raw=f"{match.group('date')} {match.group('end').replace('.', ':')}",
                venue_name=match.group("venue").strip(" ,"),
                address="Pribinova 17, 811 09 Bratislava",
                source_url=source_url,
                extraction_method="snd_program",
                extraction_confidence=0.95,
            )
        )

    return results

"""Parser for the Slovak National Theatre's text-based programme."""
import re

from crawler.items import RawEvent

_PERFORMANCE_RE = re.compile(
    r"Názov:\s*(?P<title>.+?)\s+"
    r"Umelecký súbor:.*?"
    r"Miesto konania:\s*(?P<venue>.+?)\s+"
    r"Stav:.*?"
    r"Dátum predstavenia\s*:?\s*"
    r"(?:\S+\s+)?"
    r"(?P<date>\d{1,2}\.\d{1,2}\.(?:\d{4})?)\s*"
    r"(?:o\s*)?"
    r"(?P<start>\d{1,2}[.:]\d{2})\s*h"
    r"(?:\s+(?P<end>\d{1,2}[.:]\d{2})\s*h)?",
    re.IGNORECASE,
)


def _with_year(date_text: str, time_text: str, reference_year: int) -> str:
    if not re.search(r"\d{4}$", date_text):
        date_text = f"{date_text}{reference_year}"
    return f"{date_text} {time_text.replace('.', ':')}"


def extract_snd_events(
    text: str, source_url: str, reference_year: int = 2026
) -> list[RawEvent]:
    cleaned = re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()
    results: list[RawEvent] = []

    for match in _PERFORMANCE_RE.finditer(cleaned):
        start_raw = _with_year(match.group("date"), match.group("start"), reference_year)
        end_raw = (
            _with_year(match.group("date"), match.group("end"), reference_year)
            if match.group("end")
            else None
        )
        results.append(
            RawEvent(
                title=match.group("title").strip(" ,"),
                start_raw=start_raw,
                end_raw=end_raw,
                venue_name=match.group("venue").strip(" ,"),
                address="Pribinova 17, 811 09 Bratislava",
                source_url=source_url,
                extraction_method="snd_program",
                extraction_confidence=0.95,
            )
        )

    return results

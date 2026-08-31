"""
Extraction priority levels 4-7 (spec section 18): used only when a page has
no JSON-LD/schema.org Event data. Tries OpenGraph metadata first (cheap,
common), then falls back to heuristic HTML scanning for elements whose
class/id names suggest they hold event info. Confidence is intentionally
lower than the JSON-LD path so the pipeline's confidence-based LLM
fallback (section 19) can kick in on the pages this still can't handle.
"""
import re
from typing import Optional

from bs4 import BeautifulSoup

from crawler.items import RawEvent

DATE_HINT_RE = re.compile(
    r"\d{1,2}[./]\d{1,2}[./]\d{2,4}(?:\s+\d{1,2}:\d{2})?|"
    r"\b\d{1,2}\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
    r"(?:\s+\d{4})?(?:\s*,?\s*\d{1,2}:\d{2})?",
    re.IGNORECASE,
)


def _meta(soup: BeautifulSoup, *names: str) -> Optional[str]:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def extract_opengraph_event(html: str, source_url: str) -> Optional[RawEvent]:
    """Level 4: OpenGraph metadata. Common on venue sites even without
    full schema.org markup, but says nothing reliable about *when* the
    event is — so this alone yields a low-confidence, date-less RawEvent
    that the caller should only keep if a date is found elsewhere on page."""
    soup = BeautifulSoup(html, "html.parser")
    title = _meta(soup, "og:title")
    if not title:
        return None

    description = _meta(soup, "og:description")
    image = _meta(soup, "og:image")

    date_text = None
    body_text = soup.get_text(" ", strip=True)
    match = DATE_HINT_RE.search(body_text)
    if match:
        # Use the matched date/time span itself (not a surrounding text
        # window) — the date parser handles that cleanly, whereas ragged
        # prose fragments around it ("...rsky trh Kedy: 31/08/2026 08:00 - S")
        # can trip up dateutil's fuzzy matching.
        date_text = match.group().strip()

    return RawEvent(
        title=title,
        start_raw=date_text or "",
        description=description,
        image_url=image,
        source_url=source_url,
        extraction_method="opengraph",
        extraction_confidence=0.4 if date_text else 0.15,
    )


EVENT_CLASS_HINTS = ["event", "akcia", "podujatie", "program"]
DATE_CLASS_HINTS = ["date", "datum", "dátum", "time", "cas", "čas"]
VENUE_CLASS_HINTS = ["venue", "location", "miesto"]
PRICE_CLASS_HINTS = ["price", "cena", "vstupne", "vstupné"]


def _find_by_class_hint(soup: BeautifulSoup, hints: list[str]):
    for tag in soup.find_all(True):
        classes = " ".join(tag.get("class", [])) + " " + (tag.get("id") or "")
        classes = classes.lower()
        if any(hint in classes for hint in hints):
            return tag
    return None


def extract_generic_html(html: str, source_url: str) -> list[RawEvent]:
    """Level 7: last-resort heuristic scan for pages with no structured
    data at all. Deliberately conservative — one best-guess event per page
    rather than trying to enumerate a listing page's structure generically,
    since false positives are worse than a missed low-value page here
    (spec section 27: false merges/extractions are more damaging than gaps)."""
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find(["h1", "h2"])
    title = title_tag.get_text(strip=True) if title_tag else None
    if not title:
        return []

    date_tag = _find_by_class_hint(soup, DATE_CLASS_HINTS)
    venue_tag = _find_by_class_hint(soup, VENUE_CLASS_HINTS)
    price_tag = _find_by_class_hint(soup, PRICE_CLASS_HINTS)

    date_text = date_tag.get_text(" ", strip=True) if date_tag else ""
    if not date_text:
        return []  # no usable date at all -> not worth returning a guess

    return [RawEvent(
        title=title,
        start_raw=date_text,
        venue_name=venue_tag.get_text(strip=True) if venue_tag else None,
        price_raw=price_tag.get_text(strip=True) if price_tag else None,
        source_url=source_url,
        extraction_method="generic_html",
        extraction_confidence=0.35,
    )]


def extract_best_effort(html: str, source_url: str) -> list[RawEvent]:
    """Runs the fallback ladder (levels 4 then 7) and returns whatever it finds.
    Called by the pipeline only after jsonld_extractor found nothing —
    see crawler/processing/validate.py for how these confidence scores
    are used downstream."""
    events: list[RawEvent] = []
    og_event = extract_opengraph_event(html, source_url)
    if og_event and og_event.start_raw:
        events.append(og_event)
    if not events:
        events.extend(extract_generic_html(html, source_url))
    return events

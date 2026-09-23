"""Fallback extraction for pages without usable JSON-LD."""
import re
from typing import Optional

from bs4 import BeautifulSoup

from crawler.items import RawEvent

DATE_HINT_RE = re.compile(
    r"(?:"
    r"d{1,2}[./]s*d{1,2}[./]s*(?:d{4})?(?:s+d{1,2}[:.]d{2})?"
    r"|"
    r"d{1,2}.s*(?:–|-)s*d{1,2}.s*[A-Za-zÀ-ž]+(?:s+d{4})?"
    r"|"
    r"d{1,2}.s*[A-Za-zÀ-ž]+(?:s+d{4})?(?:[,s]+d{1,2}[:.]d{2})?"
    r"|"
    r"d{1,2}/d{1,2}(?:/d{2,4})?(?:s+d{1,2}[:.]d{2})?"
    r")",
    re.IGNORECASE,
)

EVENT_CLASS_HINTS = ("event", "akcia", "podujatie", "program", "event-card")
DATE_CLASS_HINTS = ("date", "datum", "dátum", "time", "cas", "čas", "term")
VENUE_CLASS_HINTS = ("venue", "location", "miesto", "place", "lokal")
ADDRESS_CLASS_HINTS = ("address", "adresa")
PRICE_CLASS_HINTS = ("price", "cena", "vstupne", "vstupné")


def _meta(soup: BeautifulSoup, *names: str) -> Optional[str]:
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find(
            "meta", attrs={"name": name}
        )
        if tag and tag.get("content"):
            return tag["content"].strip()
    return None


def _find_by_class_hint(soup: BeautifulSoup, hints: tuple[str, ...]):
    for tag in soup.find_all(True):
        haystack = " ".join(tag.get("class", [])) + " " + (tag.get("id") or "")
        if any(hint in haystack.lower() for hint in hints):
            return tag
    return None


def _first_title(soup: BeautifulSoup) -> Optional[str]:
    for selector in ("h1", "main h1", "[itemprop='name']", "meta[property='og:title']"):
        tag = soup.select_one(selector)
        if tag:
            value = tag.get("content") if tag.name == "meta" else tag.get_text(" ", strip=True)
            if value:
                return value.strip()
    return None


def extract_opengraph_event(html: str, source_url: str) -> Optional[RawEvent]:
    soup = BeautifulSoup(html, "html.parser")
    title = _meta(soup, "og:title")
    if not title:
        return None

    body_text = soup.get_text(" ", strip=True)
    match = DATE_HINT_RE.search(body_text)
    return RawEvent(
        title=title,
        start_raw=match.group(0).strip() if match else "",
        description=_meta(soup, "og:description"),
        image_url=_meta(soup, "og:image"),
        source_url=source_url,
        extraction_method="opengraph",
        extraction_confidence=0.45 if match else 0.15,
    )


def extract_generic_html(html: str, source_url: str) -> list[RawEvent]:
    soup = BeautifulSoup(html, "html.parser")
    title = _first_title(soup)
    if not title:
        return []

    date_tag = _find_by_class_hint(soup, DATE_CLASS_HINTS)
    venue_tag = _find_by_class_hint(soup, VENUE_CLASS_HINTS)
    address_tag = _find_by_class_hint(soup, ADDRESS_CLASS_HINTS)
    price_tag = _find_by_class_hint(soup, PRICE_CLASS_HINTS)

    body_text = soup.get_text(" ", strip=True)
    date_text = date_tag.get_text(" ", strip=True) if date_tag else ""
    if not date_text:
        match = DATE_HINT_RE.search(body_text)
        date_text = match.group(0).strip() if match else ""

    if not date_text:
        return []

    venue_name = venue_tag.get_text(" ", strip=True) if venue_tag else None
    address = address_tag.get_text(" ", strip=True) if address_tag else None

    # Stará Tržnica and similar venue pages expose the venue/address in a
    # footer rather than an event-card element.
    if "staratrznica.sk" in source_url:
        venue_name = venue_name or "Stará tržnica"
        address = address or "Námestie SNP 25, 811 01 Bratislava"

    return [
        RawEvent(
            title=title,
            start_raw=date_text,
            description=_meta(soup, "og:description"),
            venue_name=venue_name,
            address=address,
            price_raw=price_tag.get_text(" ", strip=True) if price_tag else None,
            image_url=_meta(soup, "og:image"),
            source_url=source_url,
            extraction_method="generic_html",
            extraction_confidence=0.6 if venue_name else 0.45,
        )
    ]


def extract_best_effort(html: str, source_url: str) -> list[RawEvent]:
    og_event = extract_opengraph_event(html, source_url)
    if og_event and og_event.start_raw:
        return [og_event]
    return extract_generic_html(html, source_url)

"""Fallback extraction for pages without usable JSON-LD."""
import re
from urllib.parse import urljoin
from typing import Optional

from bs4 import BeautifulSoup

from crawler.items import RawEvent
from crawler.extraction.date_parser import _MONTH_NAME_RE, parse_event_datetime

MONTH_HINT = rf"(?:{_MONTH_NAME_RE}|january|february|march|april|june|july|august|september|october|november|december)\b"

DATE_HINT_RE = re.compile(
    r"(?:"
    r"\d{1,2}[./]\s*\d{1,2}[./]\s*(?:\d{4})?(?:[,\s]+\d{1,2}[:.]\d{2})?"
    r"|"
    rf"\d{{1,2}}\.\s*(?:–|-)\s*\d{{1,2}}\.\s*{MONTH_HINT}(?:\s+\d{{4}})?"
    r"|"
    rf"\d{{1,2}}\.\s*{MONTH_HINT}(?:\s+\d{{4}})?(?:[,\s]+\d{{1,2}}[:.]\d{{2}})?"
    r"|"
    r"\d{1,2}/\d{1,2}(?:/\d{2,4})?(?:\s+\d{1,2}[:.]\d{2})?"
    r")",
    re.IGNORECASE,
)

DATE_CLASS_HINTS = ("date", "datum", "dátum", "time", "cas", "čas", "term")
VENUE_CLASS_HINTS = ("venue", "location", "miesto", "place", "lokal")
ADDRESS_CLASS_HINTS = ("address", "adresa")
PRICE_CLASS_HINTS = ("price", "cena", "vstupne", "vstupné")


def _event_date(soup):
    # Prefer explicit event start data over incidental dates in titles/navigation.
    for tag in soup.select('[itemprop="startDate"], time[datetime], meta[property="event:start_time"]'):
        value = tag.get('datetime') or tag.get('content') or tag.get_text(' ', strip=True)
        if parse_event_datetime(value):
            return value
    date_tag = _find_by_class_hint(soup, DATE_CLASS_HINTS)
    for text in ([date_tag.get_text(' ', strip=True)] if date_tag else []) + [soup.get_text(' ', strip=True)]:
        for match in DATE_HINT_RE.finditer(text):
            if parse_event_datetime(match.group(0)):
                return match.group(0).strip()
    return None


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

    if title.strip().lower() in {"program", "events", "event", "what's on", "whats on"}:
        return None

    date_text = _event_date(soup)
    if not date_text:
        return None

    return RawEvent(
        title=title,
        start_raw=date_text,
        description=_meta(soup, "og:description"),
        image_url=_meta(soup, "og:image"),
        source_url=source_url,
        extraction_method="opengraph",
        extraction_confidence=0.45,
    )


def extract_generic_html(html: str, source_url: str) -> list[RawEvent]:
    soup = BeautifulSoup(html, "html.parser")
    title = _first_title(soup)
    if not title:
        return []
    if title.strip().lower() in {"program", "events", "event", "what's on", "whats on"}:
        return []

    venue_tag = _find_by_class_hint(soup, VENUE_CLASS_HINTS)
    address_tag = _find_by_class_hint(soup, ADDRESS_CLASS_HINTS)
    price_tag = _find_by_class_hint(soup, PRICE_CLASS_HINTS)

    date_text = _event_date(soup)

    if not date_text:
        return []

    venue_name = venue_tag.get_text(" ", strip=True) if venue_tag else None
    address = address_tag.get_text(" ", strip=True) if address_tag else None

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
    structured = extract_generic_html(html, source_url)
    if structured:
        return structured
    og_event = extract_opengraph_event(html, source_url)
    if og_event:
        return [og_event]
    return []


def extract_event_cards(html: str, source_url: str) -> list[RawEvent]:
    """Extract multiple event cards from listing pages using repeated date-bearing nodes."""
    soup = BeautifulSoup(html, "html.parser")
    events: list[RawEvent] = []
    seen: set[tuple[str, str]] = set()

    for node in soup.find_all(["article", "li", "div"]):
        text = node.get_text(" ", strip=True)
        if len(text) > 2500:
            continue
        date_text = _event_date(node)
        if not date_text:
            continue

        title_tag = node.find(["h1", "h2", "h3", "h4", "a"])
        detail_link = title_tag if title_tag and title_tag.name == 'a' else (title_tag.find('a', href=True) if title_tag else None)
        detail_link = detail_link or (title_tag.find_parent('a', href=True) if title_tag else None) or node.find('a', href=True)
        title = title_tag.get_text(" ", strip=True) if title_tag else ""
        if not title or title.lower() in {"program", "events", "event", "more", "viac"}:
            continue

        key = (title.lower(), date_text)
        if key in seen:
            continue
        seen.add(key)

        venue_tag = _find_by_class_hint(node, VENUE_CLASS_HINTS)
        address_tag = _find_by_class_hint(node, ADDRESS_CLASS_HINTS)
        price_tag = _find_by_class_hint(node, PRICE_CLASS_HINTS)

        venue_name = venue_tag.get_text(" ", strip=True) if venue_tag else None
        address = address_tag.get_text(" ", strip=True) if address_tag else None

        if not venue_name and 'staratrznica.sk' in source_url:
            venue_name = 'Stará tržnica'
            address = 'Námestie SNP 25, 811 01 Bratislava'
        events.append(
            RawEvent(
                title=title,
                start_raw=date_text,
                venue_name=venue_name,
                address=address,
                price_raw=price_tag.get_text(" ", strip=True) if price_tag else None,
                image_url=(
                    node.find("img").get("src")
                    if node.find("img") and node.find("img").get("src")
                    else None
                ),
                source_url=urljoin(source_url, detail_link.get('href', '')) if detail_link else source_url,
                original_source_url=source_url,
                extraction_method="event_card",
                extraction_confidence=0.55 if venue_name else 0.45,
            )
        )

    return events

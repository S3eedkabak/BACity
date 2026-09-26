"""Deterministic adapters for trusted community sources."""
import re
from datetime import datetime
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from crawler.items import RawEvent


def extract_cvernovka_events(html: str, source_url: str) -> list[RawEvent]:
    soup = BeautifulSoup(html, "html.parser")
    events = []
    for card in soup.select("article.hk_event[data-start]"):
        title_tag = card.select_one(".entry-title")
        link = card.select_one("a[href]")
        raw_day = card.get("data-start", "")
        if not title_tag or not link or not re.fullmatch(r"\d{8}", raw_day):
            continue
        time_parts = card.select(".FilterItem__date-container > div")
        clock = time_parts[-1].get_text(" ", strip=True) if time_parts else "00:00"
        if not re.fullmatch(r"\d{1,2}:\d{2}", clock):
            clock = "00:00"
        start_raw = f"{raw_day[:4]}-{raw_day[4:6]}-{raw_day[6:]} {clock}"
        image = card.select_one("img[src]")
        tags = [node.get_text(" ", strip=True).lstrip("#") for node in card.select(".tag")]
        events.append(RawEvent(
            title=title_tag.get_text(" ", strip=True), start_raw=start_raw,
            description=(card.select_one(".entry-content").get_text(" ", strip=True)
                         if card.select_one(".entry-content") else None),
            venue_name="Nová Cvernovka", address="Račianska 78, 831 02 Bratislava",
            image_url=urljoin(source_url, image.get("src")) if image else None,
            source_url=urljoin(source_url, link.get("href")), original_source_url=source_url,
            tags=tags, extraction_method="cvernovka_cards", extraction_confidence=0.90,
        ))
    return events


def extract_karlova_ves_events(data: object, source_url: str) -> list[RawEvent]:
    rows = data.get("data", data) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    events = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("title") or not row.get("start_date"):
            continue
        description = BeautifulSoup(row.get("description") or "", "html.parser").get_text(" ", strip=True)
        poster = row.get("poster_image")
        try:
            latitude = float(row["lat"]) if row.get("lat") is not None else None
            longitude = float(row["lng"]) if row.get("lng") is not None else None
        except (TypeError, ValueError):
            latitude = longitude = None
        events.append(RawEvent(
            title=str(row["title"]).strip(), description=description or None,
            start_raw=row["start_date"], end_raw=row.get("end_date"),
            venue_name=row.get("location") or "Karloveské centrum kultúry",
            address="Molecova 2, 841 04 Bratislava" if not row.get("location") else None,
            latitude=latitude, longitude=longitude,
            price_raw=str(row.get("seat_price")) if row.get("seat_price") is not None else ("0" if row.get("is_paid") is False else None),
            image_url=urljoin(source_url, poster) if poster else None,
            source_url=urljoin("https://kultura.karlovaves.sk", f"/podujatie/{row.get('slug', row.get('id'))}"),
            original_source_url=source_url, extraction_method="karlova_ves_api", extraction_confidence=0.96,
        ))
    return events

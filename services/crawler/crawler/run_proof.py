#!/usr/bin/env python3
"""
This is the milestone spec section 63 calls "the first technical proof" —
runnable without Docker, Postgres, OpenSearch, or live network access.
It feeds a handful of realistic fixture pages (JSON-LD, Slovak-language
generic HTML, OpenGraph-only, and deliberately bad/stale pages) through
the exact same extraction -> normalization -> validation -> deduplication
pipeline a real crawl would use, and reports the same shape of output the
spec's worked example describes.

Run it with:
    python -m crawler.run_proof
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from crawler.extraction.jsonld_extractor import extract_jsonld_events
from crawler.extraction.generic_extractor import extract_best_effort
from crawler.processing.normalize import normalize_event
from crawler.processing.validate import validate_event
from crawler.processing.dedup import find_duplicate_groups

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


def extract_page(html: str, url: str):
    events = extract_jsonld_events(html, url)
    if not events:
        events = extract_best_effort(html, url)
    return events


def main():
    fixture_files = sorted(FIXTURES_DIR.glob("*.html"))
    all_raw = []

    print(f"Crawling {len(fixture_files)} fixture pages "
          f"(stand-ins for real Bratislava source pages)...\n")

    for path in fixture_files:
        html = path.read_text(encoding="utf-8")
        fake_url = f"https://example-source.sk/{path.stem}"
        raw_events = extract_page(html, fake_url)
        print(f"  {path.name:35s} -> {len(raw_events)} raw event(s) "
              f"[{raw_events[0].extraction_method if raw_events else 'none'}]")
        all_raw.extend(raw_events)

    print(f"\nExtracted {len(all_raw)} raw events total.\n")

    normalized = []
    dropped_normalize = 0
    for raw in all_raw:
        n = normalize_event(raw)
        if n is None:
            dropped_normalize += 1
        else:
            normalized.append(n)

    accepted = []
    rejected = []
    for n in normalized:
        result = validate_event(n)
        if result.accepted:
            accepted.append(n)
        else:
            rejected.append((n, result.reason))

    groups = find_duplicate_groups(accepted)
    deduped = [accepted[g[0]] for g in groups]
    duplicate_count = len(accepted) - len(deduped)

    print("=" * 60)
    print(f"Found {len(all_raw)} events.")
    print()
    print(f"{len(all_raw)} extracted")
    print(f"{dropped_normalize} unparseable (dropped at normalization)")
    print(f"{len(accepted)} valid")
    print(f"{len(rejected)} rejected")
    print(f"{duplicate_count} duplicate(s) merged -> {len(deduped)} unique events")
    print("0 crashes")
    print("=" * 60)

    if rejected:
        print("\nRejected events:")
        for event, reason in rejected:
            print(f"  - {event.title!r}: {reason}")

    print("\nAccepted, deduplicated events:")
    for event in deduped:
        price = "Free" if event.price == 0 else (
            f"{event.price} {event.currency}" if event.price is not None else "price unknown"
        )
        print(f"  - {event.title}")
        print(f"      when:  {event.start_time}")
        print(f"      venue: {event.venue_name or 'unknown'}")
        print(f"      price: {price}")
        print(f"      category: {event.category}  (confidence: {event.extraction_confidence})")

    return 0 if len(all_raw) > 0 and not dropped_normalize == len(all_raw) else 1


if __name__ == "__main__":
    sys.exit(main())

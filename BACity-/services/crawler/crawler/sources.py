"""Verified Bratislava event sources used by the prototype crawler.

The registry is deliberately data-driven. Adding a source later means adding
one SourceSeed instead of creating another spider. The spider discovers
event/detail links inside each source domain and delegates structured pages
to the common extraction ladder.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceSeed:
    name: str
    domain: str
    base_url: str
    event_url: str
    source_type: str
    reliability_score: float
    requires_js: bool = False
    crawl_frequency_minutes: int = 720
    language: str = "sk"
    tags: list[str] = field(default_factory=list)


ACTIVE_SOURCES: tuple[SourceSeed, ...] = (
    SourceSeed(
        "Visit Bratislava",
        "visitbratislava.com",
        "https://www.visitbratislava.com",
        "https://www.visitbratislava.com/events/",
        "tourism",
        0.90,
        language="en",
    ),
    SourceSeed(
        "Stará Tržnica",
        "staratrznica.sk",
        "https://staratrznica.sk",
        "https://staratrznica.sk/sk/program",
        "event_platform",
        0.85,
        language="sk",
    ),
    SourceSeed(
        "Slovak National Gallery",
        "sng.sk",
        "https://www.sng.sk",
        "https://www.sng.sk/en/slovak-national-gallery/whatson",
        "gallery",
        0.95,
        language="en",
    ),
    SourceSeed(
        "Bratislava City",
        "bratislava.sk",
        "https://www.bratislava.sk",
        "https://www.bratislava.sk/",
        "government",
        0.90,
        language="sk",
    ),
    SourceSeed(
        "GoOut Bratislava",
        "goout.net",
        "https://goout.net",
        "https://goout.net/en/bratislava/events/",
        "event_platform",
        0.75,
        language="en",
    ),
)

DEFERRED_SOURCES: tuple[SourceSeed, ...] = (
    SourceSeed(
        "Slovak National Theatre",
        "snd.sk",
        "https://snd.sk",
        "https://snd.sk/program",
        "theatre",
        0.97,
        requires_js=True,
        language="sk",
    ),
)


# Link text/URL hints used only for discovery. The crawler never follows
# arbitrary external links, which keeps the prototype bounded.
EVENT_LINK_HINTS = (
    "event", "events", "program", "programmes", "whatson", "what's-on",
    "poduj", "udalost", "calendar", "agenda", "akcia", "vystav",
    "exhibition", "koncert", "concert", "festival", "divadlo",
)


def as_dicts() -> list[dict]:
    return [s.__dict__.copy() for s in ACTIVE_SOURCES]


if __name__ == "__main__":
    print(f"{len(ACTIVE_SOURCES)} active sources.")
    for source in ACTIVE_SOURCES:
        print(f"  {source.name}: {source.event_url}")

"""
Initial Source Registry seed (spec sections 13-14). ~20 real, high-value
Bratislava sources to start with — mixing major institutions with the
small/niche venues the spec calls out as a core product requirement
(section 15). This is meant to be loaded into the `sources` table by a
seed script; crawl_frequency/reliability are starting estimates to be
tuned once real crawl data exists.

Domains are real; event_url paths are best-effort guesses at each site's
events listing and should be verified against the live site structure
before a spider is pointed at them (this file doesn't crawl anything —
see crawler/spiders/).
"""
from dataclasses import dataclass, field


@dataclass
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


INITIAL_SOURCES: list[SourceSeed] = [
    # --- Major cultural institutions (high reliability, low crawl frequency) ---
    SourceSeed("Slovak National Theatre", "snd.sk", "https://www.snd.sk", "/en/program",
               "theatre", 0.97, crawl_frequency_minutes=1440),
    SourceSeed("Slovak National Gallery", "sng.sk", "https://www.sng.sk", "/en/exhibitions",
               "gallery", 0.95, crawl_frequency_minutes=1440),
    SourceSeed("Bratislava City Museum", "muzeum.bratislava.sk", "https://muzeum.bratislava.sk",
               "/en/whats-on", "museum", 0.93, crawl_frequency_minutes=1440),
    SourceSeed("Visit Bratislava (tourism board)", "visitbratislava.com",
               "https://www.visitbratislava.com", "/en/events", "tourism", 0.9,
               crawl_frequency_minutes=720),
    SourceSeed("Bratislava City Council", "bratislava.sk", "https://bratislava.sk",
               "/en/events", "government", 0.9, crawl_frequency_minutes=720),

    # --- Independent / niche venues (spec section 15: core to the product) ---
    SourceSeed("A4 - Space for Contemporary Culture", "a4.sk", "https://a4.sk", "/program",
               "community", 0.85, requires_js=True, crawl_frequency_minutes=360),
    SourceSeed("Nu Spirit Bar", "nuspirit.sk", "https://www.nuspirit.sk", "/program",
               "club", 0.75, crawl_frequency_minutes=360),
    SourceSeed("Fuga", "fuga.sk", "https://fuga.sk", "/program", "club", 0.75,
               crawl_frequency_minutes=360),
    SourceSeed("Klub Randal", "randalklub.sk", "https://randalklub.sk", "/program",
               "club", 0.72, crawl_frequency_minutes=360),
    SourceSeed("Stará Tržnica", "staratrznica.sk", "https://staratrznica.sk", "/program",
               "event_platform", 0.85, crawl_frequency_minutes=360),
    SourceSeed("Cvernovka", "cvernovka.org", "https://www.cvernovka.org", "/program",
               "community", 0.8, requires_js=True, crawl_frequency_minutes=720),
    SourceSeed("KC Dunaj", "kcdunaj.sk", "https://kcdunaj.sk", "/program",
               "community", 0.78, crawl_frequency_minutes=360),
    SourceSeed("Design Factory Bratislava", "designfactory.sk", "https://designfactory.sk",
               "/program", "event_platform", 0.75, crawl_frequency_minutes=720),

    # --- Universities / student communities ---
    SourceSeed("Comenius University", "uniba.sk", "https://uniba.sk", "/en/news-and-events",
               "university", 0.88, crawl_frequency_minutes=1440),
    SourceSeed("Slovak University of Technology (STU)", "stuba.sk", "https://www.stuba.sk",
               "/sk/aktuality", "university", 0.85, crawl_frequency_minutes=1440),
    SourceSeed("ESN Bratislava (Erasmus Student Network)", "esnbratislava.sk",
               "https://esnbratislava.sk", "/events", "community", 0.7,
               crawl_frequency_minutes=720),

    # --- Sports / community / markets ---
    SourceSeed("Bratislava City Marathon", "bratislavamarathon.com",
               "https://www.bratislavamarathon.com", "/en/events", "sports", 0.8,
               crawl_frequency_minutes=1440),
    SourceSeed("Trhovisko Farmers Markets Bratislava", "trhbratislava.sk",
               "https://trhbratislava.sk", "/kalendar", "community", 0.7,
               crawl_frequency_minutes=1440),

    # --- Aggregators / listings (useful for discovery, lower per-item trust) ---
    SourceSeed("Kam do mesta (Bratislava listings)", "kamdomesta.sk",
               "https://www.kamdomesta.sk", "/bratislava", "event_platform", 0.65,
               requires_js=True, crawl_frequency_minutes=180),
    SourceSeed("BratislavaEvents.sk", "bratislavaevents.sk", "https://www.bratislavaevents.sk",
               "/", "event_platform", 0.6, crawl_frequency_minutes=180),
]


def as_dicts() -> list[dict]:
    return [s.__dict__ for s in INITIAL_SOURCES]


if __name__ == "__main__":
    print(f"{len(INITIAL_SOURCES)} seed sources defined.")
    for s in INITIAL_SOURCES:
        print(f"  [{s.source_type:14s}] {s.name} ({s.domain}) reliability={s.reliability_score}")

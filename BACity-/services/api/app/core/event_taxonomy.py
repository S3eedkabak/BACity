"""Pure publisher/title taxonomy; synchronized with crawler regression tests."""
import re
from typing import Optional

CATEGORY_KEYWORDS = {
    "Festivals": ["festival"],
    "Community": ["community", "komunit"],
    "Student": ["student", "študent", "univerzita", "university"],
    "Comedy": ["comedy", "standup", "stand-up", "komédia"],
    "Theatre": ["divadlo", "theatre", "theater", "drama", "činohra", "opera", "balet"],
    "Sports": ["sport", "šport", "run", "marathon", "tournament"],
    "Family": ["family", "rodina", "kids", "deti", "detské"],
    "Markets": ["market", "trh", "trhy"],
    "Workshops": ["workshop", "dielňa", "dielna", "seminar"],
    "Food & Drink": ["food", "wine", "beer", "tasting", "degustácia", "degustacia"],
    "Culture": ["kultúra", "kultura", "culture", "exhibition", "výstava", "vystava", "film", "cinema", "premietanie", "documentary"],
    "Music": ["concert", "jazz", "rock", "metal", "gig", "band", "koncert"],
    "Nightlife": ["techno", "house music", "house party", "party", "nightclub", "dj", "clubbing", "rave", "clubnight"],
}


def guess_category(title: str, description: Optional[str], hint: Optional[str]) -> str:
    # Publisher taxonomy and title outrank prose; venues never supply taxonomy.
    canonical={name.casefold():name for name in [*CATEGORY_KEYWORDS,'Arts','Exhibitions','Education','Networking','Technology','Other']}
    if (hint or '').strip().casefold() in canonical:
        return canonical[hint.strip().casefold()]
    def matching(value):
        value = (value or '').casefold()
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(re.search(r'(?<!\w)' + re.escape(keyword) + r'\w*', value) for keyword in keywords):
                return category
    exhibition = r'(?<!\w)(exhibition|výstav|vystav|expozíci|expozici)\w*'
    for value in (hint, title):
        if re.search(r'(?<!\w)(workshop|dielňa|dielna|seminar)\w*',(value or '').casefold()):
            return 'Workshops'
        if re.search(exhibition, (value or '').casefold()):
            return 'Exhibitions'
        result = matching(value)
        if result:
            return result
    if re.search(exhibition, (description or '').casefold()):
        return 'Exhibitions'
    return matching(description) or 'Other'

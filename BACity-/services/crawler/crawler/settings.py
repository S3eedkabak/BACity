"""Scrapy project settings. Kept conservative per spec section 12/59:
respect robots.txt, throttle aggressively, identify the bot honestly."""
import os

BOT_NAME = "bratislava_events_bot"
SPIDER_MODULES = ["crawler.spiders"]
NEWSPIDER_MODULE = "crawler.spiders"

USER_AGENT = os.environ.get(
    "CRAWLER_USER_AGENT", "BratislavaEventsBot/0.1 (+https://example.com/bot)"
)

ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 2
DOWNLOAD_DELAY = 1.5
AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 10.0

RETRY_TIMES = 2
DOWNLOAD_TIMEOUT = 20

ITEM_PIPELINES = {
    "crawler.pipelines.NormalizePipeline": 100,
    "crawler.pipelines.ValidatePipeline": 200,
    "crawler.pipelines.ApiSubmitPipeline": 300,
}

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

# Playwright is opt-in per-source (Source.requires_js), not global —
# spec section 17: it's a fallback, not the default path.
PLAYWRIGHT_LAUNCH_OPTIONS = {"headless": True}

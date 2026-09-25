"""Test-only entry point: permit loopback fixture server, retain robots and retries."""
import json
import sys
from urllib.parse import urlsplit
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from crawler.sources import SourceSeed
from crawler.spiders import discovery

discovery.allowed_url = lambda url: urlsplit(url).hostname == '127.0.0.1'
settings = get_project_settings()
settings.set('DOWNLOADER_MIDDLEWARES', {'crawler.middleware.PublicNetworkMiddleware': None}, priority='cmdline')
settings.set('DOWNLOAD_DELAY', 0, priority='cmdline')
settings.set('AUTOTHROTTLE_ENABLED', False, priority='cmdline')
settings.set('LOG_LEVEL', 'ERROR', priority='cmdline')
settings.set('GEOCODER_URL', '', priority='cmdline')
process = CrawlerProcess(settings)
crawler = process.create_crawler(discovery.DiscoverySpider)
seed = SourceSeed('Fixture', '127.0.0.1', sys.argv[1], sys.argv[1] + '/events', 'venue', .95)
process.crawl(crawler, source=seed)
process.start()
stats = crawler.stats.get_stats()
print(json.dumps(stats, default=str))
assert stats.get('item_scraped_count', 0) >= 2, stats
assert not any(value for key, value in stats.items() if key.startswith('spider_exceptions/')), stats
assert stats.get('ingestion/pending', 0) == 0, stats

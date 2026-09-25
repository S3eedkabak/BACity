"""One reactor per subprocess, with machine-readable success criteria."""
import argparse
import json
from pathlib import Path
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from crawler.sources import SourceSeed
from crawler.spiders.discovery import DiscoverySpider


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--stats", required=True)
    args = parser.parse_args()
    settings = get_project_settings()
    import os
    timeout = int(os.getenv('CRAWLER_JOB_TIMEOUT', '900'))
    settings.set('CLOSESPIDER_TIMEOUT', max(10, timeout - 30), priority='cmdline')
    process = CrawlerProcess(settings)
    crawler = process.create_crawler(DiscoverySpider)
    errors = []
    deferred = process.crawl(crawler, source=SourceSeed(**json.loads(args.source)))
    deferred.addErrback(lambda failure: errors.append(str(failure.value)))
    process.start()
    stats = crawler.stats.get_stats()
    stats['success'] = bool(not errors and stats.get('finish_reason') in ('finished', 'closespider_timeout', 'closespider_pagecount')
                            and stats.get('response_received_count', 0) > 0
                            and stats.get('item_scraped_count', 0) > 0
                            and not any(value for key, value in stats.items() if key.startswith('spider_exceptions/')))
    if errors:
        stats['error'] = '; '.join(errors)
    Path(args.stats).write_text(json.dumps(stats, default=str), encoding='utf-8')
    raise SystemExit(0 if stats['success'] else 1)


if __name__ == '__main__':
    main()

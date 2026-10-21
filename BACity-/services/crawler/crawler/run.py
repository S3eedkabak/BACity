"""One reactor per subprocess, with machine-readable success criteria."""
import argparse
import json
from pathlib import Path
from scrapy.crawler import CrawlerProcess
from scrapy import signals
from scrapy.utils.project import get_project_settings
from crawler.sources import SourceSeed
from crawler.spiders.discovery import DiscoverySpider


def successful(stats, errors):
    return bool(not errors and stats.get('finish_reason') in (
        'finished','closespider_timeout','closespider_pagecount','closespider_itemcount')
        and stats.get('response_received_count',0)>0
        and not stats.get('source/request_errors',0)
        and not stats.get('extraction/errors',0)
        and not stats.get('item_error_count',0)
        and not stats.get('log_count/ERROR',0)
        and not any(value for key,value in stats.items() if key.startswith('spider_exceptions/')))


def track_pipeline_errors(crawler,errors):
    def failed(failure):
        crawler.stats.inc_value('item_error_count')
        errors.append('item_pipeline_failure:'+type(failure.value).__name__)
    crawler.signals.connect(failed,signal=signals.item_error,weak=False)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--stats", required=True)
    parser.add_argument('--inspection', action='store_true')
    parser.add_argument('--audit', action='store_true', help='Validate live extraction without geocoding or ingestion')
    parser.add_argument('--output', help='Export validated audit records as JSON lines (requires --audit)')
    args = parser.parse_args()
    if args.output and not args.audit:
        parser.error('--output requires --audit')
    source=SourceSeed(**json.loads(args.source))
    settings = get_project_settings()
    settings.set('CLOSESPIDER_PAGECOUNT',min(300,max(1,source.max_pages)),priority='cmdline')
    if args.output:
        settings.set('FEEDS', {Path(args.output).resolve().as_uri(): {'format':'jsonlines','overwrite':True}}, priority='cmdline')
    if args.audit:
        settings.set('ITEM_PIPELINES', {
            'crawler.pipelines.NormalizePipeline':100,
            'crawler.pipelines.ValidatePipeline':200,
            'crawler.pipelines.QualityAuditPipeline':300,
        }, priority='cmdline')
    import os
    timeout = int(os.getenv('CRAWLER_JOB_TIMEOUT', '900'))
    settings.set('CLOSESPIDER_TIMEOUT', max(10, timeout - 30), priority='cmdline')
    if args.inspection:
        settings.set('CLOSESPIDER_TIMEOUT', 90, priority='cmdline')
        settings.set('CLOSESPIDER_PAGECOUNT', 10, priority='cmdline')
        settings.set('CLOSESPIDER_ITEMCOUNT', 100, priority='cmdline')
        settings.set('CONCURRENT_REQUESTS', 2, priority='cmdline')
    process = CrawlerProcess(settings)
    crawler = process.create_crawler(DiscoverySpider)
    errors = []
    track_pipeline_errors(crawler,errors)
    deferred = process.crawl(crawler, source=source)
    deferred.addErrback(lambda failure: errors.append(str(failure.value)))
    process.start()
    stats = crawler.stats.get_stats()
    stats['audit'] = args.audit
    # A reachable source with zero current events is a valid crawl, not an outage.
    stats['success'] = successful(stats,errors)
    if errors:
        stats['error'] = '; '.join(errors)
    Path(args.stats).write_text(json.dumps(stats, default=str), encoding='utf-8')
    raise SystemExit(0 if stats['success'] else 1)


if __name__ == '__main__':
    main()

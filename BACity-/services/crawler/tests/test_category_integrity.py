import pytest
from crawler.items import RawEvent
from crawler.processing.normalize import normalize_event,guess_category

@pytest.mark.parametrize('title,description,hint,expected',[
 ('Vincent van Gogh','An immersive exhibition of paintings at Sport Mall',None,'Exhibitions'),
 ('A show','A long generic description','Exhibition','Exhibitions'),
 ('Jazz concert','Evening at Sport Mall',None,'Music'),
 ('Marathon','City race',None,'Sports'),
 ('DJ party','Club music',None,'Nightlife'),
 ('Culture festival',None,'Culture','Culture'),
 ('Engineering talk',None,None,'Other'),
])
def test_taxonomy(title,description,hint,expected):
 assert guess_category(title,description,hint)==expected

def test_venue_does_not_supply_category():
 event=normalize_event(RawEvent(title='Paintings',start_raw='2027-01-01T10:00:00+01:00',venue_name='Sport Mall',description='An immersive exhibition of paintings',source_url='https://venue.example/event'))
 assert event.category=='Exhibitions'
 assert 'sports' not in event.tags

def test_running_club_is_not_a_nightclub():
 assert guess_category('TU–BA Archirun Club','The run is open to everyone, pace 6:30 minutes per km',None)=='Sports'

def test_explicit_cancelled_title_and_sentinel_dates():
 event=normalize_event(RawEvent(title='Cancelled // Theatre show',start_raw='2016-01-01T12:00:00Z',end_raw='2038-01-01T00:00:00Z',description='Provided by GoOut.sk',source_url='https://visitbratislava.com/event'))
 assert event.event_status=='cancelled' and event.end_time is None

def test_card_title_uses_heading_and_does_not_use_an_outbound_share_link():
 from crawler.extraction.generic_extractor import extract_event_cards
 cards=extract_event_cards('<article><a href="https://facebook.com/share">Share</a><h3><a href="/events/art">Art exhibition</a></h3><time datetime="2027-01-02">2 Jan</time><p class="venue">Gallery</p></article>','https://gallery.example/events')
 assert cards and cards[0].title=='Art exhibition'
 assert cards[0].source_url=='https://gallery.example/events/art'


def test_year_2000_permanent_listing_has_unknown_end():
 event=normalize_event(RawEvent(title='Permanent collection',start_raw='2000-01-01T12:00:00Z',end_raw='2030-01-01T22:59:00Z',source_url='https://calendar.example/exhibition'))
 assert event.end_time is None and event.temporal_evidence=='unknown'


def test_exhibition_reference_does_not_reclassify_a_workshop_or_historical_house():
 from crawler.processing.normalize import guess_category
 assert guess_category('Sochársky workshop k výstave',None,None)=='Workshops'
 assert guess_category('The Graphic Cabinets','The historical house contains engraved pictures.',None)=='Other'
 assert guess_category('Halloween Rave',None,None)=='Nightlife'


def test_explicit_publisher_category_outranks_incidental_description():
 from crawler.processing.normalize import guess_category
 assert guess_category('An artist','The historical gallery hosts this concert','Music')=='Music'
 assert guess_category('An event','A social gathering','Nightlife')=='Nightlife'


def test_pipeline_counts_raw_and_normalized_stages_separately():
 from collections import Counter
 from types import SimpleNamespace
 import pytest
 from crawler.pipelines import NormalizePipeline,DropItem
 class Stats:
  def __init__(self):self.values=Counter()
  def inc_value(self,key,count=1):self.values[key]+=count
 stats=Stats();spider=SimpleNamespace(crawler=SimpleNamespace(stats=stats))
 pipeline=NormalizePipeline()
 pipeline.process_item(RawEvent(title='A real concert',start_raw='2027-01-02T19:00:00Z',source_url='https://hall.example/event'),spider)
 with pytest.raises(DropItem):pipeline.process_item(RawEvent(title='No schedule',start_raw='',source_url='https://hall.example/unknown'),spider)
 assert stats.values['pipeline/raw_listings']==2
 assert stats.values['pipeline/normalized_listings']==1
 assert stats.values['validation/rejected/normalization']==1

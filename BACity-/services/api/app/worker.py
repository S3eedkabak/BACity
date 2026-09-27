"""Run continuously beside the API: SMTP outbox and retention maintenance."""
import argparse
import logging
import time
from datetime import datetime, timedelta
from app.config import get_settings
from app.database import SessionLocal
from app.models.community import MailOutbox, Message, ActionToken, RateBucket
from app.models.community import CityUtility
from app.core.mail import deliver_pending_mail
from app.crud.ingestion import expire_events
from app.core.utilities import OFFICIAL_TOILET_SOURCE
from app.utility_import import sync_bratislava_toilets

log = logging.getLogger('bacity.worker')
_last_utility_sync_attempt = None


def tick():
    global _last_utility_sync_attempt
    s = get_settings()
    with SessionLocal() as db:
        now = datetime.utcnow()
        if s.smtp_host:
            deliver_pending_mail(db, now=now)
        db.query(Message).filter(Message.created_at < now-timedelta(days=s.message_retention_days)).delete()
        db.query(ActionToken).filter(ActionToken.expires_at < now-timedelta(days=1)).delete()
        db.query(MailOutbox).filter(MailOutbox.created_at < now-timedelta(days=7)).delete()
        db.query(RateBucket).filter(RateBucket.window < int(time.time()) - 172800).delete()
        db.commit()
        expire_events(db)
        if s.utility_sync_enabled:
            last_sync = db.query(CityUtility.updated_at).filter(
                CityUtility.source_url.startswith(OFFICIAL_TOILET_SOURCE)
            ).order_by(CityUtility.updated_at.desc()).limit(1).scalar()
            latest_attempt = max(filter(None, [last_sync, _last_utility_sync_attempt]), default=None)
            if not latest_attempt or latest_attempt < now - timedelta(hours=s.utility_sync_interval_hours):
                _last_utility_sync_attempt = now
                try:
                    result = sync_bratislava_toilets(db)
                    log.info('Public-toilet dataset synchronized: %s', result)
                except Exception:
                    db.rollback()
                    log.exception('Public-toilet dataset synchronization failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    log.info('Maintenance worker started smtp_configured=%s smtp_port=%s starttls=%s ssl=%s',
             bool(settings.smtp_host), settings.smtp_port, settings.smtp_starttls, settings.smtp_ssl)
    while True:
        try:
            tick()
        except Exception:
            log.exception('Maintenance cycle failed')
            if args.once:
                raise
        if args.once:
            return
        time.sleep(30)


if __name__ == '__main__':
    main()

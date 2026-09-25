"""Run continuously beside the API: SMTP outbox and retention maintenance."""
import argparse
import logging
import smtplib
import time
from datetime import datetime, timedelta
from email.message import EmailMessage
from app.config import get_settings
from app.database import SessionLocal
from app.models.community import MailOutbox, Message, ActionToken, RateBucket
from app.crud.ingestion import expire_events

log = logging.getLogger('bacity.worker')


def tick():
    s = get_settings()
    with SessionLocal() as db:
        now = datetime.utcnow()
        if s.smtp_host:
            messages = db.query(MailOutbox).filter(MailOutbox.sent_at.is_(None), MailOutbox.attempts < 10, MailOutbox.next_attempt_at <= now).with_for_update(skip_locked=True).limit(50).all()
            for item in messages:
                item.attempts += 1
                try:
                    message = EmailMessage()
                    message['From'], message['To'], message['Subject'] = s.mail_from, item.recipient, item.subject
                    message.set_content(item.body)
                    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
                        if s.smtp_starttls:
                            smtp.starttls()
                        if s.smtp_username:
                            smtp.login(s.smtp_username, s.smtp_password)
                        smtp.send_message(message)
                    item.sent_at, item.error, item.body = now, None, '[Delivered]'
                except (OSError, smtplib.SMTPException) as exc:
                    item.error = type(exc).__name__
                    item.next_attempt_at = now + timedelta(seconds=min(3600, 30 * 2 ** item.attempts))
            db.commit()
        db.query(Message).filter(Message.created_at < now-timedelta(days=s.message_retention_days)).delete()
        db.query(ActionToken).filter(ActionToken.expires_at < now-timedelta(days=1)).delete()
        db.query(MailOutbox).filter(MailOutbox.created_at < now-timedelta(days=7)).delete()
        db.query(RateBucket).filter(RateBucket.window < int(time.time()) - 172800).delete()
        db.commit()
        expire_events(db)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
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

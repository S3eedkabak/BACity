"""Transactional account email. Tokens are hashed; delivery is retried from an outbox."""
import hashlib
import logging
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import formataddr

from sqlalchemy.orm import sessionmaker

from app.models.community import ActionToken, MailOutbox
from app.config import get_settings

log = logging.getLogger("bacity.mail")
MAX_MAIL_ATTEMPTS = 10


def _recipient_ref(recipient: str) -> str:
    """Stable diagnostic reference that does not disclose an email address."""
    return hashlib.sha256(recipient.strip().lower().encode()).hexdigest()[:12]


def queue_action(db, user, purpose):
    now = datetime.utcnow()
    db.query(ActionToken).filter_by(user_id=user.id, purpose=purpose, used_at=None).update({'used_at': now})
    token = secrets.token_urlsafe(32)
    db.add(ActionToken(user_id=user.id, token_hash=hashlib.sha256(token.encode()).hexdigest(), purpose=purpose,
                       expires_at=now + timedelta(minutes=30 if purpose == 'reset' else 1440)))
    url = f'{get_settings().account_action_url.rstrip("/")}/account?action={purpose}&token={token}'
    subject = 'Reset your BACity password' if purpose == 'reset' else 'Verify your BACity email'
    body = f'Open this link to {purpose} your BACity account:\n{url}\nIf you did not request this, ignore this email.'
    # Replace an unsent obsolete message instead of creating a retry storm of
    # links whose tokens were invalidated above.
    pending = db.query(MailOutbox).filter_by(recipient=user.email, subject=subject, sent_at=None).first()
    if pending:
        pending.body, pending.attempts, pending.next_attempt_at, pending.error = body, 0, now, None
        action = "replaced"
    else:
        db.add(MailOutbox(recipient=user.email, subject=subject, body=body))
        action = "created"
    log.info("Account email queued purpose=%s recipient_ref=%s outbox_action=%s",
             purpose, _recipient_ref(user.email), action)


def deliver_pending_mail(db, *, now: datetime | None = None, limit: int = 50) -> int:
    """Attempt one bounded outbox batch and return the number accepted by SMTP."""
    settings = get_settings()
    if not settings.smtp_host:
        log.warning("Account email delivery deferred smtp_configured=false")
        return 0

    now = now or datetime.utcnow()
    messages = (
        db.query(MailOutbox)
        .filter(
            MailOutbox.sent_at.is_(None),
            MailOutbox.attempts < MAX_MAIL_ATTEMPTS,
            MailOutbox.next_attempt_at <= now,
        )
        .with_for_update(skip_locked=True)
        .limit(limit)
        .all()
    )
    accepted = 0
    for item in messages:
        item.attempts += 1
        recipient_ref = _recipient_ref(item.recipient)
        phase = "connection"
        smtp = None
        log.info("Account email SMTP attempt outbox_id=%s recipient_ref=%s attempt=%s",
                 item.id, recipient_ref, item.attempts)
        try:
            message = EmailMessage()
            message["From"] = formataddr((settings.mail_from_name, settings.mail_from))
            message["To"] = item.recipient
            message["Subject"] = item.subject
            message.set_content(item.body)

            smtp_class = smtplib.SMTP_SSL if settings.smtp_ssl else smtplib.SMTP
            smtp = smtp_class(settings.smtp_host, settings.smtp_port, timeout=15)
            if settings.smtp_starttls:
                phase = "connection"
                smtp.starttls()
            if settings.smtp_username:
                phase = "authentication"
                smtp.login(settings.smtp_username, settings.smtp_password)
            phase = "send"
            refused = smtp.send_message(message)
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)

            item.sent_at, item.error, item.body = now, None, "[Delivered]"
            accepted += 1
            log.info("Account email accepted by SMTP provider outbox_id=%s recipient_ref=%s attempt=%s",
                     item.id, recipient_ref, item.attempts)
        except (OSError, smtplib.SMTPException) as exc:
            item.error = type(exc).__name__
            item.next_attempt_at = now + timedelta(seconds=min(3600, 30 * 2 ** item.attempts))
            if isinstance(exc, smtplib.SMTPAuthenticationError) or phase == "authentication":
                failure = "authentication"
            elif phase == "connection":
                failure = "connection"
            else:
                failure = "send"
            log.warning("Account email SMTP %s failure outbox_id=%s recipient_ref=%s attempt=%s error_type=%s",
                        failure, item.id, recipient_ref, item.attempts, type(exc).__name__)
        finally:
            if smtp is not None:
                try:
                    smtp.quit()
                except (OSError, smtplib.SMTPException):
                    try:
                        smtp.close()
                    except (OSError, smtplib.SMTPException):
                        pass
    db.commit()
    return accepted


def dispatch_pending_mail(engine) -> int:
    """Open an independent session for a post-response delivery attempt."""
    delivery_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with delivery_session() as db:
        return deliver_pending_mail(db)


def consume_action(db, token, purpose):
    from fastapi import HTTPException
    now = datetime.utcnow()
    item = db.query(ActionToken).filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest(), purpose=purpose).with_for_update().first()
    if not item or item.used_at or item.expires_at < now:
        raise HTTPException(400, 'Invalid or expired link')
    item.used_at = now
    return item.user_id

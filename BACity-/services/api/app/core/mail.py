"""Transactional account email. Tokens are hashed; delivery is retried from an outbox."""
import hashlib
import secrets
from datetime import datetime, timedelta
from app.models.community import ActionToken, MailOutbox
from app.config import get_settings


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
    else:
        db.add(MailOutbox(recipient=user.email, subject=subject, body=body))


def consume_action(db, token, purpose):
    from fastapi import HTTPException
    now = datetime.utcnow()
    item = db.query(ActionToken).filter_by(token_hash=hashlib.sha256(token.encode()).hexdigest(), purpose=purpose).with_for_update().first()
    if not item or item.used_at or item.expires_at < now:
        raise HTTPException(400, 'Invalid or expired link')
    item.used_at = now
    return item.user_id

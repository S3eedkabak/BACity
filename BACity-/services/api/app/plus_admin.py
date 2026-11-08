"""Explicitly enabled, development-only BACity+ fixture helper.

Usage: ENABLE_DEVELOPMENT_PLUS_GRANTS=true python -m app.plus_admin user@example.com active
"""
import argparse
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.core.entitlements import BACITY_PLUS
from app.database import SessionLocal
from app.models.entitlement import EntitlementGrant
from app.models.user import User


def set_development_plus(db: Session, email: str, mode: str, settings: Settings | None = None) -> EntitlementGrant | None:
    settings = settings or get_settings()
    if settings.environment != "development" or not settings.enable_development_plus_grants:
        raise RuntimeError("Development BACity+ grants are disabled")
    if mode not in {"free", "active", "expired"}:
        raise ValueError("Mode must be free, active, or expired")
    user = db.query(User).filter(User.email == email.strip().lower()).one_or_none()
    if not user:
        raise ValueError("User not found")

    now = datetime.utcnow()
    existing = db.query(EntitlementGrant).filter(
        EntitlementGrant.user_id == user.id,
        EntitlementGrant.entitlement == BACITY_PLUS,
        EntitlementGrant.source == "development",
        EntitlementGrant.revoked_at.is_(None),
    ).all()
    for grant in existing:
        grant.revoked_at = now

    grant = None
    if mode != "free":
        grant = EntitlementGrant(
            user_id=user.id,
            entitlement=BACITY_PLUS,
            source="development",
            reason_category="local_fixture",
            valid_from=now - timedelta(days=2 if mode == "expired" else 0),
            valid_until=now - timedelta(days=1) if mode == "expired" else now + timedelta(days=30),
            audit_metadata={"fixture_mode": mode},
        )
        db.add(grant)
    db.commit()
    return grant


def main():
    parser = argparse.ArgumentParser(description="Set a local BACity+ fixture state")
    parser.add_argument("email")
    parser.add_argument("mode", choices=("free", "active", "expired"))
    args = parser.parse_args()
    with SessionLocal() as db:
        set_development_plus(db, args.email, args.mode)
    print(f"Development entitlement state set to {args.mode}.")


if __name__ == "__main__":
    main()

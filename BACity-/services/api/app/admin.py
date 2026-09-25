"""Bootstrap the first administrator from a verified account, without public escalation."""
import argparse
from app.database import SessionLocal
from app.models.user import User
from app.core.community import audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('email')
    args = parser.parse_args()
    with SessionLocal() as db:
        if db.query(User).filter_by(role='ADMIN', active=True).first():
            raise SystemExit('An administrator already exists; use the audited role API')
        user = db.query(User).filter_by(email=args.email.lower(), email_verified=True, active=True).first()
        if not user:
            raise SystemExit('Register and verify the account first')
        user.role = 'ADMIN'
        user.token_version += 1
        audit(db, user, 'bootstrap_admin', 'user', user.id)
        db.commit()
        print('Administrator created; sign in again')


if __name__ == '__main__':
    main()

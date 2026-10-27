"""Host-owner provisioning and protected audit export; never a public signup."""
import argparse
import json
import secrets
import time
from .db import session_factory
from .models import Staff, Invitation, Credential, StaffSession, AuditEvent, AuditHead
from .security import audit,digest,verify_audit


def main():
    parser=argparse.ArgumentParser(description='Run only on the private administrative host')
    sub=parser.add_subparsers(dest='action',required=True)
    bootstrap=sub.add_parser('bootstrap-owner');bootstrap.add_argument('--email',required=True);bootstrap.add_argument('--name',required=True)
    recovery=sub.add_parser('recover-owner');recovery.add_argument('--email',required=True)
    sub.add_parser('export-audit')
    sub.add_parser('verify-audit')
    args=parser.parse_args()
    with session_factory()() as db:
        if args.action in ('export-audit','verify-audit'):
            rows=db.query(AuditEvent).order_by(AuditEvent.sequence).yield_per(500)
            if not verify_audit(rows,db.get(AuditHead,1)):
                raise SystemExit('Audit chain verification failed')
            if args.action=='export-audit':
                # The caller redirects to owner-only storage / a separate backup host.
                for event in rows:
                    print(json.dumps({'sequence':event.sequence,'previous':event.previous,'digest':event.digest,'record':event.record}))
                audit(db,'local-operator','audit.export');db.commit()
            else:
                print('Audit chain verified')
            return
        if '@' not in args.email or len(args.email)>254 or any(c in args.email for c in '\r\n '):
            raise SystemExit('Use an individual staff email address')
        if args.action=='bootstrap-owner':
            if db.query(Staff).count():
                raise SystemExit('Owner already provisioned; use owner-controlled invitations')
            staff=Staff(email=args.email.lower(),name=args.name[:120],role='OWNER')
            db.add(staff);db.flush()
        else:
            staff=db.query(Staff).filter_by(email=args.email.lower(),role='OWNER',active=True).first()
            if not staff:
                raise SystemExit('Active owner not found')
            # Deliberately requires host access; all existing passkeys and sessions revoked.
            db.query(Credential).filter_by(staff_id=staff.id).update({'revoked':True})
            db.query(StaffSession).filter_by(staff_id=staff.id).update({'revoked':True})
            db.query(Invitation).filter_by(staff_id=staff.id).update({'consumed':True})
            staff.version+=1
        token=secrets.token_urlsafe(32)
        db.add(Invitation(digest=digest(token),staff_id=staff.id,expires=time.time()+900))
        audit(db,'local-operator','staff.'+args.action,staff.id);db.commit()
        print('One-use enrollment invitation (15 minutes). Deliver privately; never put it in a URL:')
        print(token)

if __name__=='__main__':
    main()

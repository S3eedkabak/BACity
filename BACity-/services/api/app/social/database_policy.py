"""Fail closed on migration-owner credentials and unsafe deployment role grants."""
from fastapi import HTTPException
from sqlalchemy import text


def verify_database_policy(db,*,service_role,consumer_role):
    if db.bind.dialect.name=='sqlite':
        # Explicit disposable development setting; never a production assurance claim.
        return
    if service_role not in ('staff','gateway','relay','maintenance') or not consumer_role:
        raise HTTPException(503,'Configure distinct private and public database roles before enabling Level 4')
    current=db.execute(text("""SELECT current_user, r.rolsuper, pg_get_userbyid(d.datdba)=current_user AS owns_database
        FROM pg_roles r JOIN pg_database d ON d.datname=current_database() WHERE r.rolname=current_user""")).one()
    group='bacity_l4_'+service_role
    member=db.execute(text('SELECT pg_has_role(current_user,:role,\'member\')'),{'role':group}).scalar()
    if current.rolsuper or current.owns_database or not member:
        raise HTTPException(503,'The service database role is too privileged or incorrectly assigned')
    # The configured consumer login must also be deprivileged; an owner bypasses grants.
    safe_consumer=db.execute(text('SELECT 1 FROM pg_roles WHERE rolname=:role AND NOT rolsuper'),{'role':consumer_role}).scalar()
    if not safe_consumer:
        raise HTTPException(503,'The consumer API database role is not verified')
    for table in ('l4_credentials','l4_sessions','l4_invitations','l4_staff'):
        allowed=db.execute(text('SELECT has_table_privilege(:role,:table,\'SELECT\')'),{'role':consumer_role,'table':table}).scalar()
        if allowed:
            raise HTTPException(503,'The public API must not have access to private staff tables')
    for privilege in ('UPDATE','DELETE','TRUNCATE'):
        if db.execute(text('SELECT has_table_privilege(current_user,\'l4_audit_events\',:privilege)'),{'privilege':privilege}).scalar():
            raise HTTPException(503,'Audit database permissions must be append-only')
    if service_role in ('staff','gateway','relay'):
        for table in ('users','oauth_identities','consumer_subscriptions'):
            if db.execute(text('SELECT has_table_privilege(current_user,:table,\'SELECT\')'),{'table':table}).scalar():
                raise HTTPException(503,'Private Level 4 services must not read consumer account data')
    if service_role in ('staff','gateway'):
        if db.execute(text("SELECT has_table_privilege(current_user,'events','INSERT')")).scalar():
            raise HTTPException(503,'Staff and collection gateways cannot write canonical events')
    if service_role=='gateway':
        if db.execute(text("SELECT has_table_privilege(current_user,'l4_credentials','SELECT')")).scalar():
            raise HTTPException(503,'Collection gateways cannot access staff credentials')

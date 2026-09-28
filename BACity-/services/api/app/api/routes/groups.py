import hashlib
import secrets
from datetime import datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_plus
from app.config import get_settings
from app.core.community import blocked, blocked_ids, notify, rate_limit
from app.core.entitlements import BACITY_PLUS, EntitlementService
from app.core.group_match import MAX_DB_CANDIDATES, ParticipantPreference, rank_group_candidates
from app.core.planning import local_planning_window
from app.core.recommendation_context import build_recommendation_context
from app.database import get_db
from app.models.event import Event, EventStatus
from app.models.group import GroupCandidate, GroupMatchRound, GroupParticipant, GroupSession, GroupVote
from app.models.user import User
from app.schemas.event import EventOut
from app.schemas.group import (
    GroupCreate, GroupCreateOut, GroupDetailOut, GroupSummaryOut, GroupUpdate,
    InviteOut, JoinRequest, MatchRequest, PreferenceUpdate, VoteRequest,
)

router = APIRouter(prefix="/groups", tags=["private group decisions"])

DEFAULT_START = time(10)
DEFAULT_END = time(23)
SESSION_WRITE_GRACE = timedelta(days=2)
RETENTION = timedelta(days=90)
INVITE_LIFETIME = timedelta(days=7)


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _new_invite(group: GroupSession):
    raw = secrets.token_urlsafe(32)
    group.invite_token_hash = _token_hash(raw)
    group.invite_expires_at = min(group.expires_at, datetime.utcnow() + INVITE_LIFETIME)
    return raw


def _purge_due(db):
    return db.query(GroupSession).filter(GroupSession.purge_after <= datetime.utcnow()).delete(synchronize_session=False)


def _refresh_expiration(group: GroupSession):
    if group.status not in {"cancelled", "expired"} and group.expires_at <= datetime.utcnow():
        group.status = "expired"
        group.invite_token_hash = None
        group.invite_expires_at = None


def _group(db, identifier, *, for_update: bool = False) -> GroupSession:
    query = db.query(GroupSession).filter(GroupSession.id == identifier)
    if for_update:
        query = query.with_for_update()
    group = query.first()
    if not group:
        raise HTTPException(404, "Not found")
    _refresh_expiration(group)
    return group


def _membership(db, group, user):
    membership = db.query(GroupParticipant).filter_by(group_id=group.id, user_id=user.id).first()
    if not membership:
        raise HTTPException(404, "Group not found")
    return membership


def _host(group, user):
    if group.host_id != user.id:
        raise HTTPException(403, "Only the host can perform this action")


def _recalculate_ready(db, group):
    members = db.query(GroupParticipant).filter_by(group_id=group.id).all()
    if group.status in {"open", "ready", "completed"}:
        group.status = "ready" if len(members) >= 2 and all(member.ready for member in members) else "open"


def _round_progress(db, round_item, participant_ids, candidate_ids):
    if not candidate_ids:
        return 0
    votes = db.query(GroupVote.user_id, GroupVote.candidate_id).filter(
        GroupVote.user_id.in_(participant_ids), GroupVote.candidate_id.in_(candidate_ids)
    ).all()
    by_user: dict[UUID, set[UUID]] = {}
    for user_id, candidate_id in votes:
        by_user.setdefault(user_id, set()).add(candidate_id)
    return sum(candidate_ids.issubset(by_user.get(user_id, set())) for user_id in participant_ids)


def _active_round(db, group):
    return db.query(GroupMatchRound).filter_by(group_id=group.id).order_by(GroupMatchRound.round_number.desc()).first()


def _complete_if_everyone_voted(db, group, round_item):
    if not round_item or round_item.status != "voting":
        return False
    participant_ids = {user_id for (user_id,) in db.query(GroupParticipant.user_id).filter_by(group_id=group.id)}
    candidate_ids = {candidate_id for (candidate_id,) in db.query(GroupCandidate.id).filter_by(round_id=round_item.id)}
    if participant_ids and candidate_ids and _round_progress(db, round_item, participant_ids, candidate_ids) == len(participant_ids):
        round_item.status = "completed"
        round_item.revealed_at = datetime.utcnow()
        group.status = "completed"
        for participant_id in participant_ids:
            notify(db, participant_id, "group", "Your group results are ready", group.id)
        return True
    return False


def _serialize_group(db, group, user):
    members = db.query(GroupParticipant, User).join(User, User.id == GroupParticipant.user_id).filter(
        GroupParticipant.group_id == group.id
    ).order_by(GroupParticipant.joined_at, GroupParticipant.id).all()
    round_item = _active_round(db, group)
    round_out = None
    if round_item:
        candidates = db.query(GroupCandidate, Event).join(Event, Event.id == GroupCandidate.event_id).filter(
            GroupCandidate.round_id == round_item.id
        ).order_by(GroupCandidate.position).all()
        candidate_ids = {candidate.id for candidate, _ in candidates}
        participant_ids = {member.user_id for member, _ in members}
        votes = db.query(GroupVote).filter(GroupVote.candidate_id.in_(candidate_ids)).all() if candidate_ids else []
        my_votes = {vote.candidate_id: vote.value for vote in votes if vote.user_id == user.id}
        all_votes: dict[UUID, list[int]] = {}
        for vote in votes:
            if vote.user_id in participant_ids:
                all_votes.setdefault(vote.candidate_id, []).append(vote.value)
        visible = []
        for candidate, event in candidates:
            values = all_votes.get(candidate.id, [])
            aggregate = None
            explanations = list(candidate.explanations or [])
            if round_item.status == "completed":
                likes = values.count(1)
                dislikes = values.count(-1)
                aggregate = {"likes": likes, "neutral": values.count(0), "dislikes": dislikes, "score": sum(values)}
                if participant_ids and likes > len(participant_ids) / 2:
                    explanations = ["Popular with your group", *explanations]
                elif dislikes == 0:
                    explanations = ["No strong group dislikes", *explanations]
            visible.append({
                "id": candidate.id,
                "event": EventOut.model_validate(event),
                "explanations": list(dict.fromkeys(explanations))[:3],
                "my_vote": my_votes.get(candidate.id),
                "aggregate": aggregate,
                "_score": sum(values),
                "_likes": values.count(1),
                "_dislikes": values.count(-1),
                "_match": candidate.match_score,
                "_position": candidate.position,
            })
        if round_item.status == "completed":
            visible.sort(key=lambda item: (-item["_score"], -item["_likes"], item["_dislikes"], -item["_match"], item["_position"]))
        for item in visible:
            for private in ("_score", "_likes", "_dislikes", "_match", "_position"):
                item.pop(private)
        round_out = {
            "id": round_item.id,
            "number": round_item.round_number,
            "status": round_item.status,
            "voted_participants": _round_progress(db, round_item, participant_ids, candidate_ids),
            "participant_count": len(participant_ids),
            "candidates": visible,
        }
    return {
        "id": group.id,
        "name": group.name,
        "status": group.status,
        "target_date": group.target_date,
        "starts_at": group.starts_at.replace(tzinfo=timezone.utc),
        "ends_at": group.ends_at.replace(tzinfo=timezone.utc),
        "participant_count": len(members),
        "max_participants": group.max_participants,
        "role": "host" if group.host_id == user.id else "participant",
        "categories": group.categories or [],
        "expires_at": group.expires_at.replace(tzinfo=timezone.utc),
        "participants": [{
            "id": member_user.id,
            "display_name": member_user.display_name or "BACity member",
            "avatar_url": member_user.avatar_url,
            "is_host": member_user.id == group.host_id,
            "ready": member.ready,
        } for member, member_user in members],
        "round": round_out,
    }


@router.get("", response_model=list[GroupSummaryOut])
def list_groups(user=Depends(get_current_user), db: Session = Depends(get_db)):
    purged = _purge_due(db)
    rows = db.query(GroupSession, func.count(GroupParticipant.id)).join(
        GroupParticipant, GroupParticipant.group_id == GroupSession.id
    ).filter(
        GroupSession.id.in_(db.query(GroupParticipant.group_id).filter_by(user_id=user.id))
    ).group_by(GroupSession.id).order_by(GroupSession.updated_at.desc()).limit(100).all()
    output = []
    changed = bool(purged)
    for group, count in rows:
        previous = group.status
        _refresh_expiration(group)
        changed = changed or previous != group.status
        output.append({
            "id": group.id, "name": group.name, "status": group.status,
            "target_date": group.target_date,
            "starts_at": group.starts_at.replace(tzinfo=timezone.utc),
            "ends_at": group.ends_at.replace(tzinfo=timezone.utc),
            "participant_count": count, "max_participants": group.max_participants,
            "role": "host" if group.host_id == user.id else "participant",
        })
    if changed:
        db.commit()
    return output


@router.post("", response_model=GroupCreateOut)
def create_group(payload: GroupCreate, user=Depends(require_plus), db: Session = Depends(get_db)):
    rate_limit(db, f"group-create:{user.id}", 10, 86400)
    _purge_due(db)
    timezone_name = get_settings().default_timezone
    try:
        window = local_planning_window(payload.target_date, payload.start_time or DEFAULT_START, payload.end_time or DEFAULT_END, timezone_name)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    now = datetime.utcnow()
    if window.starts_at_utc <= now or window.starts_at_utc > now + timedelta(days=60):
        raise HTTPException(422, "Choose a future date within 60 days")
    group = GroupSession(
        host_id=user.id, name=payload.name.strip(), target_date=payload.target_date,
        starts_at=window.starts_at_utc, ends_at=window.ends_at_utc,
        categories=[category.value for category in payload.categories],
        max_participants=payload.max_participants,
        expires_at=window.ends_at_utc + SESSION_WRITE_GRACE,
        purge_after=window.ends_at_utc + SESSION_WRITE_GRACE + RETENTION,
    )
    code = _new_invite(group)
    db.add(group)
    db.flush()
    db.add(GroupParticipant(group_id=group.id, user_id=user.id))
    db.commit()
    db.refresh(group)
    return {"group": _serialize_group(db, group, user), "join_code": code, "join_code_expires_at": group.invite_expires_at.replace(tzinfo=timezone.utc)}


@router.post("/join", response_model=GroupDetailOut)
def join_group(payload: JoinRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    rate_limit(db, f"group-join:{user.id}", 30)
    group = db.query(GroupSession).filter_by(invite_token_hash=_token_hash(payload.code)).with_for_update().first()
    now = datetime.utcnow()
    if not group or not group.invite_expires_at or group.invite_expires_at <= now:
        raise HTTPException(404, "Invite unavailable")
    _refresh_expiration(group)
    existing = db.query(GroupParticipant).filter_by(group_id=group.id, user_id=user.id).first()
    if existing:
        db.commit()
        return _serialize_group(db, group, user)
    if group.status not in {"open", "ready"}:
        raise HTTPException(409, "This group is no longer accepting participants")
    members = db.query(GroupParticipant).filter_by(group_id=group.id).all()
    if len(members) >= group.max_participants:
        raise HTTPException(409, "This group is full")
    if any(blocked(db, user.id, member.user_id) for member in members):
        raise HTTPException(403, "This invite is unavailable")
    db.add(GroupParticipant(group_id=group.id, user_id=user.id))
    group.status = "open"
    notify(db, group.host_id, "group", "A BACity member joined your group", group.id)
    db.commit()
    return _serialize_group(db, group, user)


@router.get("/{identifier}", response_model=GroupDetailOut)
def get_group(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    group = _group(db, identifier)
    _membership(db, group, user)
    db.commit()
    return _serialize_group(db, group, user)


@router.patch("/{identifier}", response_model=GroupDetailOut)
def update_group(identifier: UUID, payload: GroupUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    group = _group(db, identifier, for_update=True)
    _membership(db, group, user)
    _host(group, user)
    if group.status not in {"open", "ready", "completed"}:
        raise HTTPException(409, "Group configuration is locked")
    member_count = db.query(GroupParticipant).filter_by(group_id=group.id).count()
    if payload.max_participants is not None and payload.max_participants < member_count:
        raise HTTPException(422, "Participant limit cannot be below current membership")
    if payload.name is not None:
        group.name = payload.name.strip()
    if payload.categories is not None:
        group.categories = [category.value for category in payload.categories]
    if payload.max_participants is not None:
        group.max_participants = payload.max_participants
    db.commit()
    return _serialize_group(db, group, user)


@router.post("/{identifier}/invite", response_model=InviteOut)
def rotate_invite(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    rate_limit(db, f"group-invite:{user.id}", 20)
    group = _group(db, identifier, for_update=True)
    _membership(db, group, user)
    _host(group, user)
    if group.status not in {"open", "ready"}:
        raise HTTPException(409, "Invites are closed")
    code = _new_invite(group)
    db.commit()
    return {"join_code": code, "expires_at": group.invite_expires_at.replace(tzinfo=timezone.utc)}


@router.patch("/{identifier}/preferences", response_model=GroupDetailOut)
def update_preferences(identifier: UUID, payload: PreferenceUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    rate_limit(db, f"group-preferences:{user.id}", 60)
    group = _group(db, identifier, for_update=True)
    member = _membership(db, group, user)
    if group.status == "voting" or group.status in {"expired", "cancelled"}:
        raise HTTPException(409, "Preferences are locked")
    member.liked_categories = [category.value for category in payload.liked_categories]
    member.disliked_categories = [category.value for category in payload.disliked_categories]
    member.ready = payload.ready
    _recalculate_ready(db, group)
    db.commit()
    return _serialize_group(db, group, user)


@router.delete("/{identifier}/members/me")
def leave_group(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    group = _group(db, identifier, for_update=True)
    member = _membership(db, group, user)
    if group.status in {"expired", "cancelled"}:
        raise HTTPException(409, "This group is read-only")
    if group.host_id == user.id:
        raise HTTPException(409, "The host must cancel the group")
    candidate_ids = [candidate_id for (candidate_id,) in db.query(GroupCandidate.id).join(GroupMatchRound).filter(GroupMatchRound.group_id == group.id)]
    if candidate_ids:
        db.query(GroupVote).filter(GroupVote.user_id == user.id, GroupVote.candidate_id.in_(candidate_ids)).delete(synchronize_session=False)
    db.delete(member)
    db.flush()
    _recalculate_ready(db, group)
    _complete_if_everyone_voted(db, group, _active_round(db, group))
    db.commit()
    return {"left": True}


@router.delete("/{identifier}/members/{participant_id}", response_model=GroupDetailOut)
def remove_participant(identifier: UUID, participant_id: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    group = _group(db, identifier, for_update=True)
    _membership(db, group, user)
    _host(group, user)
    if group.status in {"expired", "cancelled"}:
        raise HTTPException(409, "This group is read-only")
    if participant_id == group.host_id:
        raise HTTPException(409, "The host cannot be removed")
    member = db.query(GroupParticipant).filter_by(group_id=group.id, user_id=participant_id).first()
    if not member:
        raise HTTPException(404, "Participant not found")
    candidate_ids = [candidate_id for (candidate_id,) in db.query(GroupCandidate.id).join(GroupMatchRound).filter(GroupMatchRound.group_id == group.id)]
    if candidate_ids:
        db.query(GroupVote).filter(GroupVote.user_id == participant_id, GroupVote.candidate_id.in_(candidate_ids)).delete(synchronize_session=False)
    db.delete(member)
    db.flush()
    _recalculate_ready(db, group)
    _complete_if_everyone_voted(db, group, _active_round(db, group))
    db.commit()
    return _serialize_group(db, group, user)


@router.post("/{identifier}/matches", response_model=GroupDetailOut)
def generate_match(identifier: UUID, payload: MatchRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    rate_limit(db, f"group-match:{user.id}", 5)
    group = _group(db, identifier, for_update=True)
    _membership(db, group, user)
    _host(group, user)
    if not EntitlementService(db).has_entitlement(user.id, BACITY_PLUS):
        raise HTTPException(403, "BACity+ required")
    if group.status in {"expired", "cancelled", "voting"}:
        raise HTTPException(409, "This group cannot start a new match")
    members = db.query(GroupParticipant, User).join(User, User.id == GroupParticipant.user_id).filter(
        GroupParticipant.group_id == group.id, User.active.is_(True)
    ).all()
    if len(members) < 2 or not all(member.ready for member, _ in members):
        raise HTTPException(409, "At least two ready participants are required")
    excluded = {blocked_id for _, member_user in members for blocked_id in blocked_ids(db, member_user.id)}
    query = db.query(Event).options(joinedload(Event.venue)).filter(
        Event.status.in_([EventStatus.fresh, EventStatus.stale]),
        Event.start_time >= max(group.starts_at, datetime.utcnow()),
        Event.start_time < group.ends_at,
        or_(Event.end_time.is_(None), Event.end_time <= group.ends_at),
    )
    if excluded:
        query = query.filter(or_(Event.contributor_id.is_(None), ~Event.contributor_id.in_(excluded)))
    events = query.order_by(Event.start_time, Event.id).limit(MAX_DB_CANDIDATES).all()
    participant_preferences = []
    for member, member_user in members:
        context = build_recommendation_context(db, member_user, events, payload.latitude, payload.longitude)
        participant_preferences.append(ParticipantPreference(
            context,
            frozenset(str(value).casefold() for value in (member.liked_categories or [])),
            frozenset(str(value).casefold() for value in (member.disliked_categories or [])),
        ))
    ranked = rank_group_candidates(
        events, tuple(participant_preferences),
        frozenset(str(value).casefold() for value in (group.categories or [])),
        max(group.starts_at, datetime.utcnow()),
    )
    next_number = (db.query(func.max(GroupMatchRound.round_number)).filter_by(group_id=group.id).scalar() or 0) + 1
    round_item = GroupMatchRound(
        group_id=group.id, round_number=next_number,
        status="voting" if ranked else "completed",
        revealed_at=None if ranked else datetime.utcnow(),
    )
    db.add(round_item)
    db.flush()
    for position, item in enumerate(ranked, start=1):
        db.add(GroupCandidate(
            round_id=round_item.id, event_id=item.event.id, position=position,
            match_score=item.score, explanations=list(item.explanations),
        ))
    group.status = "voting" if ranked else "completed"
    group.invite_token_hash = None
    group.invite_expires_at = None
    for _, member_user in members:
        if member_user.id != user.id:
            notify(db, member_user.id, "group", "Your group is ready to vote", group.id)
    db.commit()
    return _serialize_group(db, group, user)


@router.patch("/{identifier}/rounds/{round_id}/vote", response_model=GroupDetailOut)
def cast_vote(identifier: UUID, round_id: UUID, payload: VoteRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    rate_limit(db, f"group-vote:{user.id}", 200)
    group = _group(db, identifier, for_update=True)
    _membership(db, group, user)
    if group.status in {"expired", "cancelled"}:
        raise HTTPException(409, "Voting is closed")
    round_item = db.query(GroupMatchRound).filter_by(id=round_id, group_id=group.id).with_for_update().first()
    if not round_item or round_item.status != "voting":
        raise HTTPException(409, "Voting is closed")
    candidate = db.query(GroupCandidate).filter_by(id=payload.candidate_id, round_id=round_item.id).first()
    if not candidate:
        raise HTTPException(404, "Candidate not found")
    vote = db.query(GroupVote).filter_by(candidate_id=candidate.id, user_id=user.id).first()
    if vote:
        vote.value = payload.value
    else:
        db.add(GroupVote(candidate_id=candidate.id, user_id=user.id, value=payload.value))
    db.flush()
    _complete_if_everyone_voted(db, group, round_item)
    db.commit()
    return _serialize_group(db, group, user)


@router.post("/{identifier}/rounds/{round_id}/reveal", response_model=GroupDetailOut)
def reveal_round(identifier: UUID, round_id: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    group = _group(db, identifier, for_update=True)
    _membership(db, group, user)
    _host(group, user)
    if group.status in {"expired", "cancelled"}:
        raise HTTPException(409, "This group is read-only")
    round_item = db.query(GroupMatchRound).filter_by(id=round_id, group_id=group.id).with_for_update().first()
    if not round_item:
        raise HTTPException(404, "Round not found")
    if round_item.status == "voting":
        round_item.status = "completed"
        round_item.revealed_at = datetime.utcnow()
        group.status = "completed"
        participant_ids = [user_id for (user_id,) in db.query(GroupParticipant.user_id).filter_by(group_id=group.id)]
        for participant_id in participant_ids:
            notify(db, participant_id, "group", "Your group results are ready", group.id)
    db.commit()
    return _serialize_group(db, group, user)


@router.post("/{identifier}/cancel", response_model=GroupDetailOut)
def cancel_group(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    group = _group(db, identifier, for_update=True)
    _membership(db, group, user)
    _host(group, user)
    if group.status in {"expired", "cancelled"}:
        raise HTTPException(409, "This group is read-only")
    group.status = "cancelled"
    group.invite_token_hash = None
    group.invite_expires_at = None
    active = db.query(GroupMatchRound).filter_by(group_id=group.id, status="voting").first()
    if active:
        active.status = "completed"
        active.revealed_at = datetime.utcnow()
    db.commit()
    return _serialize_group(db, group, user)

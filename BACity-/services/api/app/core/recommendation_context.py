"""Database-backed construction of the shared recommendation context."""
from sqlalchemy import and_, func, or_

from app.core.recommendations import RecommendationContext
from app.models.community import Follow, OrganizationMember
from app.models.event import Event
from app.models.saved_event import SavedEvent


def build_recommendation_context(db, user, candidates, latitude=None, longitude=None):
    interests = {item.casefold() for item in user.interests}
    following = {
        (follow.target_type.casefold(), follow.target_id.casefold())
        for follow in db.query(Follow).filter_by(user_id=user.id)
    }
    saved_categories = {
        str(category.value).casefold()
        for (category,) in db.query(Event.category).join(
            SavedEvent, SavedEvent.event_id == Event.id
        ).filter(SavedEvent.user_id == user.id).distinct()
    }
    candidate_ids = [event.id for event in candidates]
    saved_event_ids = frozenset(
        event_id for (event_id,) in db.query(SavedEvent.event_id).filter(
            SavedEvent.user_id == user.id,
            SavedEvent.event_id.in_(candidate_ids),
        )
    ) if candidate_ids else frozenset()
    counts = {}
    if candidate_ids:
        counts = dict(
            db.query(SavedEvent.event_id, func.count(func.distinct(SavedEvent.user_id)))
            .join(Event, Event.id == SavedEvent.event_id)
            .outerjoin(OrganizationMember, and_(
                OrganizationMember.organization_id == Event.organization_id,
                OrganizationMember.user_id == SavedEvent.user_id,
            ))
            .filter(
                SavedEvent.event_id.in_(candidate_ids),
                OrganizationMember.id.is_(None),
                or_(Event.contributor_id.is_(None), Event.contributor_id != SavedEvent.user_id),
            )
            .group_by(SavedEvent.event_id)
            .all()
        )
    return RecommendationContext(
        interests=frozenset(interests),
        saved_categories=frozenset(saved_categories),
        following=frozenset(following),
        save_counts=counts,
        saved_event_ids=saved_event_ids,
        latitude=latitude,
        longitude=longitude,
    )

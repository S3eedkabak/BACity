"""Small shared temporal/geographic primitives for bounded itinerary features."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class PlanningWindow:
    timezone: str
    starts_at_utc: datetime
    ends_at_utc: datetime

    @property
    def duration(self) -> timedelta:
        return self.ends_at_utc - self.starts_at_utc


@dataclass(frozen=True)
class Transition:
    feasible: bool
    required_gap: timedelta
    distance_km: float | None
    location_confidence: str


def utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def local_planning_window(day: date, starts_at: time, ends_at: time, timezone_name: str) -> PlanningWindow:
    if starts_at == ends_at:
        raise ValueError("Start and end time must differ")
    zone = ZoneInfo(timezone_name)
    end_day = day + timedelta(days=1) if ends_at < starts_at else day

    def convert(local_day: date, local_time: time) -> datetime:
        naive = datetime.combine(local_day, local_time.replace(tzinfo=None))
        aware = naive.replace(tzinfo=zone, fold=0)
        utc = aware.astimezone(timezone.utc)
        if utc.astimezone(zone).replace(tzinfo=None) != naive:
            raise ValueError("Selected time does not exist in the local timezone")
        return utc.replace(tzinfo=None)

    return PlanningWindow(timezone_name, convert(day, starts_at), convert(end_day, ends_at))


def event_coordinates(event) -> tuple[float, float] | None:
    if event.latitude is not None and event.longitude is not None:
        return float(event.latitude), float(event.longitude)
    venue = getattr(event, "venue", None)
    if venue and venue.latitude is not None and venue.longitude is not None:
        return float(venue.latitude), float(venue.longitude)
    return None


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Canonical great-circle distance used by location-aware product features."""
    lat1r, lat2r = radians(lat1), radians(lat2)
    delta_lat = lat2r - lat1r
    delta_lng = radians(lng2 - lng1)
    root = sin(delta_lat / 2) ** 2 + cos(lat1r) * cos(lat2r) * sin(delta_lng / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(root))


def distance_km(first, second) -> float | None:
    left, right = event_coordinates(first), event_coordinates(second)
    if left is None or right is None:
        return None
    lat1, lng1 = left
    lat2, lng2 = right
    return haversine_km(lat1, lng1, lat2, lng2)


def required_transition(first, second) -> Transition:
    """Internal conservative buffers; these are never travel-time estimates."""
    distance = distance_km(first, second)
    if distance is None:
        return Transition(True, timedelta(minutes=60), None, "location_unknown")
    if distance <= 1.5:
        return Transition(True, timedelta(minutes=20), distance, "nearby")
    if distance <= 5:
        return Transition(True, timedelta(minutes=35), distance, "nearby")
    if distance <= 10:
        return Transition(True, timedelta(minutes=60), distance, "distance_buffered")
    return Transition(True, timedelta(minutes=90), distance, "distance_buffered")


def valid_event_interval(event) -> bool:
    start = utc_naive(event.start_time)
    return event.end_time is None or utc_naive(event.end_time) > start


def following_transition(first, second) -> Transition | None:
    if not valid_event_interval(first) or not valid_event_interval(second) or first.end_time is None:
        return None
    transition = required_transition(first, second)
    gap = utc_naive(second.start_time) - utc_naive(first.end_time)
    return transition if transition.feasible and gap >= transition.required_gap else None

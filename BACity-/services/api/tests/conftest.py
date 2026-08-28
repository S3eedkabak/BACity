import os
import sys
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base, get_db
from app.models.event import Event, EventCategory
from app.models.venue import Venue
from app.main import app
from fastapi.testclient import TestClient

TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def sample_venue(db_session):
    venue = Venue(
        id=uuid.uuid4(),
        name="Fuga",
        address="Coburgova 84, Bratislava",
        city="Bratislava",
        latitude=48.1425,
        longitude=17.1183,
    )
    db_session.add(venue)
    db_session.commit()
    db_session.refresh(venue)
    return venue


@pytest.fixture
def sample_event(db_session, sample_venue):
    event = Event(
        id=uuid.uuid4(),
        title="Techno Night",
        description="A night of techno at Fuga.",
        start_time=datetime.utcnow() + timedelta(days=1),
        venue_id=sample_venue.id,
        latitude=sample_venue.latitude,
        longitude=sample_venue.longitude,
        category=EventCategory.nightlife,
        tags=["techno", "nightlife"],
        price=10.0,
        currency="EUR",
        source_url="https://example.com/events/techno-night",
        language="en",
        extraction_confidence=0.9,
        source_reliability=0.8,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event

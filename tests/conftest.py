"""Pytest configuration and shared fixtures."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models.domain import WorkItem, Constraint, Commitment, LearningSignal


@pytest.fixture
def db_session():
    """Create a fresh in-memory database for each test."""
    # In-memory SQLite for fast tests
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    TestingSessionLocal = sessionmaker(bind=engine)
    session = TestingSessionLocal()

    yield session

    session.close()


@pytest.fixture
def sample_work_item(db_session):
    """Create a basic work item in Intent state."""
    work_item = WorkItem(
        title="Install formwork",
        description="Install formwork for foundation",
        location="Grid A1-A5",
        owner_user_id="user_123"
    )
    db_session.add(work_item)
    db_session.commit()
    db_session.refresh(work_item)
    return work_item

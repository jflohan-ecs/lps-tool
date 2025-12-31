"""
Internal audit logging model - NOT a user-facing domain object.

This model exists to provide immutable, append-only audit trails
for critical actions and refusals. It is not exposed in user-facing APIs.
"""
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON
from app.database import Base


class AuditEvent(Base):
    """
    Immutable audit event for reconstructing behavioral truth.

    Invariants:
    - Once written, never edited or deleted
    - Append-only
    - Records all critical actions and refusals
    """
    __tablename__ = "audit_events"

    # Required fields per repair constitution
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_type = Column(String, nullable=False, index=True)  # e.g., "commitment_refused_not_ready"
    entity_type = Column(String, nullable=False)  # e.g., "WorkItem", "Commitment"
    entity_id = Column(String, nullable=False, index=True)  # ID of the entity being acted upon
    user_id = Column(String, nullable=True)  # Nullable for system events
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    payload_json = Column(JSON, nullable=True)  # Minimal contextual data


# Event type constants for consistency
class AuditEventType:
    """Enumeration of audit event types."""
    # Constraint lifecycle
    CONSTRAINT_CREATED = "constraint_created"
    CONSTRAINT_CLEARED = "constraint_cleared"
    CONSTRAINT_REOPENED = "constraint_reopened"

    # Commitment lifecycle
    COMMITMENT_CREATED = "commitment_created"
    COMMITMENT_COMPLETED = "commitment_completed"
    COMMITMENT_FAILED = "commitment_failed"

    # Refusal events
    COMMITMENT_REFUSED_NOT_READY = "commitment_refused_not_ready"

    # State transitions (optional but recommended)
    WORK_ITEM_STATE_CHANGED = "work_item_state_changed"

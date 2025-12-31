"""Domain models - the four frozen objects from the constitution."""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.enums import (
    WorkItemState,
    ConstraintStatus,
    CommitmentStatus,
    PrimaryCause,
    ReferencePlanSystem
)


class WorkItem(Base):
    """
    A work item progresses through states: Intent → Not Ready → Ready → Committed → Complete/Failed.

    Invariants enforced here:
    - State is always one of the six allowed states
    - Created with Intent state (handled in service layer)
    """
    __tablename__ = "work_items"

    # Required fields per constitution
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)  # Optional, short
    location = Column(String, nullable=True)  # Optional but recommended
    owner_user_id = Column(String, nullable=False)  # Simple user ID for MVP
    state = Column(SQLEnum(WorkItemState), nullable=False, default=WorkItemState.INTENT)

    # Optional reference to external plan (read-only linkage)
    reference_plan_system = Column(SQLEnum(ReferencePlanSystem), nullable=True)
    reference_plan_external_id = Column(String, nullable=True)
    reference_plan_dates = Column(JSON, nullable=True)  # Display only

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    constraints = relationship("Constraint", back_populates="work_item", cascade="all, delete-orphan")
    commitments = relationship("Commitment", back_populates="work_item", cascade="all, delete-orphan")
    learning_signals = relationship("LearningSignal", back_populates="work_item", cascade="all, delete-orphan")


class Constraint(Base):
    """
    Constraints block readiness. All must be Cleared for a WorkItem to be Ready.

    Invariants:
    - When cleared, cleared_by_user_id and cleared_at must be set
    - Status is binary: Open or Cleared
    """
    __tablename__ = "constraints"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    work_item_id = Column(Integer, ForeignKey("work_items.id"), nullable=False)
    type = Column(String, nullable=False)  # Minimal string enum
    description = Column(String, nullable=True)
    status = Column(SQLEnum(ConstraintStatus), nullable=False, default=ConstraintStatus.OPEN)

    # Required when cleared
    cleared_by_user_id = Column(String, nullable=True)
    cleared_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    work_item = relationship("WorkItem", back_populates="constraints")


class Commitment(Base):
    """
    A Commitment is created from a Ready WorkItem and is immutable.

    Invariants:
    - Only one active commitment per work_item
    - Cannot be edited once created (due_at is immutable in MVP)
    - Late completion (after due_at) counts as Failed
    - Status change must set completed_at or failed_at
    """
    __tablename__ = "commitments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    work_item_id = Column(Integer, ForeignKey("work_items.id"), nullable=False)
    committed_by_user_id = Column(String, nullable=False)
    owner_user_id = Column(String, nullable=False)  # Can equal committed_by_user_id
    due_at = Column(DateTime, nullable=False)  # Immutable in MVP
    status = Column(SQLEnum(CommitmentStatus), nullable=False, default=CommitmentStatus.ACTIVE)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)

    # Relationships
    work_item = relationship("WorkItem", back_populates="commitments")
    learning_signals = relationship("LearningSignal", back_populates="commitment", cascade="all, delete-orphan")


class LearningSignal(Base):
    """
    Automatically created when a Commitment fails.

    Invariants:
    - primary_cause is required
    - Linked to both work_item and commitment
    - drilldown_key is derived for aggregation
    """
    __tablename__ = "learning_signals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    work_item_id = Column(Integer, ForeignKey("work_items.id"), nullable=False)
    commitment_id = Column(Integer, ForeignKey("commitments.id"), nullable=False)

    primary_cause = Column(SQLEnum(PrimaryCause), nullable=False)
    secondary_cause = Column(String, nullable=True)
    notes = Column(String, nullable=True)  # Short, non-blame

    # Derived key for drill-down aggregation
    drilldown_key = Column(String, nullable=False, index=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    work_item = relationship("WorkItem", back_populates="learning_signals")
    commitment = relationship("Commitment", back_populates="learning_signals")

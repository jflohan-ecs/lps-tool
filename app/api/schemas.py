"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.models.enums import (
    WorkItemState,
    ConstraintStatus,
    CommitmentStatus,
    PrimaryCause,
    ReferencePlanSystem
)


# WorkItem schemas
class WorkItemCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = None
    owner_user_id: str
    reference_plan_system: Optional[ReferencePlanSystem] = None
    reference_plan_external_id: Optional[str] = None
    reference_plan_dates: Optional[dict] = None


class WorkItemResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    location: Optional[str]
    owner_user_id: str
    state: WorkItemState
    reference_plan_system: Optional[ReferencePlanSystem]
    reference_plan_external_id: Optional[str]
    reference_plan_dates: Optional[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


# Constraint schemas
class ConstraintCreate(BaseModel):
    type: str = Field(..., min_length=1)
    description: Optional[str] = None


class ConstraintResponse(BaseModel):
    id: int
    work_item_id: int
    type: str
    description: Optional[str]
    status: ConstraintStatus
    cleared_by_user_id: Optional[str]
    cleared_at: Optional[datetime]
    created_at: datetime

    class Config:
        orm_mode = True


class ConstraintClear(BaseModel):
    cleared_by_user_id: str


# Commitment schemas
class CommitmentCreate(BaseModel):
    committed_by_user_id: str
    owner_user_id: str
    due_at: datetime


class CommitmentResponse(BaseModel):
    id: int
    work_item_id: int
    committed_by_user_id: str
    owner_user_id: str
    due_at: datetime
    status: CommitmentStatus
    created_at: datetime
    completed_at: Optional[datetime]
    failed_at: Optional[datetime]

    class Config:
        orm_mode = True


class CommitmentFail(BaseModel):
    primary_cause: PrimaryCause
    secondary_cause: Optional[str] = None
    notes: Optional[str] = Field(None, max_length=500)


# Learning Signal schemas
class LearningSignalResponse(BaseModel):
    id: int
    work_item_id: int
    commitment_id: int
    primary_cause: PrimaryCause
    secondary_cause: Optional[str]
    notes: Optional[str]
    drilldown_key: str
    created_at: datetime

    class Config:
        orm_mode = True


class DrilldownItem(BaseModel):
    """Aggregated learning signals by drilldown key."""
    primary_cause: str
    location: str
    reference_system: str
    count: int
    latest_occurrence: datetime


# Error response
class RefusalResponse(BaseModel):
    """Response when an action is refused."""
    message: str
    open_constraints: List[str] = []

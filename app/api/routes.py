"""API routes for the LPS spine workflow."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from app.database import get_db
from app.models.domain import WorkItem, Constraint, Commitment, LearningSignal
from app.models.enums import WorkItemState
from app.services.state_machine import StateMachine, RefusalError
from app.api.schemas import (
    WorkItemCreate,
    WorkItemResponse,
    ConstraintCreate,
    ConstraintResponse,
    ConstraintClear,
    CommitmentCreate,
    CommitmentResponse,
    CommitmentFail,
    LearningSignalResponse,
    DrilldownItem,
    RefusalResponse
)

router = APIRouter()


# WorkItem endpoints
@router.post("/work-items", response_model=WorkItemResponse, status_code=status.HTTP_201_CREATED)
def create_work_item(work_item_data: WorkItemCreate, db: Session = Depends(get_db)):
    """Create a new work item in Intent state."""
    work_item = WorkItem(
        title=work_item_data.title,
        description=work_item_data.description,
        location=work_item_data.location,
        owner_user_id=work_item_data.owner_user_id,
        state=WorkItemState.INTENT,
        reference_plan_system=work_item_data.reference_plan_system,
        reference_plan_external_id=work_item_data.reference_plan_external_id,
        reference_plan_dates=work_item_data.reference_plan_dates
    )
    db.add(work_item)
    db.commit()
    db.refresh(work_item)
    return work_item


@router.get("/work-items", response_model=List[WorkItemResponse])
def list_work_items(db: Session = Depends(get_db)):
    """List all work items."""
    return db.query(WorkItem).order_by(WorkItem.created_at.desc()).all()


@router.get("/work-items/{work_item_id}", response_model=WorkItemResponse)
def get_work_item(work_item_id: int, db: Session = Depends(get_db)):
    """Get a specific work item."""
    work_item = db.query(WorkItem).filter(WorkItem.id == work_item_id).first()
    if not work_item:
        raise HTTPException(status_code=404, detail="Work item not found")
    return work_item


# Constraint endpoints
@router.post("/work-items/{work_item_id}/constraints", response_model=ConstraintResponse, status_code=status.HTTP_201_CREATED)
def add_constraint(work_item_id: int, constraint_data: ConstraintCreate, db: Session = Depends(get_db)):
    """
    Add a constraint to a work item.
    Side effect: If work item is Ready, this will return it to Not Ready.
    """
    work_item = db.query(WorkItem).filter(WorkItem.id == work_item_id).first()
    if not work_item:
        raise HTTPException(status_code=404, detail="Work item not found")

    sm = StateMachine(db)
    constraint = sm.add_constraint(
        work_item,
        constraint_type=constraint_data.type,
        description=constraint_data.description
    )
    return constraint


@router.get("/work-items/{work_item_id}/constraints", response_model=List[ConstraintResponse])
def list_constraints(work_item_id: int, db: Session = Depends(get_db)):
    """List all constraints for a work item."""
    work_item = db.query(WorkItem).filter(WorkItem.id == work_item_id).first()
    if not work_item:
        raise HTTPException(status_code=404, detail="Work item not found")
    return work_item.constraints


@router.put("/constraints/{constraint_id}/clear", response_model=ConstraintResponse)
def clear_constraint(constraint_id: int, clear_data: ConstraintClear, db: Session = Depends(get_db)):
    """
    Clear a constraint.
    Side effect: May change work item from Not Ready to Ready.
    """
    constraint = db.query(Constraint).filter(Constraint.id == constraint_id).first()
    if not constraint:
        raise HTTPException(status_code=404, detail="Constraint not found")

    sm = StateMachine(db)
    sm.clear_constraint(constraint, clear_data.cleared_by_user_id)
    db.refresh(constraint)
    return constraint


@router.put("/constraints/{constraint_id}/reopen", response_model=ConstraintResponse)
def reopen_constraint(constraint_id: int, db: Session = Depends(get_db)):
    """
    Reopen a cleared constraint.
    Side effect: Will change work item from Ready to Not Ready.
    """
    constraint = db.query(Constraint).filter(Constraint.id == constraint_id).first()
    if not constraint:
        raise HTTPException(status_code=404, detail="Constraint not found")

    sm = StateMachine(db)
    sm.reopen_constraint(constraint)
    db.refresh(constraint)
    return constraint


# Commitment endpoints
@router.post("/work-items/{work_item_id}/commit", response_model=CommitmentResponse, status_code=status.HTTP_201_CREATED, responses={
    403: {"model": RefusalResponse, "description": "Refusal - work not ready or already committed"}
})
def create_commitment(work_item_id: int, commitment_data: CommitmentCreate, db: Session = Depends(get_db)):
    """
    Create a commitment for a Ready work item.

    WILL REFUSE if:
    - Work item is not Ready
    - Work item has no constraints
    - Work item already has an active commitment
    """
    work_item = db.query(WorkItem).filter(WorkItem.id == work_item_id).first()
    if not work_item:
        raise HTTPException(status_code=404, detail="Work item not found")

    sm = StateMachine(db)
    try:
        commitment = sm.create_commitment(
            work_item,
            committed_by_user_id=commitment_data.committed_by_user_id,
            owner_user_id=commitment_data.owner_user_id,
            due_at=commitment_data.due_at
        )
        return commitment
    except RefusalError as e:
        # Return refusal as HTTP 403 Forbidden with details
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": e.message,
                "open_constraints": e.open_constraints
            }
        )


@router.get("/work-items/{work_item_id}/commitments", response_model=List[CommitmentResponse])
def list_commitments(work_item_id: int, db: Session = Depends(get_db)):
    """List all commitments for a work item."""
    work_item = db.query(WorkItem).filter(WorkItem.id == work_item_id).first()
    if not work_item:
        raise HTTPException(status_code=404, detail="Work item not found")
    return work_item.commitments


@router.put("/commitments/{commitment_id}/complete", response_model=CommitmentResponse)
def complete_commitment(commitment_id: int, db: Session = Depends(get_db)):
    """
    Mark a commitment as complete.
    If completed after due_at, will be marked as Failed instead.
    """
    commitment = db.query(Commitment).filter(Commitment.id == commitment_id).first()
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")

    sm = StateMachine(db)
    sm.complete_commitment(commitment)
    db.refresh(commitment)
    return commitment


@router.put("/commitments/{commitment_id}/fail", response_model=LearningSignalResponse)
def fail_commitment(commitment_id: int, fail_data: CommitmentFail, db: Session = Depends(get_db)):
    """
    Mark a commitment as failed and generate a Learning Signal.
    Primary cause is required - failure cannot be recorded without classification.
    """
    commitment = db.query(Commitment).filter(Commitment.id == commitment_id).first()
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")

    sm = StateMachine(db)
    learning_signal = sm.fail_commitment(
        commitment,
        primary_cause=fail_data.primary_cause,
        secondary_cause=fail_data.secondary_cause,
        notes=fail_data.notes
    )
    return learning_signal


# Learning Signal endpoints
@router.get("/learning-signals", response_model=List[LearningSignalResponse])
def list_learning_signals(db: Session = Depends(get_db)):
    """List all learning signals."""
    return db.query(LearningSignal).order_by(LearningSignal.created_at.desc()).all()


@router.get("/learning-signals/drilldown", response_model=List[DrilldownItem])
def get_drilldown(db: Session = Depends(get_db)):
    """
    Aggregate learning signals by primary cause, location, and reference system.
    Simple, deterministic aggregation with no predictions.
    """
    from sqlalchemy import func

    # Query aggregated by drilldown_key
    results = db.query(
        LearningSignal.drilldown_key,
        func.count(LearningSignal.id).label('count'),
        func.max(LearningSignal.created_at).label('latest')
    ).group_by(
        LearningSignal.drilldown_key
    ).order_by(
        func.count(LearningSignal.id).desc()
    ).all()

    # Parse drilldown keys back into components
    drilldown_items = []
    for key, count, latest in results:
        parts = key.split('|')
        drilldown_items.append(DrilldownItem(
            primary_cause=parts[0],
            location=parts[1] if parts[1] != "no_location" else "Not specified",
            reference_system=parts[2] if parts[2] != "no_reference" else "Not specified",
            count=count,
            latest_occurrence=latest
        ))

    return drilldown_items


@router.post("/work-items/{work_item_id}/reset", response_model=WorkItemResponse)
def reset_to_intent(work_item_id: int, db: Session = Depends(get_db)):
    """Reset a Failed or Complete work item back to Intent for a new cycle."""
    work_item = db.query(WorkItem).filter(WorkItem.id == work_item_id).first()
    if not work_item:
        raise HTTPException(status_code=404, detail="Work item not found")

    sm = StateMachine(db)
    try:
        sm.reset_to_intent(work_item)
        db.refresh(work_item)
        return work_item
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

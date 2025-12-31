"""
State machine that enforces the LPS constitution invariants.

This is the core enforcement mechanism - all state transitions MUST go through here.
"""
from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from app.models.domain import WorkItem, Constraint, Commitment, LearningSignal
from app.models.enums import (
    WorkItemState,
    ConstraintStatus,
    CommitmentStatus,
    PrimaryCause
)


class RefusalError(Exception):
    """
    Raised when an action is refused by the system.
    This is NOT an error - it's the system working correctly.
    """
    def __init__(self, message: str, open_constraints: List[str] = None):
        self.message = message
        self.open_constraints = open_constraints or []
        super().__init__(self.message)


class StateMachine:
    """Enforces state transition invariants and business rules."""

    def __init__(self, db: Session):
        self.db = db

    def calculate_readiness(self, work_item: WorkItem) -> WorkItemState:
        """
        Calculate whether a work item is Ready or Not Ready.

        Readiness invariants:
        - Readiness is binary: Ready or Not Ready
        - Ready requires at least one Constraint, and all Constraints must be Cleared
        - If constraints are empty, the item must be Not Ready
        - If any constraint is Open, the item must be Not Ready
        """
        constraints = work_item.constraints

        # Empty constraints = Not Ready (explicit requirement)
        if not constraints:
            return WorkItemState.NOT_READY

        # Any Open constraint = Not Ready
        for constraint in constraints:
            if constraint.status == ConstraintStatus.OPEN:
                return WorkItemState.NOT_READY

        # At least one constraint exists and all are Cleared = Ready
        return WorkItemState.READY

    def update_work_item_state(self, work_item: WorkItem) -> None:
        """
        Update work item state based on current constraints.
        Only affects Intent/Not Ready/Ready states.
        """
        # Don't change state if already Committed, Complete, or Failed
        if work_item.state in [
            WorkItemState.COMMITTED,
            WorkItemState.COMPLETE,
            WorkItemState.FAILED
        ]:
            return

        # Calculate new state
        new_state = self.calculate_readiness(work_item)

        # Update if changed
        if work_item.state != new_state:
            work_item.state = new_state
            work_item.updated_at = datetime.utcnow()
            self.db.commit()

    def add_constraint(
        self,
        work_item: WorkItem,
        constraint_type: str,
        description: Optional[str] = None
    ) -> Constraint:
        """
        Add a constraint to a work item.

        Side effect: If work item is Ready, adding an Open constraint returns it to Not Ready.
        """
        constraint = Constraint(
            work_item_id=work_item.id,
            type=constraint_type,
            description=description,
            status=ConstraintStatus.OPEN
        )
        self.db.add(constraint)
        self.db.commit()
        self.db.refresh(constraint)

        # Recalculate readiness (adding Open constraint may change Ready → Not Ready)
        self.update_work_item_state(work_item)

        return constraint

    def clear_constraint(
        self,
        constraint: Constraint,
        cleared_by_user_id: str
    ) -> None:
        """
        Clear a constraint.

        Invariants:
        - When cleared, cleared_by_user_id and cleared_at must be set
        """
        constraint.status = ConstraintStatus.CLEARED
        constraint.cleared_by_user_id = cleared_by_user_id
        constraint.cleared_at = datetime.utcnow()
        self.db.commit()

        # Recalculate readiness (clearing may change Not Ready → Ready)
        work_item = constraint.work_item
        self.update_work_item_state(work_item)

    def reopen_constraint(self, constraint: Constraint) -> None:
        """
        Reopen a cleared constraint.

        Side effect: Will change Ready → Not Ready.
        """
        constraint.status = ConstraintStatus.OPEN
        constraint.cleared_by_user_id = None
        constraint.cleared_at = None
        self.db.commit()

        # Recalculate readiness (reopening changes Ready → Not Ready)
        work_item = constraint.work_item
        self.update_work_item_state(work_item)

    def create_commitment(
        self,
        work_item: WorkItem,
        committed_by_user_id: str,
        owner_user_id: str,
        due_at: datetime
    ) -> Commitment:
        """
        Create a commitment from a Ready work item.

        Refusal invariants:
        - The commit action must be blocked server-side (not merely warned)
        - The refusal message must explicitly cite the Open constraints
        - There must be no alternative path to create a commitment

        Commitment invariants:
        - A Commitment can only be created from a Ready WorkItem
        - A WorkItem can have at most one active Commitment at a time
        """
        # Check for existing active commitment FIRST (more specific error)
        active_commitment = self.db.query(Commitment).filter(
            Commitment.work_item_id == work_item.id,
            Commitment.status == CommitmentStatus.ACTIVE
        ).first()

        if active_commitment:
            raise RefusalError(
                "REFUSAL: This work item already has an active commitment. "
                "Complete or fail the existing commitment first."
            )

        # HARD REFUSAL: Cannot commit if Not Ready
        if work_item.state != WorkItemState.READY:
            open_constraints = [
                f"{c.type}: {c.description or '(no description)'}"
                for c in work_item.constraints
                if c.status == ConstraintStatus.OPEN
            ]

            if not work_item.constraints:
                raise RefusalError(
                    "REFUSAL: Cannot commit work with no constraints. "
                    "Add at least one constraint and clear it to demonstrate readiness.",
                    open_constraints=[]
                )
            else:
                raise RefusalError(
                    f"REFUSAL: Cannot commit Not Ready work. "
                    f"The following constraints are still Open: {', '.join(open_constraints)}",
                    open_constraints=open_constraints
                )

        # Create the commitment
        commitment = Commitment(
            work_item_id=work_item.id,
            committed_by_user_id=committed_by_user_id,
            owner_user_id=owner_user_id,
            due_at=due_at,
            status=CommitmentStatus.ACTIVE
        )
        self.db.add(commitment)

        # Update work item state to Committed
        work_item.state = WorkItemState.COMMITTED
        work_item.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(commitment)

        return commitment

    def complete_commitment(
        self,
        commitment: Commitment
    ) -> None:
        """
        Mark a commitment as complete.

        Invariant: Late completion (after due_at) counts as Failed, not Complete.
        """
        now = datetime.utcnow()

        # Late completion = failure
        if now > commitment.due_at:
            # This is actually a failure, redirect to fail_commitment
            self.fail_commitment(
                commitment,
                primary_cause=PrimaryCause.OTHER,
                notes="Auto-failed: Completed after due date"
            )
            return

        # On-time completion
        commitment.status = CommitmentStatus.COMPLETE
        commitment.completed_at = now
        commitment.work_item.state = WorkItemState.COMPLETE
        commitment.work_item.updated_at = now

        self.db.commit()

    def fail_commitment(
        self,
        commitment: Commitment,
        primary_cause: PrimaryCause,
        secondary_cause: Optional[str] = None,
        notes: Optional[str] = None
    ) -> LearningSignal:
        """
        Mark a commitment as failed and generate a Learning Signal.

        Failure and learning invariants:
        - Every failed commitment must generate a LearningSignal automatically
        - Failure cannot be recorded without primary cause classification
        - LearningSignal is first-class and must be visible
        """
        now = datetime.utcnow()

        # Update commitment status
        commitment.status = CommitmentStatus.FAILED
        commitment.failed_at = now

        # Update work item state
        commitment.work_item.state = WorkItemState.FAILED
        commitment.work_item.updated_at = now

        # Generate drilldown key (deterministic aggregation key)
        drilldown_key = self._generate_drilldown_key(
            primary_cause=primary_cause.value,
            location=commitment.work_item.location,
            reference_system=commitment.work_item.reference_plan_system
        )

        # MANDATORY: Create Learning Signal
        learning_signal = LearningSignal(
            work_item_id=commitment.work_item.id,
            commitment_id=commitment.id,
            primary_cause=primary_cause,
            secondary_cause=secondary_cause,
            notes=notes,
            drilldown_key=drilldown_key
        )
        self.db.add(learning_signal)
        self.db.commit()
        self.db.refresh(learning_signal)

        return learning_signal

    def reset_to_intent(self, work_item: WorkItem) -> None:
        """
        Reset a Failed or Complete work item back to Intent.

        This creates a new Intent cycle - not a "reopen".
        """
        if work_item.state not in [WorkItemState.FAILED, WorkItemState.COMPLETE]:
            raise ValueError(
                f"Can only reset Failed or Complete work items. Current state: {work_item.state}"
            )

        work_item.state = WorkItemState.INTENT
        work_item.updated_at = datetime.utcnow()
        self.db.commit()

    def _generate_drilldown_key(
        self,
        primary_cause: str,
        location: Optional[str],
        reference_system: Optional[str]
    ) -> str:
        """
        Generate deterministic key for drill-down aggregation.

        Format: primary_cause|location|reference_system
        """
        parts = [
            primary_cause,
            location or "no_location",
            reference_system or "no_reference"
        ]
        return "|".join(parts)

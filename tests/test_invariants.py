"""
Tests that prove the constitution invariants.

Each test verifies a specific invariant from the constitution.
"""
import pytest
from datetime import datetime, timedelta
from app.services.state_machine import StateMachine, RefusalError
from app.models.enums import WorkItemState, ConstraintStatus, PrimaryCause


class TestReadinessInvariants:
    """Test readiness calculation invariants."""

    def test_empty_constraints_means_not_ready(self, db_session, sample_work_item):
        """
        INVARIANT: If constraints are empty, the item must be Not Ready.
        """
        sm = StateMachine(db_session)

        # Work item with no constraints
        assert len(sample_work_item.constraints) == 0

        # Calculate readiness
        state = sm.calculate_readiness(sample_work_item)

        # Must be Not Ready
        assert state == WorkItemState.NOT_READY

    def test_ready_requires_at_least_one_constraint_all_cleared(self, db_session, sample_work_item):
        """
        INVARIANT: Ready requires at least one Constraint, and all Constraints must be Cleared.
        """
        sm = StateMachine(db_session)

        # Add one constraint
        constraint = sm.add_constraint(sample_work_item, "Materials", "Concrete delivered")
        db_session.refresh(sample_work_item)

        # Not ready yet (constraint is Open)
        assert sm.calculate_readiness(sample_work_item) == WorkItemState.NOT_READY

        # Clear the constraint
        sm.clear_constraint(constraint, "user_123")
        db_session.refresh(sample_work_item)

        # Now it's Ready
        assert sm.calculate_readiness(sample_work_item) == WorkItemState.READY

    def test_any_open_constraint_means_not_ready(self, db_session, sample_work_item):
        """
        INVARIANT: If any constraint is Open, the item must be Not Ready.
        """
        sm = StateMachine(db_session)

        # Add two constraints
        c1 = sm.add_constraint(sample_work_item, "Materials", "Concrete")
        c2 = sm.add_constraint(sample_work_item, "Access", "Site access")

        # Clear first one
        sm.clear_constraint(c1, "user_123")
        db_session.refresh(sample_work_item)

        # Still Not Ready (c2 is Open)
        assert sm.calculate_readiness(sample_work_item) == WorkItemState.NOT_READY

        # Clear second one
        sm.clear_constraint(c2, "user_123")
        db_session.refresh(sample_work_item)

        # Now Ready
        assert sm.calculate_readiness(sample_work_item) == WorkItemState.READY

    def test_adding_open_constraint_to_ready_item_returns_to_not_ready(self, db_session, sample_work_item):
        """
        INVARIANT: Adding an Open constraint to a Ready item returns it to Not Ready.
        """
        sm = StateMachine(db_session)

        # Make it Ready first
        c1 = sm.add_constraint(sample_work_item, "Materials", "Concrete")
        sm.clear_constraint(c1, "user_123")
        db_session.refresh(sample_work_item)
        assert sample_work_item.state == WorkItemState.READY

        # Add another constraint (Open by default)
        sm.add_constraint(sample_work_item, "Access", "New issue found")
        db_session.refresh(sample_work_item)

        # Must return to Not Ready
        assert sample_work_item.state == WorkItemState.NOT_READY


class TestRefusalInvariants:
    """Test that refusals work correctly and cite constraints."""

    def test_cannot_commit_when_not_ready_server_side(self, db_session, sample_work_item):
        """
        INVARIANT: Cannot commit when Not Ready (server-side enforcement).
        """
        sm = StateMachine(db_session)

        # Try to commit when Not Ready (no constraints)
        with pytest.raises(RefusalError) as exc_info:
            sm.create_commitment(
                sample_work_item,
                committed_by_user_id="user_123",
                owner_user_id="user_123",
                due_at=datetime.utcnow() + timedelta(days=1)
            )

        # Verify refusal message mentions constraints
        assert "REFUSAL" in str(exc_info.value)
        assert "no constraints" in str(exc_info.value).lower()

    def test_refusal_cites_open_constraints(self, db_session, sample_work_item):
        """
        INVARIANT: The refusal message must explicitly cite the Open constraints.
        """
        sm = StateMachine(db_session)

        # Add some constraints but don't clear them
        sm.add_constraint(sample_work_item, "Materials", "Concrete not delivered")
        sm.add_constraint(sample_work_item, "Access", "Road blocked")
        db_session.refresh(sample_work_item)

        # Try to commit
        with pytest.raises(RefusalError) as exc_info:
            sm.create_commitment(
                sample_work_item,
                committed_by_user_id="user_123",
                owner_user_id="user_123",
                due_at=datetime.utcnow() + timedelta(days=1)
            )

        # Verify both constraints are cited
        error_message = str(exc_info.value)
        assert "Materials" in error_message
        assert "Access" in error_message

    def test_cannot_commit_intent_state(self, db_session, sample_work_item):
        """
        FORBIDDEN TRANSITION: Intent → Committed is not allowed.
        """
        sm = StateMachine(db_session)

        # Work item is in Intent state
        assert sample_work_item.state == WorkItemState.INTENT

        # Try to commit from Intent (even via API call)
        with pytest.raises(RefusalError):
            sm.create_commitment(
                sample_work_item,
                committed_by_user_id="user_123",
                owner_user_id="user_123",
                due_at=datetime.utcnow() + timedelta(days=1)
            )


class TestCommitmentInvariants:
    """Test commitment-related invariants."""

    def test_only_one_active_commitment_per_work_item(self, db_session, sample_work_item):
        """
        INVARIANT: A WorkItem can have at most one active Commitment at a time.
        """
        sm = StateMachine(db_session)

        # Make Ready
        c = sm.add_constraint(sample_work_item, "Materials", "Ready to go")
        sm.clear_constraint(c, "user_123")
        db_session.refresh(sample_work_item)

        # Create first commitment
        commitment1 = sm.create_commitment(
            sample_work_item,
            committed_by_user_id="user_123",
            owner_user_id="user_123",
            due_at=datetime.utcnow() + timedelta(days=1)
        )
        db_session.refresh(sample_work_item)

        # Try to create second commitment (should be refused)
        with pytest.raises(RefusalError) as exc_info:
            sm.create_commitment(
                sample_work_item,
                committed_by_user_id="user_456",
                owner_user_id="user_456",
                due_at=datetime.utcnow() + timedelta(days=2)
            )

        assert "already has an active commitment" in str(exc_info.value).lower()

    def test_late_completion_becomes_failure(self, db_session, sample_work_item):
        """
        INVARIANT: Late completion (after due_at) counts as Failed, not Complete.
        """
        sm = StateMachine(db_session)

        # Make Ready and commit
        c = sm.add_constraint(sample_work_item, "Materials", "Ready")
        sm.clear_constraint(c, "user_123")
        db_session.refresh(sample_work_item)

        # Commit with a due date in the past
        past_due = datetime.utcnow() - timedelta(days=1)
        commitment = sm.create_commitment(
            sample_work_item,
            committed_by_user_id="user_123",
            owner_user_id="user_123",
            due_at=past_due
        )
        db_session.refresh(commitment)

        # Try to complete it (now is after due_at)
        sm.complete_commitment(commitment)
        db_session.refresh(commitment)
        db_session.refresh(sample_work_item)

        # Should be Failed, not Complete
        assert commitment.status.value == "Failed"
        assert sample_work_item.state == WorkItemState.FAILED
        assert commitment.failed_at is not None


class TestLearningSignalInvariants:
    """Test that learning signals are generated correctly."""

    def test_every_failure_produces_learning_signal(self, db_session, sample_work_item):
        """
        INVARIANT: Every failed commitment must generate a LearningSignal automatically.
        """
        sm = StateMachine(db_session)

        # Make Ready and commit
        c = sm.add_constraint(sample_work_item, "Materials", "Ready")
        sm.clear_constraint(c, "user_123")
        db_session.refresh(sample_work_item)

        commitment = sm.create_commitment(
            sample_work_item,
            committed_by_user_id="user_123",
            owner_user_id="user_123",
            due_at=datetime.utcnow() + timedelta(days=1)
        )

        # Fail the commitment
        learning_signal = sm.fail_commitment(
            commitment,
            primary_cause=PrimaryCause.MATERIALS,
            notes="Concrete truck broke down"
        )
        db_session.refresh(sample_work_item)

        # Verify learning signal was created
        assert learning_signal is not None
        assert learning_signal.primary_cause == PrimaryCause.MATERIALS
        assert learning_signal.work_item_id == sample_work_item.id
        assert learning_signal.commitment_id == commitment.id

        # Verify drilldown key was generated
        assert learning_signal.drilldown_key is not None
        assert "Materials" in learning_signal.drilldown_key

    def test_failure_requires_primary_cause(self, db_session, sample_work_item):
        """
        INVARIANT: Failure cannot be recorded without primary cause classification.
        """
        sm = StateMachine(db_session)

        # Make Ready and commit
        c = sm.add_constraint(sample_work_item, "Materials", "Ready")
        sm.clear_constraint(c, "user_123")
        db_session.refresh(sample_work_item)

        commitment = sm.create_commitment(
            sample_work_item,
            committed_by_user_id="user_123",
            owner_user_id="user_123",
            due_at=datetime.utcnow() + timedelta(days=1)
        )

        # fail_commitment REQUIRES primary_cause parameter
        # This test verifies it's a required parameter (Python will error if missing)
        # We can verify by trying without it:
        with pytest.raises(TypeError):
            sm.fail_commitment(commitment)  # Missing required primary_cause


class TestReferencePlanInvariants:
    """Test that reference plans don't affect readiness."""

    def test_reference_plan_does_not_affect_readiness(self, db_session):
        """
        INVARIANT: Reference plan link does not affect readiness/commitment.
        """
        from app.models.domain import WorkItem
        from app.models.enums import ReferencePlanSystem

        # Create work item with reference plan
        work_item = WorkItem(
            title="Foundation pour",
            owner_user_id="user_123",
            reference_plan_system=ReferencePlanSystem.MSP,
            reference_plan_external_id="TASK-12345",
            reference_plan_dates={"start": "2025-01-15", "finish": "2025-01-20"}
        )
        db_session.add(work_item)
        db_session.commit()
        db_session.refresh(work_item)

        sm = StateMachine(db_session)

        # Readiness still requires constraints, reference plan is ignored
        assert sm.calculate_readiness(work_item) == WorkItemState.NOT_READY

        # Add and clear constraint
        c = sm.add_constraint(work_item, "Materials", "Ready")
        sm.clear_constraint(c, "user_123")
        db_session.refresh(work_item)

        # Now Ready (reference plan didn't interfere)
        assert work_item.state == WorkItemState.READY


class TestStateTransitions:
    """Test allowed and forbidden state transitions."""

    def test_complete_work_item_full_spine(self, db_session, sample_work_item):
        """
        Test the full happy path spine:
        Intent → Not Ready → Ready → Committed → Complete
        """
        sm = StateMachine(db_session)

        # 1. Starts as Intent
        assert sample_work_item.state == WorkItemState.INTENT

        # 2. Add constraint → becomes Not Ready
        c = sm.add_constraint(sample_work_item, "Materials", "Concrete needed")
        db_session.refresh(sample_work_item)
        assert sample_work_item.state == WorkItemState.NOT_READY

        # 3. Clear constraint → becomes Ready
        sm.clear_constraint(c, "user_123")
        db_session.refresh(sample_work_item)
        assert sample_work_item.state == WorkItemState.READY

        # 4. Create commitment → becomes Committed
        due_date = datetime.utcnow() + timedelta(days=2)
        commitment = sm.create_commitment(
            sample_work_item,
            committed_by_user_id="user_123",
            owner_user_id="user_123",
            due_at=due_date
        )
        db_session.refresh(sample_work_item)
        assert sample_work_item.state == WorkItemState.COMMITTED

        # 5. Complete on time → becomes Complete
        sm.complete_commitment(commitment)
        db_session.refresh(sample_work_item)
        assert sample_work_item.state == WorkItemState.COMPLETE

    def test_failed_work_item_full_spine(self, db_session, sample_work_item):
        """
        Test the failure path:
        Intent → Not Ready → Ready → Committed → Failed → Learning Signal
        """
        sm = StateMachine(db_session)

        # Get to Committed
        c = sm.add_constraint(sample_work_item, "Materials", "Ready")
        sm.clear_constraint(c, "user_123")
        db_session.refresh(sample_work_item)

        commitment = sm.create_commitment(
            sample_work_item,
            committed_by_user_id="user_123",
            owner_user_id="user_123",
            due_at=datetime.utcnow() + timedelta(days=1)
        )

        # Fail it
        learning_signal = sm.fail_commitment(
            commitment,
            primary_cause=PrimaryCause.WEATHER,
            notes="Unexpected rain"
        )
        db_session.refresh(sample_work_item)

        # Verify Failed state and learning signal
        assert sample_work_item.state == WorkItemState.FAILED
        assert learning_signal.primary_cause == PrimaryCause.WEATHER
        assert len(sample_work_item.learning_signals) == 1

    def test_reset_to_intent_from_failed(self, db_session, sample_work_item):
        """
        Test: Failed → Intent (reset for new cycle).
        """
        sm = StateMachine(db_session)

        # Get to Failed state
        c = sm.add_constraint(sample_work_item, "Materials", "Ready")
        sm.clear_constraint(c, "user_123")
        commitment = sm.create_commitment(
            sample_work_item,
            committed_by_user_id="user_123",
            owner_user_id="user_123",
            due_at=datetime.utcnow() + timedelta(days=1)
        )
        sm.fail_commitment(commitment, primary_cause=PrimaryCause.OTHER)
        db_session.refresh(sample_work_item)
        assert sample_work_item.state == WorkItemState.FAILED

        # Reset to Intent
        sm.reset_to_intent(sample_work_item)
        db_session.refresh(sample_work_item)
        assert sample_work_item.state == WorkItemState.INTENT

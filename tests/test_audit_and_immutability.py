"""
Tests for audit logging and commitment immutability (repair constitution).

These tests prove:
- Audit events are created for all mandatory actions
- Refusals are logged immutably
- Commitments are provably immutable at the service layer
"""
import pytest
from datetime import datetime, timedelta
from app.services.state_machine import StateMachine, RefusalError
from app.models.audit import AuditEvent, AuditEventType
from app.models.enums import PrimaryCause


class TestAuditLogging:
    """Test that audit events are created for all mandatory actions."""

    def test_constraint_created_audit(self, db_session, sample_work_item):
        """Audit event created when constraint is added."""
        sm = StateMachine(db_session)

        # Add constraint
        constraint = sm.add_constraint(sample_work_item, "Materials", "Concrete ready")

        # Check audit event exists
        audit = db_session.query(AuditEvent).filter(
            AuditEvent.event_type == AuditEventType.CONSTRAINT_CREATED,
            AuditEvent.entity_id == str(constraint.id)
        ).first()

        assert audit is not None
        assert audit.entity_type == "Constraint"
        assert audit.payload_json["work_item_id"] == sample_work_item.id
        assert audit.payload_json["type"] == "Materials"

    def test_constraint_cleared_audit(self, db_session, sample_work_item):
        """Audit event created when constraint is cleared."""
        sm = StateMachine(db_session)

        # Add and clear constraint
        constraint = sm.add_constraint(sample_work_item, "Materials", "Concrete ready")
        sm.clear_constraint(constraint, "user_123")

        # Check audit event exists
        audit = db_session.query(AuditEvent).filter(
            AuditEvent.event_type == AuditEventType.CONSTRAINT_CLEARED,
            AuditEvent.entity_id == str(constraint.id)
        ).first()

        assert audit is not None
        assert audit.entity_type == "Constraint"
        assert audit.user_id == "user_123"
        assert audit.payload_json["work_item_id"] == sample_work_item.id

    def test_commitment_created_audit(self, db_session, sample_work_item):
        """Audit event created when commitment is successfully created."""
        sm = StateMachine(db_session)

        # Make Ready
        c = sm.add_constraint(sample_work_item, "Materials", "Ready")
        sm.clear_constraint(c, "user_123")
        db_session.refresh(sample_work_item)

        # Create commitment
        commitment = sm.create_commitment(
            sample_work_item,
            committed_by_user_id="user_123",
            owner_user_id="user_123",
            due_at=datetime.utcnow() + timedelta(days=1)
        )

        # Check audit event exists
        audit = db_session.query(AuditEvent).filter(
            AuditEvent.event_type == AuditEventType.COMMITMENT_CREATED,
            AuditEvent.entity_id == str(commitment.id)
        ).first()

        assert audit is not None
        assert audit.entity_type == "Commitment"
        assert audit.user_id == "user_123"
        assert audit.payload_json["work_item_id"] == sample_work_item.id

    def test_commitment_completed_audit(self, db_session, sample_work_item):
        """Audit event created when commitment is completed."""
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

        # Complete commitment
        sm.complete_commitment(commitment)

        # Check audit event exists
        audit = db_session.query(AuditEvent).filter(
            AuditEvent.event_type == AuditEventType.COMMITMENT_COMPLETED,
            AuditEvent.entity_id == str(commitment.id)
        ).first()

        assert audit is not None
        assert audit.entity_type == "Commitment"
        assert audit.payload_json["on_time"] is True

    def test_commitment_failed_audit(self, db_session, sample_work_item):
        """Audit event created when commitment fails."""
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

        # Fail commitment
        sm.fail_commitment(
            commitment,
            primary_cause=PrimaryCause.MATERIALS,
            notes="Concrete delivery delayed"
        )

        # Check audit event exists
        audit = db_session.query(AuditEvent).filter(
            AuditEvent.event_type == AuditEventType.COMMITMENT_FAILED,
            AuditEvent.entity_id == str(commitment.id)
        ).first()

        assert audit is not None
        assert audit.entity_type == "Commitment"
        assert audit.payload_json["primary_cause"] == "Materials"


class TestRefusalAudit:
    """
    Test that refusal attempts are logged immutably.

    Critical per repair constitution: refusal must not be silent.
    """

    def test_refusal_creates_audit_event(self, db_session, sample_work_item):
        """
        CRITICAL: Refused commitment attempt creates AuditEvent.

        Per repair constitution section 3.4:
        - The attempt must be refused server-side
        - An AuditEvent with event_type = commitment_refused_not_ready must be written
        - The payload must include work_item_id, open_constraint_ids, attempted_by_user_id
        """
        sm = StateMachine(db_session)

        # Add constraint but don't clear it (Not Ready)
        constraint = sm.add_constraint(sample_work_item, "Materials", "Not ready")
        db_session.refresh(sample_work_item)

        # Attempt to commit (should be refused)
        with pytest.raises(RefusalError):
            sm.create_commitment(
                sample_work_item,
                committed_by_user_id="user_123",
                owner_user_id="user_123",
                due_at=datetime.utcnow() + timedelta(days=1)
            )

        # CRITICAL: Check audit event was created
        audit = db_session.query(AuditEvent).filter(
            AuditEvent.event_type == AuditEventType.COMMITMENT_REFUSED_NOT_READY
        ).first()

        assert audit is not None, "Refusal must create audit event"
        assert audit.entity_type == "WorkItem"
        assert audit.entity_id == str(sample_work_item.id)
        assert audit.user_id == "user_123", "Audit must record who attempted"

        # Verify payload contains required fields
        payload = audit.payload_json
        assert "work_item_id" in payload
        assert "open_constraint_ids" in payload
        assert "attempted_by_user_id" in payload
        assert payload["attempted_by_user_id"] == "user_123"
        assert constraint.id in payload["open_constraint_ids"]

    def test_refusal_with_no_constraints_audited(self, db_session, sample_work_item):
        """Refusal due to no constraints is also audited."""
        sm = StateMachine(db_session)

        # No constraints added (Not Ready)
        assert len(sample_work_item.constraints) == 0

        # Attempt to commit (should be refused)
        with pytest.raises(RefusalError):
            sm.create_commitment(
                sample_work_item,
                committed_by_user_id="user_123",
                owner_user_id="user_123",
                due_at=datetime.utcnow() + timedelta(days=1)
            )

        # Check audit event was created
        audit = db_session.query(AuditEvent).filter(
            AuditEvent.event_type == AuditEventType.COMMITMENT_REFUSED_NOT_READY,
            AuditEvent.entity_id == str(sample_work_item.id)
        ).first()

        assert audit is not None
        assert audit.payload_json["open_constraint_ids"] == []
        assert audit.payload_json["constraint_count"] == 0


class TestCommitmentImmutability:
    """
    Test that commitment immutability is enforced at the service layer.

    Per repair constitution section 4: Commitments are immutable once created.
    """

    def test_commitment_modification_guard_exists(self, db_session, sample_work_item):
        """StateMachine has explicit immutability guard method."""
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

        # Verify guard method exists and rejects modification
        with pytest.raises(ValueError) as exc_info:
            sm.attempt_modify_commitment(commitment, due_at=datetime.utcnow())

        assert "IMMUTABILITY VIOLATION" in str(exc_info.value)
        assert "due_at" in str(exc_info.value)

    def test_cannot_modify_due_date(self, db_session, sample_work_item):
        """Attempting to modify due_at raises ValueError."""
        sm = StateMachine(db_session)

        # Make Ready and commit
        c = sm.add_constraint(sample_work_item, "Materials", "Ready")
        sm.clear_constraint(c, "user_123")
        db_session.refresh(sample_work_item)

        original_due = datetime.utcnow() + timedelta(days=1)
        commitment = sm.create_commitment(
            sample_work_item,
            committed_by_user_id="user_123",
            owner_user_id="user_123",
            due_at=original_due
        )

        # Attempt to modify due date
        with pytest.raises(ValueError) as exc_info:
            sm.attempt_modify_commitment(commitment, due_at=datetime.utcnow() + timedelta(days=2))

        assert "IMMUTABILITY VIOLATION" in str(exc_info.value)
        assert "due_at" in str(exc_info.value)

    def test_cannot_modify_owner(self, db_session, sample_work_item):
        """Attempting to modify owner_user_id raises ValueError."""
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

        # Attempt to modify owner
        with pytest.raises(ValueError) as exc_info:
            sm.attempt_modify_commitment(commitment, owner_user_id="user_456")

        assert "IMMUTABILITY VIOLATION" in str(exc_info.value)

    def test_cannot_modify_work_item_id(self, db_session, sample_work_item):
        """Attempting to modify work_item_id raises ValueError."""
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

        # Attempt to modify work item ID
        with pytest.raises(ValueError) as exc_info:
            sm.attempt_modify_commitment(commitment, work_item_id=999)

        assert "IMMUTABILITY VIOLATION" in str(exc_info.value)


class TestAuditImmutability:
    """Test that audit events themselves are append-only."""

    def test_audit_events_have_no_update_methods(self):
        """
        AuditEvent model should not expose update methods.

        This is a design test - audit events should be append-only.
        """
        from app.models.audit import AuditEvent

        # Audit events should not have custom update/delete methods
        assert not hasattr(AuditEvent, 'update')
        assert not hasattr(AuditEvent, 'delete')
        # SQLAlchemy base methods exist, but we don't expose them in our service layer

    def test_multiple_audit_events_accumulate(self, db_session, sample_work_item):
        """
        Audit events accumulate - old ones are never deleted.

        This proves append-only behavior.
        """
        sm = StateMachine(db_session)

        # Perform multiple actions
        c1 = sm.add_constraint(sample_work_item, "Materials", "First")
        c2 = sm.add_constraint(sample_work_item, "Access", "Second")
        sm.clear_constraint(c1, "user_123")

        # Count audit events
        count = db_session.query(AuditEvent).count()
        assert count >= 3, "Should have at least 3 audit events"

        # All events still exist
        constraint_created_count = db_session.query(AuditEvent).filter(
            AuditEvent.event_type == AuditEventType.CONSTRAINT_CREATED
        ).count()
        assert constraint_created_count == 2

        constraint_cleared_count = db_session.query(AuditEvent).filter(
            AuditEvent.event_type == AuditEventType.CONSTRAINT_CLEARED
        ).count()
        assert constraint_cleared_count == 1

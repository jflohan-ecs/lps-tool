LPS Thin Slice AI Build Constitution (MVP)

Status
This constitution is binding for the MVP build. If an instruction conflicts with any other instruction, this constitution prevails.

Primary purpose
Build a production control mechanism that governs readiness, commitments, refusal, and learning. This is not a planning or scheduling tool.

Operating principle
The system must make it impossible to create commitments unless work is truly Ready, and must turn failure into structured learning signals without blame or optionality.

Thin slice scope
The MVP must support only the following end-to-end spine:
Intent → Not Ready or Ready → Committed → Complete or Failed → Learning Signal → Drill-down view

Everything outside this spine is out of scope.

Non-goals and explicit exclusions
The MVP must not include any of the following:
• Programme creation or editing
• Sequencing, dependencies, CPM, or schedule logic
• Optimisation, prediction, or AI assistance inside the product
• Dashboards beyond a minimal review list of commitments and failures
• Bidirectional integration with MSP/P6 (read-only references only)
• Bulk actions (bulk commit, bulk clear, etc.)
• Override paths of any kind (no admin override, no manager override)
• Multi-tenant enterprise capabilities, complex RBAC, delegation, approvals workflows

User posture for MVP
Assume a single project/workstream and a small set of users. Keep authentication and authorisation minimal. Do not build enterprise security features beyond basic sign-in and attribution.

Canonical language (must be used verbatim in UI and code)
• Commitment (not task, promise, action)
• Refusal (not warning, advisory block, or "are you sure")
• Not Ready (not pending, waiting)
• Failed (not slipped, delayed)
• Learning Signal (not insight, metric)

Domain objects (frozen)
Only these domain objects may exist in MVP:
1. WorkItem
2. Constraint
3. Commitment
4. LearningSignal

No additional objects are permitted (including "Task", "Issue", "Risk", "Action", "Dependency", "Programme", "Milestone").

WorkItem (minimum fields)
• id (unique, immutable)
• title (required)
• description (optional, short)
• location (optional but recommended)
• owner_user_id (required)
• state (required)
• reference_plan (optional, read-only linkage)
  – system: "MSP" or "P6" or "Other"
  – external_id: string
  – reference_dates: optional (display only)
• created_at, updated_at

Constraint (minimum fields)
• id
• work_item_id
• type (string enum, minimal)
• description (optional)
• status: Open or Cleared
• cleared_by_user_id (required when cleared)
• cleared_at (required when cleared)
• created_at

Commitment (minimum fields)
• id
• work_item_id (one active commitment per work item)
• committed_by_user_id
• owner_user_id (can equal committed_by_user_id)
• due_at (required)
• status: Active, Complete, Failed
• created_at
• completed_at or failed_at (required when status changes)

LearningSignal (minimum fields)
• id
• work_item_id
• commitment_id
• created_at
• primary_cause (required, from small enum)
• secondary_cause (optional)
• notes (optional but short, non-blame)
• drilldown_key (derived, deterministic)

State model (frozen)
WorkItem.state must be exactly one of:
• Intent
• Not Ready
• Ready
• Committed
• Complete
• Failed

No other states, sub-states, or hidden states are allowed.

State transition rules (hard invariants)
All state transitions must be enforced server-side. Client-side logic must never be authoritative.

Allowed transitions:
1. Create WorkItem → state = Intent
2. Intent → Not Ready (if any constraint is Open OR constraints list is empty)
3. Intent → Ready (only if at least one constraint exists AND all constraints are Cleared)
4. Not Ready → Ready (only when all constraints are Cleared)
5. Ready → Not Ready (if any new constraint is added as Open OR a cleared constraint is reopened)
6. Ready → Committed (only by creating a Commitment)
7. Committed → Complete (only by marking the active Commitment Complete)
8. Committed → Failed (only by marking the active Commitment Failed, or by explicit rule: Late completion counts as Failed)
9. Failed → Intent (optional reset mechanism, but must create a new Intent cycle; do not "reopen commitment")
10. Complete → Intent (optional next work cycle; not required, but if implemented must be explicit)

Forbidden transitions (must be impossible)
• Not Ready → Committed
• Intent → Committed
• Any state → Complete without an active Commitment
• Any state → Failed without an active Commitment
• Committed → Ready (no "uncommit")
• Any transition via override, admin actions, or direct database edits

Readiness invariants
• Readiness is binary: Ready or Not Ready
• Ready requires at least one Constraint, and all Constraints must be Cleared
• If constraints are empty, the item must be Not Ready
• If any constraint is Open, the item must be Not Ready
• No "soft readiness", "assumed readiness", or "ready with caveats"

Refusal invariants
A Refusal must occur when a user attempts to commit work that is Not Ready.
Refusal behaviour requirements:
• The commit action must be blocked server-side (not merely warned)
• The refusal message must explicitly cite the Open constraints
• There must be no alternative path to create a commitment

Commitment invariants
• A Commitment can only be created from a Ready WorkItem
• A WorkItem can have at most one active Commitment at a time
• Commitments are immutable once created (due date may not be edited in MVP)
• Completion is explicit; failure is explicit
• Late completion is treated as failure, not success (if completion occurs after due_at, status must be Failed)

Failure and learning invariants
• Every failed commitment must generate a LearningSignal automatically
• Failure cannot be recorded without primary cause classification
• LearningSignal is first-class and must be visible without analytics tooling
• No blame language, no user rating, no punitive scoring

Drill-down invariants
The system must provide a minimal drill-down view that aggregates LearningSignals by:
• primary_cause
• location (if present)
• reference_plan.system (if present)
Aggregation must be deterministic and simple. No predictions, no recommendations.

Audit and attribution invariants
Every critical action must be attributable to a user and time-stamped:
• Constraint cleared
• Commitment created
• Commitment completed
• Commitment failed
• Refusal event (attempted commit when Not Ready)

Build minimal audit logging sufficient to reconstruct what happened. Do not build reporting dashboards.

Minimal user interface requirements (only)
The UI must support the spine with minimal friction:
1. Create WorkItem (Intent)
2. Add constraints to the WorkItem
3. Clear constraints
4. See Ready or Not Ready clearly
5. Attempt to commit (and experience refusal if Not Ready)
6. Commit a Ready item (create Commitment)
7. Mark commitment Complete or Failed
8. On failure, classify cause (primary cause required)
9. View LearningSignals and a simple drill-down list

UX constraints (hard)
• No bulk actions
• No drag-and-drop scheduling
• No hidden states
• State must be visible at all times
• Commit and fail actions must be one-step actions
• Refusal must be clear and final, not negotiable

Reference plan linkage (read-only)
Allow optional linking of a WorkItem to an external plan identifier (MSP/P6/etc.).
Rules:
• Reference data must never alter readiness or allow commitment
• No write-back
• No schedule computations (float, criticality, dependencies)

Configuration (minimal)
Allow only minimal configuration values that do not change logic:
• cadence_label (daily, weekly) for display only
• allowed_primary_causes list (small enum)
Configuration must not:
• introduce new states
• change transition rules
• soften refusal
• make learning optional

Primary cause enum (initial suggestion, keep small)
Provide a short list suitable for construction delivery:
• Access
• Materials
• Information
• Resources
• Permits
• Plant or equipment
• Interfaces
• Weather
• Other

If "Other" is used, require a short note.

Testing requirements (must be implemented)
Write automated tests that prove the invariants. At minimum include tests for:
• Cannot commit when Not Ready (server-side)
• Ready requires at least one constraint and all constraints cleared
• Adding an Open constraint to a Ready item returns it to Not Ready
• Commitment cannot be edited once created
• Late completion becomes failure
• Every failure produces a LearningSignal
• Refusal logs an audit event
• Reference plan link does not affect readiness/commitment

Definition of done (MVP acceptance)
The MVP is done when:
• A user can run the full spine end-to-end in under 5 minutes
• It is impossible to commit Not Ready work even via API calls
• Refusals are clear, constraint-referenced, and logged
• Failure always yields a LearningSignal with a primary cause
• Drill-down shows repeated causes by simple aggregation
• No excluded features exist in the codebase (feature flags default off)

AI build loop (required working method)
Use the compounding loop:
1. Plan: restate the next ticket in this constitution's language
2. Delegate: implement only that ticket
3. Assess: run tests and a manual walkthrough of the spine
4. Codify: capture what was learned into:
   – additional tests, and
   – concise developer notes

Do not move to the next ticket until the current ticket's invariants are proven.

Instruction to the coding agent
Do not propose additional features.
Do not add new domain objects or states.
If a requirement seems to conflict with ease of implementation, preserve the invariants and simplify everything else.
When uncertain, choose the option that makes incorrect behaviour impossible, even if it reduces convenience.
End of constitution.

# LPS Tool - Getting Started

## What You've Built

You now have a working **Production Control System MVP** that implements the complete LPS constitution.

The system enforces:
- **Hard refusals** when trying to commit Not Ready work
- **State machine invariants** - impossible to violate the rules
- **Automatic learning signal generation** from every failure
- **Binary readiness** - no "soft ready" or assumptions

## Quick Start

### 1. Start the Server

```bash
cd /Users/jflohan/lps-tool
python -m uvicorn app.main:app --reload --port 8000
```

### 2. Open the UI

Visit: **http://localhost:8000**

### 3. Walk the Spine (5-minute demonstration)

#### Step 1: Create a Work Item
1. Enter a title: "Install formwork Zone A"
2. Add location: "Grid A1-A5"
3. Click "Create Work Item"
4. **Observe:** Item starts in **Intent** state

#### Step 2: Experience Refusal
1. Try to click "Create Commitment" (it's disabled)
2. **Observe:** You cannot commit because there are no constraints

#### Step 3: Add Constraints
1. Add constraint type: "Materials"
2. Description: "Concrete on site"
3. Click "Add Constraint"
4. **Observe:** State automatically changed to **Not Ready**

#### Step 4: Try to Commit (Still Refused)
1. The commit button is still disabled
2. **Observe:** Work is Not Ready because constraint is Open

#### Step 5: Clear Constraints
1. Click "Clear" on the Materials constraint
2. **Observe:** State automatically changed to **Ready**

#### Step 6: Create Commitment
1. Select a due date (future)
2. Click "Create Commitment"
3. **Observe:** State changed to **Committed**

#### Step 7: Fail the Commitment
1. Click "Fail" button
2. Enter primary cause: "Materials"
3. Add notes: "Concrete truck broke down"
4. **Observe:** State changed to **Failed**
5. **Observe:** Learning Signal automatically created

#### Step 8: View Learning Signals
1. Scroll down to "Learning Signals & Drill-down"
2. Click "Refresh Learning Signals"
3. **Observe:** Aggregated failure causes by location and system

## What Makes This Different

### 1. Refusal, Not Warnings
The system **blocks** commits when work is Not Ready. There's no "Are you sure?" dialog to click through.

###2. Server-Side Enforcement
All invariants are enforced in the state machine (`app/services/state_machine.py`). The UI can't cheat.

### 3. Automatic State Transitions
States update automatically based on constraints. You don't "move" items between states - the system calculates readiness.

### 4. Mandatory Learning
Every failure MUST have a cause. Learning signals are first-class objects, not analytics afterthoughts.

## API Documentation

FastAPI auto-generates documentation:
- **Interactive docs:** http://localhost:8000/docs
- **OpenAPI spec:** http://localhost:8000/openapi.json

## Testing

Run the invariant tests to prove the constitution rules:

```bash
pytest tests/test_invariants.py -v
```

All 15 tests should pass, proving:
- Readiness calculation
- Refusal enforcement
- Commitment constraints
- Learning signal generation
- State transition rules

## Project Structure

```
lps-tool/
├── app/
│   ├── models/
│   │   ├── domain.py          # 4 frozen domain objects
│   │   └── enums.py            # State, status, and cause enums
│   ├── services/
│   │   └── state_machine.py    # Core enforcement logic
│   ├── api/
│   │   ├── routes.py           # REST API endpoints
│   │   └── schemas.py          # Request/response models
│   ├── database.py             # SQLite setup
│   └── main.py                 # FastAPI app
├── tests/
│   └── test_invariants.py      # Proves all rules work
├── static/
│   └── index.html              # Minimal UI
├── CONSTITUTION.md             # The binding specification
└── lps.db                      # SQLite database (created on first run)
```

## Next Steps

This MVP is complete and functional. To extend it:

1. **Add authentication** - Currently using simple user IDs
2. **Deploy to production** - Use PostgreSQL instead of SQLite
3. **Build mobile UI** - API is ready, just needs a mobile client
4. **Add reporting** - Drill-down API is ready for dashboards
5. **Integrate with MSP/P6** - Use reference_plan fields for read-only linkage

## Key Files to Understand

1. **CONSTITUTION.md** - The law of the system
2. **app/services/state_machine.py** - Where invariants are enforced
3. **tests/test_invariants.py** - Proofs that it works
4. **app/api/routes.py** - API surface area

## Philosophy

This system is built on **enforcement, not encouragement**. It makes bad behavior impossible rather than just inadvisable.

The state machine is the product. Everything else is just interface.

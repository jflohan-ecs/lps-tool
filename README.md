# LPS Tool - MVP

## What This Is
A production control mechanism that governs readiness, commitments, refusal, and learning.

**Not** a planning or scheduling tool.

## Core Principle
Make it impossible to create commitments unless work is truly Ready.
Turn failure into structured learning signals without blame.

## Thin Slice Spine
Intent → Not Ready or Ready → Committed → Complete or Failed → Learning Signal → Drill-down

## Quick Start
```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Start the server
uvicorn app.main:app --reload

# Access at http://localhost:8000
```

## Project Structure
```
lps-tool/
├── app/
│   ├── models/        # Domain objects (WorkItem, Constraint, Commitment, LearningSignal)
│   ├── services/      # State machine and business logic
│   ├── api/           # FastAPI endpoints
│   └── main.py        # Application entry point
├── tests/             # Invariant tests
├── requirements.txt
└── README.md
```

## Constitution
See `CONSTITUTION.md` for the complete, binding specification.

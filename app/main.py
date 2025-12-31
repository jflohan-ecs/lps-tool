"""Main FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.database import engine, Base
from app.api.routes import router
# Import models to register them with SQLAlchemy Base
from app.models.domain import WorkItem, Constraint, Commitment, LearningSignal
from app.models.audit import AuditEvent

# Create database tables
Base.metadata.create_all(bind=engine)

# Create FastAPI app
app = FastAPI(
    title="LPS Tool - Production Control System",
    description="A production control mechanism that governs readiness, commitments, refusal, and learning.",
    version="0.1.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For MVP - restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api", tags=["LPS"])


@app.get("/", response_class=HTMLResponse)
def root():
    """Serve the UI."""
    with open("static/index.html", "r") as f:
        return f.read()


# Health check
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "LPS Tool"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

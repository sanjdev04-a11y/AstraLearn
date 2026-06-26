# ──────────────────────────────────────────────────────────────
# app/main.py
#
# WHY THIS FILE EXISTS:
#   This is the entry point of the entire backend application.
#   It creates the FastAPI app, configures middleware (like CORS),
#   registers all API routes, and defines startup/shutdown logic.
#
#   When you run `uvicorn app.main:app`, Python looks for a variable
#   named `app` in this file — that's the FastAPI instance.
# ──────────────────────────────────────────────────────────────

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database.base import Base
from app.database.session import engine
from app.models import document, subject, user  # noqa: F401

# ── Lifespan ──────────────────────────────────────────────────
# FastAPI's "lifespan" runs code at startup and shutdown.
# Everything BEFORE `yield` runs on startup.
# Everything AFTER `yield` runs on shutdown.
#
# We use it here to create database tables automatically on startup.
# In production, Alembic migrations replace this — but it's useful
# while developing so you don't have to run migration commands manually.
@asynccontextmanager
async def lifespan(app: FastAPI):
    from pathlib import Path
    # ── STARTUP ──────────────────────────────────────────────
    print(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Create upload directory if it doesn't exist
    Path(settings.UPLOAD_DIR).mkdir(
        parents=True,
        exist_ok=True,
    )
    # Create all tables that are registered with Base.metadata.
    # This is safe to run repeatedly — it only creates tables that
    # don't already exist (it never drops or modifies existing tables).
    #
    # NOTE: For this to pick up your models, you must import them
    # somewhere before this line runs. We do that below in the
    # "Import models" section.
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables ready")

    yield  # ← App is running and handling requests here

    # ── SHUTDOWN ─────────────────────────────────────────────
    print(f"👋 Shutting down {settings.APP_NAME}")


# ── Import models so Base knows about them ────────────────────
# SQLAlchemy's Base.metadata only knows about a model if that
# model's module has been imported. We import them here to ensure
# create_all() above sees every table.
#
# noqa: F401 suppresses "imported but unused" linter warnings —
# these imports are intentional side-effects (registering models).


# ── FastAPI App Instance ──────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Agentic Adaptive Learning Platform — Backend API",
    # Show interactive docs only in DEBUG mode
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)


# ── CORS Middleware ───────────────────────────────────────────
# CORS (Cross-Origin Resource Sharing) is a browser security feature.
# Without this, your React frontend (localhost:5173) would be blocked
# from calling this backend (localhost:8000).
#
# In production, replace "*" with your actual frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL]
    if not settings.DEBUG
    else ["*"],
    allow_credentials=True,
    allow_methods=["*"],   # GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],   # Authorization, Content-Type, etc.
)


# ── API Routers ───────────────────────────────────────────────
# Each feature module registers its own router here.
# prefix   → all routes in this router are prefixed with this path
# tags     → groups routes together in the /docs UI
from app.api.v1 import auth, subjects, documents

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(subjects.router, prefix="/api/v1/subjects", tags=["Subjects"])
app.include_router(
    documents.router,
    prefix="/api/v1/subjects/{subject_id}/documents",
    tags=["Documents"],
)


# ── Health Check ──────────────────────────────────────────────
# A simple endpoint to verify the server is alive.
# Load balancers, Docker, and monitoring tools use this.
@app.get("/health", tags=["Health"])
def health_check():
    """Returns 200 OK if the server is running."""
    return {
    "status": "healthy",
    "app": settings.APP_NAME,
    "version": settings.APP_VERSION,
    "debug": settings.DEBUG,
}


# ── Root ──────────────────────────────────────────────────────
@app.get("/", tags=["Root"])
def root():
    """Welcome message at the API root."""
    return {
    "message": f"Welcome to {settings.APP_NAME} API",
    "version": settings.APP_VERSION,
    "docs": "/docs" if settings.DEBUG else None,
}

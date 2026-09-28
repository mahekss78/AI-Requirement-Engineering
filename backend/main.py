"""
main.py
=======
FastAPI application entry point for the AREA platform.

Responsibilities:
1. Create the FastAPI application instance with OpenAPI metadata.
2. Register CORS middleware so the React frontend (localhost:5173) can
   communicate with this API in local development.
3. Mount the API router under the /api prefix.
4. Run create_all_tables() on startup to materialise ORM-defined tables.
5. Log a startup confirmation that the database and settings are accessible.

Running locally (without Docker):
    cd backend
    cp .env.example .env        # fill in your credentials
    pip install -r requirements.txt
    uvicorn main:app --reload --port 8000

Interactive API docs will be available at:
    http://localhost:8000/docs  (Swagger UI)
    http://localhost:8000/redoc (ReDoc)
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router
from app.config import settings
from app.database.connection import create_all_tables, verify_connection

# ------------------------------------------------------------------ #
# Logging
# ------------------------------------------------------------------ #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("area")


# ------------------------------------------------------------------ #
# Lifespan (replaces deprecated @app.on_event startup/shutdown)
# ------------------------------------------------------------------ #
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown handler.
    FastAPI calls the code before 'yield' on startup and after 'yield'
    on shutdown. This is the recommended pattern since FastAPI 0.95+.
    """
    # ---- Startup ----
    logger.info("AREA Platform starting up …")
    logger.info(f"Environment : {settings.APP_ENV}")
    logger.info(f"LLM Model   : {settings.OPENAI_MODEL}")

    # Initialise all database tables defined in models.py
    logger.info("Initialising database tables …")
    create_all_tables()

    # Verify the database is reachable before accepting traffic
    if not verify_connection():
        logger.error(
            "Database is unreachable. Check DATABASE_URL in .env "
            "and ensure PostgreSQL is running."
        )
    else:
        logger.info("Database connection verified ✓")

    # Warn if optional integrations are not configured
    if not settings.is_jira_configured:
        logger.warning(
            "Jira credentials not configured. Export-to-Jira will be unavailable."
        )
    if not settings.is_smtp_configured:
        logger.warning(
            "SMTP credentials not configured. Email notifications will be skipped."
        )

    logger.info("AREA Platform ready ✓")

    yield  # ← application runs here

    # ---- Shutdown ----
    logger.info("AREA Platform shutting down …")


# ------------------------------------------------------------------ #
# FastAPI Application
# ------------------------------------------------------------------ #
app = FastAPI(
    title="AREA — AI Requirement Engineering Assistant",
    description=(
        "Enterprise-grade requirement lifecycle management platform. "
        "Transforms unstructured stakeholder inputs into validated, "
        "structured SDLC requirements."
    ),
    version="1.0.0",
    contact={"name": "AREA Project Team"},
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ------------------------------------------------------------------ #
# CORS Middleware
# In production, replace "*" with the explicit frontend domain.
# ------------------------------------------------------------------ #
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:80",    # Docker frontend container
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------ #
# API Router
# All endpoints are prefixed with /api so they are clearly distinguishable
# from static assets or future WebSocket paths.
# ------------------------------------------------------------------ #
app.include_router(router, prefix="/api")

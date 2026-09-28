"""
app/models/models.py
====================
SQLAlchemy ORM models for the AREA platform.

Each class maps directly to a PostgreSQL table. The table creation order
(enforced by FK constraints) matches the migration sequence in the PDS:

  1. projects
  2. documents
  3. requirements
  4. requirement_versions
  5. clarifications
  6. comments
  7. notifications
  8. audit_logs

Design notes:
- UUIDs are used as primary keys across all tables for distributed-safe
  identity (no auto-increment collisions if the database is ever sharded).
- JSONB columns store the dynamic RequirementObject payload. JSONB is
  preferred over JSON in PostgreSQL because it is stored in binary form,
  supports indexing, and allows efficient key-path queries.
- server_default=func.now() lets the database engine set timestamps,
  ensuring accuracy even if application clocks drift.
- All FK relationships use ON DELETE CASCADE so that deleting a project
  automatically removes all its child records without orphaned rows.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    Text,
    ForeignKey,
    DateTime,
    JSON,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.database.connection import Base

# Dialect-compatible JSONB type (uses PostgreSQL JSONB in production, falls back to JSON in SQLite tests)
JSONB_TYPE = JSONB().with_variant(JSON, "sqlite")



# ------------------------------------------------------------------ #
# 0. Accounts & User Sessions (Authentication / Session Engine)
# ------------------------------------------------------------------ #
class Account(Base):
    """
    Persistent account model stored in PostgreSQL.
    Manages user identity, account status (ACTIVE | INACTIVE), and permanent role binding.
    """

    __tablename__ = "accounts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Unique account identifier (UUID v4)",
    )
    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique user email address",
    )
    password_hash = Column(
        String(255),
        nullable=True,
        comment="Securely hashed password (bcrypt via passlib; NULL for OAuth accounts)",
    )
    account_status = Column(
        String(20),
        nullable=False,
        default="ACTIVE",
        index=True,
        comment="ACTIVE | INACTIVE — deactivated accounts cannot authenticate",
    )
    assigned_role = Column(
        String(50),
        nullable=True,
        default=None,
        comment=(
            "One of: BUSINESS_ANALYST, CLIENT, DEVELOPER, QA, PRODUCT_OWNER. "
            "NULL until initial one-time role selection. Immutable once set."
        ),
    )
    email_verified = Column(
        Boolean,
        nullable=False,
        default=False,
        comment="True once email ownership is verified via OTP code",
    )
    verification_code = Column(
        String(10),
        nullable=True,
        comment="6-digit OTP code for email verification",
    )
    verification_code_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Expiration timestamp for verification OTP code",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_login_at = Column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of last successful sign-in",
    )

    # Relationships
    sessions = relationship("UserSession", back_populates="account", cascade="all, delete-orphan")
    oauth_accounts = relationship("OAuthAccount", back_populates="account", cascade="all, delete-orphan")


class OAuthAccount(Base):
    """
    Maps external OAuth 2.0 provider identities (Google, Microsoft, GitHub) to an AREA Account.
    Authoritative lookup key is (provider, provider_user_id).
    """

    __tablename__ = "oauth_accounts"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(
        String(50),
        nullable=False,
        comment="OAuth provider identifier (google, microsoft, github)",
    )
    provider_user_id = Column(
        String(255),
        nullable=False,
        comment="Immutable provider subject/user ID (e.g. sub from OpenID)",
    )
    provider_email = Column(
        String(255),
        nullable=True,
        comment="Email returned by provider at linking time",
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    account = relationship("Account", back_populates="oauth_accounts")


class OAuthState(Base):
    """
    Short-lived, server-side OAuth 2.0 state record for CSRF protection.
    Bound to a dedicated browser transaction cookie (area_oauth_state).
    """

    __tablename__ = "oauth_states"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    state_token = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    provider = Column(
        String(50),
        nullable=False,
    )
    transaction_cookie_hash = Column(
        String(255),
        nullable=False,
        comment="SHA-256 hash of area_oauth_state transaction cookie",
    )
    is_used = Column(
        Boolean,
        default=False,
        nullable=False,
    )
    consumed_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class UserSession(Base):
    """
    Server-managed session record stored in PostgreSQL.
    Paired with an HttpOnly, Secure session cookie sent to the browser.
    """

    __tablename__ = "user_sessions"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    session_token = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Cryptographically secure 256-bit token string stored in HttpOnly cookie",
    )
    account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
        comment="Session expiration timestamp",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        comment="Set to False on logout or manual revocation",
    )

    account = relationship("Account", back_populates="sessions")



# ------------------------------------------------------------------ #
# 1. Projects
# ------------------------------------------------------------------ #
class Project(Base):
    """
    Top-level container for a client engagement.
    All requirements, documents, and audit records belong to a project.
    """

    __tablename__ = "projects"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        comment="Unique project identifier (UUID v4)",
    )
    name = Column(String(255), nullable=False, comment="Human-readable project name")
    description = Column(Text, nullable=True, comment="Optional project summary")
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships (back-populates for ORM traversal)
    documents = relationship("Document", back_populates="project", cascade="all, delete-orphan")
    requirements = relationship("Requirement", back_populates="project", cascade="all, delete-orphan")


# ------------------------------------------------------------------ #
# 2. Documents
# ------------------------------------------------------------------ #
class Document(Base):
    """
    Stores metadata and normalized plain-text content for every
    uploaded file. The raw binary is NOT stored in the database;
    only the extracted text is persisted here so AI capabilities
    can query it without re-parsing the file each time.
    """

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    file_name = Column(String(255), nullable=False, comment="Original uploaded filename")
    file_type = Column(
        String(50),
        nullable=False,
        comment="Detected MIME type or extension: pdf, docx, txt, xlsx, eml",
    )
    file_size_bytes = Column(Integer, nullable=False)
    normalized_content = Column(
        Text,
        nullable=False,
        comment="Plain text extracted from the file by the parser service",
    )
    word_count = Column(Integer, nullable=True)
    parse_status = Column(
        String(30),
        nullable=False,
        default="SUCCESS",
        comment="SUCCESS | FAILED | EMPTY",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    project = relationship("Project", back_populates="documents")


# ------------------------------------------------------------------ #
# 3. Requirements
# ------------------------------------------------------------------ #
class Requirement(Base):
    """
    Central table. Each row represents one living requirement object
    that evolves through the lifecycle states defined by the PDS state machine.

    The `requirement_data` JSONB column stores the full RequirementObject
    Pydantic schema (content, relationships, artifacts, scores) so that
    capabilities can read and update it as a single atomic document.
    """

    __tablename__ = "requirements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    project_id = Column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = Column(String(255), nullable=False)

    # ---- Lifecycle State Machine ----
    current_state = Column(
        String(50),
        nullable=False,
        default="DRAFT",
        comment=(
            "Valid states: DRAFT | INGESTING | AI_ANALYZED | "
            "BA_REVIEW | CLARIFYING | PEER_REVIEW | FROZEN | FAILED"
        ),
    )
    assigned_role = Column(
        String(50),
        nullable=False,
        default="BUSINESS_ANALYST",
        comment="Role currently responsible for actioning this requirement",
    )

    # ---- Version Control ----
    version = Column(
        String(20),
        nullable=False,
        default="0.1.0",
        comment="Semantic versioning: MAJOR.MINOR.PATCH",
    )

    # ---- AI Quality Metrics ----
    confidence_score = Column(
        Float,
        nullable=False,
        default=0.0,
        comment="Normalized 0.0–100.0 composite quality score from the Confidence Engine",
    )
    health_score = Column(
        Float,
        nullable=False,
        default=100.0,
        comment="Normalized 0.0–100.0 workflow health score from the Health Engine",
    )
    health_status = Column(
        String(30),
        nullable=False,
        default="Healthy",
        comment="Healthy | Needs Review | At Risk | Blocked",
    )
    open_questions_count = Column(Integer, nullable=False, default=0)
    clarification_cycle_count = Column(
        Integer,
        nullable=False,
        default=0,
        comment="Incremented each BA_REVIEW -> CLARIFYING -> BA_REVIEW cycle",
    )

    # ---- Dynamic Payload (JSONB) ----
    requirement_data = Column(
        JSONB_TYPE,
        nullable=False,
        default=dict,
        comment="Full RequirementObject Pydantic schema serialised as JSONB",
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    project = relationship("Project", back_populates="requirements")
    versions = relationship(
        "RequirementVersion", back_populates="requirement", cascade="all, delete-orphan"
    )
    clarifications = relationship(
        "Clarification", back_populates="requirement", cascade="all, delete-orphan"
    )
    comments = relationship(
        "Comment", back_populates="requirement", cascade="all, delete-orphan"
    )
    audit_logs = relationship(
        "AuditLog", back_populates="requirement", cascade="all, delete-orphan"
    )


# ------------------------------------------------------------------ #
# 4. Requirement Versions (Immutable Snapshots)
# ------------------------------------------------------------------ #
class RequirementVersion(Base):
    """
    Immutable snapshot of a requirement at a specific point in time.
    Written whenever:
    - The BA approves a draft (minor version bump).
    - A requirement is frozen/baselined (major version bump).
    - A rollback is executed.

    Rows in this table are NEVER updated — only inserted. This provides
    a complete, tamper-evident audit trail of requirement evolution.
    """

    __tablename__ = "requirement_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    requirement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    version = Column(String(20), nullable=False)
    requirement_data = Column(
        JSONB_TYPE,
        nullable=False,
        comment="Complete snapshot of requirement_data at this version",
    )
    change_rationale = Column(
        Text,
        nullable=True,
        comment="Human-readable reason for this version (e.g. 'Client updated return period')",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    requirement = relationship("Requirement", back_populates="versions")


# ------------------------------------------------------------------ #
# 5. Clarifications
# ------------------------------------------------------------------ #
class Clarification(Base):
    """
    A targeted question generated by the AI Gap Detection service and
    sent to a specific stakeholder role for resolution.

    Status lifecycle: PENDING -> ANSWERED
    Once answered, the Lifecycle Coordinator feeds the answer back into
    the Requirement Object and recalculates the confidence score.
    """

    __tablename__ = "clarifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    requirement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    question = Column(Text, nullable=False)
    assigned_role = Column(
        String(50),
        nullable=False,
        comment="CLIENT | DEVELOPER | QA | PRODUCT_OWNER",
    )
    status = Column(
        String(30),
        nullable=False,
        default="PENDING",
        comment="PENDING | ANSWERED",
    )
    options = Column(
        JSONB_TYPE,
        nullable=True,
        comment="Optional list of predefined answer choices, e.g. ['Yes', 'No']",
    )
    answer = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    answered_at = Column(DateTime(timezone=True), nullable=True)

    requirement = relationship("Requirement", back_populates="clarifications")


# ------------------------------------------------------------------ #
# 6. Comments
# ------------------------------------------------------------------ #
class Comment(Base):
    """
    Inline annotation left by a reviewer (Developer, QA, PO) on a
    specific element of the requirement (e.g. a User Story ID or AC ID).

    `target_element_id` stores the ID of the annotated element (e.g. "US-1",
    "AC-2") so the frontend can render comments inline next to the correct item.
    """

    __tablename__ = "comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    requirement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    author_role = Column(
        String(50),
        nullable=False,
        comment="DEVELOPER | QA | PRODUCT_OWNER | BUSINESS_ANALYST",
    )
    target_element_id = Column(
        String(50),
        nullable=False,
        comment="ID of the annotated requirement element, e.g. US-1, AC-3",
    )
    comment_text = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    requirement = relationship("Requirement", back_populates="comments")


# ------------------------------------------------------------------ #
# 7. Notifications
# ------------------------------------------------------------------ #
class Notification(Base):
    """
    In-app notification delivered to a specific role.
    Created by the Audit & Notification service whenever a lifecycle
    event requires stakeholder attention (e.g. a clarification question is
    routed to the Client, or a review is requested from QA).

    When SMTP is configured, an email is also dispatched; this row acts as
    the fallback to ensure the message is still visible in the dashboard
    if email delivery fails.
    """

    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    recipient_role = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    notification_type = Column(
        String(50),
        nullable=False,
        default="INFO",
        comment="INFO | CLARIFICATION | REVIEW_REQUEST | APPROVAL | WARNING",
    )
    is_read = Column(Boolean, nullable=False, default=False)
    requirement_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        comment="Optional link to the related requirement",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ------------------------------------------------------------------ #
# 8. Audit Logs (Immutable Event Log)
# ------------------------------------------------------------------ #
class AuditLog(Base):
    """
    Immutable record of every significant action taken on a requirement.
    Written by the Audit & Notification service on:
    - State transitions
    - BA edits (with JSON diff of before/after)
    - Stakeholder approvals and rejections
    - AI capability completions
    - Jira export events

    Rows in this table are NEVER updated — only inserted.
    """

    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)
    requirement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("requirements.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_role = Column(
        String(50),
        nullable=False,
        comment="Role that caused this event (SYSTEM | BUSINESS_ANALYST | DEVELOPER | ...)",
    )
    action_type = Column(
        String(100),
        nullable=False,
        comment=(
            "Descriptive action label, e.g. STATE_TRANSITION | BA_EDIT | "
            "AI_ANALYSIS_COMPLETE | JIRA_EXPORT | CLARIFICATION_ANSWERED"
        ),
    )
    prev_state = Column(String(50), nullable=True)
    new_state = Column(String(50), nullable=True)
    change_diff = Column(
        JSONB_TYPE,
        nullable=True,
        comment="JSON diff (before/after) for BA edits; null for other event types",
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    requirement = relationship("Requirement", back_populates="audit_logs")


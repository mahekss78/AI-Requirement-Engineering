"""
app/schemas/schemas.py
======================
Pydantic schemas (request/response contracts) for the AREA platform.

These schemas serve three purposes:
1. Request validation — FastAPI validates incoming JSON bodies against them.
2. Response serialisation — FastAPI converts ORM objects to these schemas
   for API responses, ensuring no unexpected fields leak to the client.
3. API documentation — FastAPI auto-generates OpenAPI docs from these classes.

Design notes:
- Schemas are intentionally separate from ORM models (models.py) to maintain
  clean architecture boundaries.
- `from_attributes=True` in model_config allows Pydantic to read values from
  SQLAlchemy ORM instances as if they were dicts (replaces Pydantic v1 orm_mode).
- Nested schemas (e.g. RequirementContent) mirror the JSONB structure stored
  in requirements.requirement_data, keeping serialisation consistent.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ================================================================== #
# Shared / Primitive Schemas
# ================================================================== #


class OKResponse(BaseModel):
    """Generic success acknowledgement used by state-change endpoints."""

    status: str = "ok"
    message: str = ""


# ================================================================== #
# Authentication & Session Schemas
# ================================================================== #


SUPPORTED_ROLES = {
    "BUSINESS_ANALYST",
    "CLIENT",
    "DEVELOPER",
    "QA",
    "PRODUCT_OWNER",
}


class EmailCheckRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, description="Email address to validate")


class EmailCheckResponse(BaseModel):
    exists: bool = Field(description="True if account already exists")
    deliverable: bool = Field(description="True if email address passes syntax and domain/MX checks")
    detail: str = Field(description="Human-readable validation status message")


class OnboardRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, description="Email address")
    password: str = Field(min_length=12, max_length=128, description="Strong password")


class OnboardResponse(BaseModel):
    status: str = Field(description="verification_required | success")
    message: str = Field(description="Instructions or confirmation")
    email: str = Field(description="Target email address")
    dev_otp: Optional[str] = Field(default=None, description="OTP code displayed in dev mode for manual testing")


class VerifyEmailRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255, description="Email address")
    code: str = Field(min_length=6, max_length=10, description="6-digit OTP verification code")


class UserRegister(BaseModel):
    email: str = Field(min_length=3, max_length=255, description="User email address")
    password: str = Field(min_length=6, max_length=128, description="User password")


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: UUID
    email: str

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    authenticated: bool
    user: Optional[UserResponse] = None
    account_status: Optional[str] = None  # 'ACTIVE' | 'INACTIVE'
    assigned_role: Optional[str] = None   # 'BUSINESS_ANALYST' | 'CLIENT' | etc. or None


class RoleAssignmentRequest(BaseModel):
    role: str = Field(description="One of: BUSINESS_ANALYST, CLIENT, DEVELOPER, QA, PRODUCT_OWNER")

    @model_validator(mode="after")
    def validate_role(self) -> "RoleAssignmentRequest":
        if self.role not in SUPPORTED_ROLES:
            raise ValueError(
                f"Invalid role '{self.role}'. Supported roles: {sorted(SUPPORTED_ROLES)}"
            )
        return self


class ForgotPasswordRequest(BaseModel):
    email: str



# ================================================================== #
# Requirement Content Sub-schemas
# These mirror the JSONB structure stored inside requirements.requirement_data
# ================================================================== #


class SourceEvidence(BaseModel):
    snippet: str = ""
    start_offset: int = 0
    end_offset: int = 0
    confidence: float = 1.0

    model_config = {"extra": "allow"}


class NFRItem(BaseModel):
    id: str = Field(description="e.g. NFR-001")
    statement: str
    category: str = "Performance"  # Performance | Scalability | Security | Availability | Reliability | Compliance | Usability
    metric: Optional[str] = None
    scope: Optional[str] = "System"
    validation_method: Optional[str] = None
    source_evidence: Optional[SourceEvidence] = None
    derivation_type: str = "EXPLICIT"  # EXPLICIT | INFERRED

    model_config = {"extra": "allow"}


class OpenQuestionItem(BaseModel):
    id: str = Field(description="e.g. Q-001")
    question: str
    blocking: bool = True
    related_requirements: List[str] = []
    reason: Optional[str] = None
    source_evidence: Optional[SourceEvidence] = None
    derivation_type: str = "EXPLICIT"

    model_config = {"extra": "allow"}


class AmbiguityItem(BaseModel):
    id: str = Field(description="e.g. AMB-001")
    statement: str
    ambiguous_term: str
    clarification_question: str
    related_requirements: List[str] = []
    source_evidence: Optional[SourceEvidence] = None
    derivation_type: str = "EXPLICIT"

    model_config = {"extra": "allow"}


class ConflictItem(BaseModel):
    id: str = Field(description="e.g. CON-001")
    requirement_a: str
    requirement_b: str
    conflict_description: str
    severity: str = "HIGH"  # HIGH | MEDIUM | LOW
    clarification_question: str
    source_evidence: Optional[SourceEvidence] = None

    model_config = {"extra": "allow"}


class GapItem(BaseModel):
    id: str = Field(description="e.g. GAP-001")
    description: str
    related_requirement: Optional[str] = None
    severity: str = "MEDIUM"  # HIGH | MEDIUM | LOW
    clarification_question: str
    assigned_role: str = "CLIENT"
    derivation_type: str = "AI_SUGGESTION"

    model_config = {"extra": "allow"}


class UserStory(BaseModel):
    id: str = Field(description="e.g. US-001")
    as_a: str
    i_want: str
    so_that: str
    source_requirement: Optional[str] = None
    status: Optional[str] = "complete"  # complete | needs_clarification
    missing: List[str] = []

    model_config = {"extra": "allow"}


class AcceptanceCriterion(BaseModel):
    id: str = Field(description="e.g. AC-001")
    story_id: Optional[str] = Field(default="", description="References a UserStory.id")
    scenario: Optional[str] = ""
    given: Optional[str] = ""
    when_: Optional[str] = Field(default="", alias="when")
    then: Optional[str] = ""
    derivation_type: Optional[str] = "EXPLICIT"
    gherkin_status: Optional[str] = "complete"

    model_config = {"populate_by_name": True, "extra": "allow"}


class BusinessRule(BaseModel):
    id: str = Field(description="e.g. BR-001")
    statement: str
    source_evidence: Optional[SourceEvidence] = None
    derivation_type: str = "EXPLICIT"

    model_config = {"extra": "allow"}


class Constraint(BaseModel):
    id: str = Field(description="e.g. CO-001")
    statement: str
    source_evidence: Optional[SourceEvidence] = None

    model_config = {"extra": "allow"}


class Assumption(BaseModel):
    id: Optional[str] = None
    statement: str
    source_evidence: Optional[SourceEvidence] = None

    model_config = {"extra": "allow"}


class RequirementContent(BaseModel):
    """Full structured content of a single requirement."""

    epic_title: str = ""
    metadata: Dict[str, Any] = {}
    user_stories: List[UserStory] = []
    acceptance_criteria: List[AcceptanceCriterion] = []
    incomplete_stories: List[Dict[str, Any]] = []
    non_functional_requirements: List[NFRItem] = []
    business_rules: List[BusinessRule] = []
    constraints: List[Constraint] = []
    assumptions: List[Assumption] = []
    open_questions: List[OpenQuestionItem] = []
    ambiguities: List[AmbiguityItem] = []
    conflicts: List[ConflictItem] = []
    gaps: List[GapItem] = []

    model_config = {"extra": "allow"}


class RequirementRelationships(BaseModel):
    depends_on: List[UUID] = []
    blocked_by: List[UUID] = []
    duplicate_of: Optional[UUID] = None
    related_requirements: List[UUID] = []


class GeneratedArtifactRefs(BaseModel):
    brd_uuid: Optional[UUID] = None
    frd_uuid: Optional[UUID] = None
    rtm_uuid: Optional[UUID] = None
    test_case_uuids: List[UUID] = []
    jira_epic_id: Optional[str] = None
    jira_story_ids: Dict[str, str] = {}  # {"US-1": "PROJ-101"}


class ConfidenceBreakdown(BaseModel):
    completeness: float = 0.0
    clarity: float = 0.0
    consistency: float = 0.0
    testability: float = 0.0
    traceability: float = 0.0


# ================================================================== #
# Project Schemas
# ================================================================== #


class ProjectCreate(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    description: Optional[str] = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ================================================================== #
# Document Schemas
# ================================================================== #


class DocumentResponse(BaseModel):
    id: UUID
    project_id: UUID
    file_name: str
    file_type: str
    file_size_bytes: int
    word_count: Optional[int]
    parse_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ================================================================== #
# Requirement Schemas
# ================================================================== #


class RequirementCreate(BaseModel):
    """Used internally when the ingestion endpoint initialises a new requirement."""

    project_id: UUID
    title: str = Field(min_length=3, max_length=255)


class RequirementSummary(BaseModel):
    """Lightweight view used in the BA Dashboard list."""

    id: UUID
    title: str
    current_state: str
    assigned_role: str
    version: str
    confidence_score: float
    health_score: float
    health_status: str
    open_questions_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RequirementDetail(BaseModel):
    """
    Full Requirement Object view returned by GET /api/requirements/{id}.
    The requirement_data JSONB is exposed as a typed Dict so downstream
    consumers can read all nested sub-schemas.
    """

    id: UUID
    project_id: UUID
    title: str
    current_state: str
    assigned_role: str
    version: str
    confidence_score: float
    health_score: float
    health_status: str
    open_questions_count: int
    clarification_cycle_count: int
    requirement_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RequirementUpdate(BaseModel):
    """
    Payload for PUT /api/requirements/{id}.
    The BA sends partial or full requirement_data updates.
    Only fields explicitly provided are applied; None means "leave unchanged".
    """

    title: Optional[str] = None
    requirement_data: Optional[Dict[str, Any]] = None
    change_rationale: Optional[str] = Field(
        default=None,
        description="Reason for this edit — stored in requirement_versions",
    )


# ================================================================== #
# Ingest Schemas
# ================================================================== #


class IngestRequest(BaseModel):
    """
    Payload for POST /api/requirements/ingest.
    The file content is sent as a Base64-encoded string so it can be
    transmitted as JSON without a multipart upload endpoint.
    """

    project_id: UUID
    file_name: str = Field(min_length=1, max_length=255)
    file_content_base64: str = Field(
        description="Base64-encoded binary content of the uploaded file"
    )


class IngestTextRequest(BaseModel):
    """
    Payload for POST /api/requirements/ingest-text.
    Allows direct ingestion of meeting transcripts, interview notes, or raw requirements text.
    """

    project_id: UUID = Field(default_factory=lambda: UUID("a1b2c3d4-e5f6-47a8-b9c0-d1e2f3a4b5c6"))
    title: Optional[str] = Field(default=None, max_length=255)
    text: str = Field(min_length=1, description="Raw transcript, email content, or requirements text")
    source_type: Optional[str] = Field(default="TRANSCRIPT", description="TRANSCRIPT | DIRECT_TEXT | MEETING_MINUTES | EMAIL")


class IngestResponse(BaseModel):
    requirement_id: UUID
    document_id: UUID
    status: str = "INGESTING"
    message: str = "Document accepted. Analysis pipeline started in background."


# ================================================================== #
# State Transition Schemas
# ================================================================== #


VALID_EVENTS = {
    "APPROVE_DRAFT",
    "REQUEST_REWORK",
    "SEND_CLARIFICATION",
    "CLARIFICATION_ANSWERED",
    "APPROVE_PEER_REVIEW",
    "REJECT_PEER_REVIEW",
    "FREEZE",
}


class TransitionRequest(BaseModel):
    event: str = Field(description=f"One of: {', '.join(sorted(VALID_EVENTS))}")
    actor_role: str = Field(default="BUSINESS_ANALYST")
    rationale: Optional[str] = None

    @model_validator(mode="after")
    def validate_event(self) -> "TransitionRequest":
        if self.event not in VALID_EVENTS:
            raise ValueError(
                f"Unknown event '{self.event}'. Valid events: {VALID_EVENTS}"
            )
        return self


class TransitionResponse(BaseModel):
    requirement_id: UUID
    previous_state: str
    new_state: str
    assigned_role: str


# ================================================================== #
# Clarification Schemas
# ================================================================== #


class ClarificationCreate(BaseModel):
    requirement_id: UUID
    question: str
    assigned_role: str = Field(
        description="CLIENT | DEVELOPER | QA | PRODUCT_OWNER"
    )
    options: Optional[List[str]] = None


class ClarificationAnswer(BaseModel):
    answer: str


class ClarificationResponse(BaseModel):
    id: UUID
    requirement_id: UUID
    question: str
    assigned_role: str
    status: str
    options: Optional[List[str]]
    answer: Optional[str]
    created_at: datetime
    answered_at: Optional[datetime]

    model_config = {"from_attributes": True}


# ================================================================== #
# Comment Schemas
# ================================================================== #


class CommentCreate(BaseModel):
    requirement_id: UUID
    author_role: str
    target_element_id: str = Field(
        description="ID of the annotated element, e.g. US-1 or AC-3"
    )
    comment_text: str


class CommentResponse(BaseModel):
    id: UUID
    requirement_id: UUID
    author_role: str
    target_element_id: str
    comment_text: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ================================================================== #
# Notification Schemas
# ================================================================== #


class NotificationResponse(BaseModel):
    id: UUID
    recipient_role: str
    message: str
    notification_type: str
    is_read: bool
    requirement_id: Optional[UUID]
    created_at: datetime

    model_config = {"from_attributes": True}


# ================================================================== #
# Audit Log Schemas
# ================================================================== #


class AuditLogResponse(BaseModel):
    id: UUID
    requirement_id: UUID
    actor_role: str
    action_type: str
    prev_state: Optional[str]
    new_state: Optional[str]
    change_diff: Optional[Dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


# ================================================================== #
# Dashboard / Metrics Schemas
# ================================================================== #


class DashboardMetrics(BaseModel):
    total_requirements: int
    frozen_count: int
    at_risk_count: int
    blocked_count: int
    average_confidence: float
    average_health: float


# ================================================================== #
# Jira Export Schemas
# ================================================================== #


class JiraExportRequest(BaseModel):
    jira_domain: Optional[str] = None   # Overrides config if provided
    jira_email: Optional[str] = None    # Overrides config if provided
    project_key: Optional[str] = None   # Overrides config if provided


class JiraExportResponse(BaseModel):
    status: str
    jira_epic_key: Optional[str] = None
    jira_epic_url: Optional[str] = None
    jira_story_count: int = 0
    message: str = ""


# ================================================================== #
# Rollback Schemas
# ================================================================== #


class RollbackRequest(BaseModel):
    target_version: str = Field(
        description="Semantic version string to restore, e.g. '0.3.0'"
    )


class VersionHistoryItem(BaseModel):
    id: UUID
    version: str
    change_rationale: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ================================================================== #
# Health Check Schema
# ================================================================== #


class HealthCheckResponse(BaseModel):
    status: str
    database: str
    version: str = "1.0.0"

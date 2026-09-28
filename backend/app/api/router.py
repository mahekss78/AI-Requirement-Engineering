"""
app/api/router.py
=================
FastAPI route controller for the AREA platform.

Implements all 15 REST endpoints as specified in PDS Volume 3, Chapter 18:
- Health check
- Requirements CRUD & Version history
- State machine transitions & gating
- Clarifications & Stakeholder Q&A
- Inline Comments & Annotations
- Audit-driven Notifications
- Dashboard metrics aggregation
- Version rollback
"""

import uuid
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.auth_router import router as auth_router
from app.api.dependencies import (
    get_current_account,
    get_db,
    require_role,
)
from app.database.connection import verify_connection
from app.models.models import (
    Account,
    Clarification,
    Comment,
    Project,
    Requirement,
)
from app.schemas.schemas import (
    AuditLogResponse,
    ClarificationAnswer,
    ClarificationCreate,
    ClarificationResponse,
    CommentCreate,
    CommentResponse,
    DashboardMetrics,
    HealthCheckResponse,
    IngestRequest,
    IngestResponse,
    IngestTextRequest,
    JiraExportRequest,
    JiraExportResponse,
    NotificationResponse,
    RequirementDetail,
    RequirementSummary,
    RequirementUpdate,
    RollbackRequest,
    TransitionRequest,
    TransitionResponse,
    VersionHistoryItem,
)
from app.services.audit_notify import audit_service, notification_service
from app.services.lifecycle import lifecycle_coordinator
from app.services.memory import compute_json_diff, memory_service
from app.services.scoring import confidence_engine, health_engine

router = APIRouter()

# Mount Authentication & Session endpoints under /api/auth
router.include_router(auth_router)


# ================================================================== #
# Health Check
# ================================================================== #


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check",
    tags=["System"],
)
def health_check(db: Session = Depends(get_db)) -> HealthCheckResponse:
    """
    Returns the operational status of the API and database connection.
    """
    db_ok = verify_connection()
    return HealthCheckResponse(
        status="ok" if db_ok else "degraded",
        database="connected" if db_ok else "unreachable",
    )


from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.models.models import (
    Account,
    Clarification,
    Comment,
    Document,
    Requirement,
)
from app.services.runner import capability_runner
from app.utils.helpers import parse_document_content


# ================================================================== #
# Ingestion  (CapabilityRunner pipeline wired in Phase C)
# ================================================================== #


@router.post(
    "/requirements/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a document and start the analysis pipeline",
    tags=["Ingestion"],
)
def ingest_document(
    payload: IngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_account: Account = Depends(require_role("BUSINESS_ANALYST")),
) -> IngestResponse:
    """
    Accepts Base64 document, parses content, creates Document and Requirement records,
    and dispatches the 6-step CapabilityRunner pipeline in background.
    """
    parsed_text = parse_document_content(payload.file_content_base64, payload.file_name)
    if not parsed_text:
        parsed_text = f"Ingested document content from {payload.file_name}"

    # 0. Ensure Project container exists (prevents foreign key constraint failure)
    project = db.query(Project).filter(Project.id == payload.project_id).first()
    if not project:
        project = Project(
            id=payload.project_id,
            name="Default Enterprise Project",
            description="Container project for ingested documents",
        )
        db.add(project)
        db.commit()

    # 1. Create Document record
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        project_id=payload.project_id,
        file_name=payload.file_name,
        file_type=payload.file_name.rsplit(".", 1)[-1].lower() if "." in payload.file_name else "txt",
        file_size_bytes=len(payload.file_content_base64),
        normalized_content=parsed_text,
    )

    db.add(doc)
    db.commit()

    # 2. Create Draft Requirement record
    req_id = uuid.uuid4()
    req = Requirement(
        id=req_id,
        project_id=payload.project_id,
        title=f"Draft: {payload.file_name}",
        current_state="INGESTING",
        assigned_role="BUSINESS_ANALYST",
        version="0.1.0",
        confidence_score=0.0,
        health_score=100.0,
        health_status="Healthy",
        open_questions_count=0,
        clarification_cycle_count=0,
        requirement_data={},
    )
    db.add(req)
    db.commit()

    # 3. Dispatch CapabilityRunner in BackgroundTasks
    background_tasks.add_task(
        capability_runner.run_pipeline,
        db=db,
        requirement_id=req.id,
        document_content=parsed_text,
    )

    return IngestResponse(
        document_id=doc.id,
        requirement_id=req.id,
        status="INGESTING",
        message="Document uploaded successfully. AI capability pipeline started in background.",
    )


@router.post(
    "/requirements/ingest-text",
    response_model=IngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest plain text or meeting transcript and start the analysis pipeline",
    tags=["Ingestion"],
)
def ingest_text(
    payload: IngestTextRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_account: Account = Depends(require_role("BUSINESS_ANALYST")),
) -> IngestResponse:
    """
    Accepts direct text or transcript, validates word count, creates Document and Requirement records,
    and dispatches the 6-step CapabilityRunner pipeline in background.
    """
    cleaned_text = payload.text.strip()
    words = cleaned_text.split()
    if not cleaned_text or len(words) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requirement text or transcript is too short (minimum 10 words required). Please provide substantive requirement text.",
        )

    # 0. Ensure Project container exists
    project = db.query(Project).filter(Project.id == payload.project_id).first()
    if not project:
        project = Project(
            id=payload.project_id,
            name="Default Enterprise Project",
            description="Container project for ingested documents and transcripts",
        )
        db.add(project)
        db.commit()

    source_label = (payload.source_type or "TRANSCRIPT").upper()
    title_snippet = payload.title or f"{source_label} - {words[0]} {words[1] if len(words)>1 else ''} {words[2] if len(words)>2 else ''}..."

    # 1. Create Document record for text/transcript
    doc_id = uuid.uuid4()
    doc = Document(
        id=doc_id,
        project_id=payload.project_id,
        file_name=title_snippet,
        file_type=source_label.lower(),
        file_size_bytes=len(cleaned_text.encode('utf-8')),
        normalized_content=cleaned_text,
        word_count=len(words),
        parse_status="SUCCESS",
    )
    db.add(doc)
    db.commit()

    # 2. Create Requirement record
    req_id = uuid.uuid4()
    req = Requirement(
        id=req_id,
        project_id=payload.project_id,
        title=f"Draft: {title_snippet}",
        current_state="INGESTING",
        assigned_role="BUSINESS_ANALYST",
        version="0.1.0",
        confidence_score=0.0,
        health_score=100.0,
        health_status="Healthy",
        open_questions_count=0,
        clarification_cycle_count=0,
        requirement_data={},
    )
    db.add(req)
    db.commit()

    # 3. Dispatch CapabilityRunner in BackgroundTasks
    background_tasks.add_task(
        capability_runner.run_pipeline,
        db=db,
        requirement_id=req.id,
        document_content=cleaned_text,
    )

    return IngestResponse(
        document_id=doc.id,
        requirement_id=req.id,
        status="INGESTING",
        message="Transcript text accepted successfully. AI capability pipeline started in background.",
    )



# ================================================================== #
# Requirements CRUD
# ================================================================== #


@router.get(
    "/requirements",
    response_model=list[RequirementSummary],
    summary="List all requirements for a project",
    tags=["Requirements"],
)
def list_requirements(
    project_id: UUID = Query(...),
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> list[RequirementSummary]:
    """Query requirements filtered by project_id and optional state."""
    query = db.query(Requirement).filter(Requirement.project_id == project_id)
    if state:
        query = query.filter(Requirement.current_state == state)
    return query.order_by(Requirement.updated_at.desc()).all()


@router.get(
    "/requirements/{req_id}",
    response_model=RequirementDetail,
    summary="Fetch a single requirement by UUID",
    tags=["Requirements"],
)
def get_requirement(
    req_id: UUID,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> RequirementDetail:
    """Return the full RequirementObject for the given UUID."""
    req = db.query(Requirement).filter(Requirement.id == req_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement '{req_id}' not found.",
        )
    return req


@router.put(
    "/requirements/{req_id}",
    response_model=RequirementDetail,
    summary="Update requirement content (BA edits)",
    tags=["Requirements"],
)
def update_requirement(
    req_id: UUID,
    payload: RequirementUpdate,
    db: Session = Depends(get_db),
    current_account: Account = Depends(require_role("BUSINESS_ANALYST")),
) -> RequirementDetail:
    """Apply BA edits, snapshot version, and log audit event."""
    req = db.query(Requirement).filter(Requirement.id == req_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement '{req_id}' not found.",
        )

    if req.current_state == "FROZEN":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requirement is FROZEN and locked. Cannot edit content directly.",
        )

    before_data = dict(req.requirement_data or {})

    if payload.title is not None:
        req.title = payload.title
    if payload.requirement_data is not None:
        req.requirement_data = payload.requirement_data

    # Compute JSON diff
    diff = compute_json_diff(before_data, req.requirement_data or {})

    # Create minor version snapshot
    rationale = payload.change_rationale or "BA content update"
    memory_service.create_version_snapshot(
        db, req, change_rationale=rationale, is_major_bump=False
    )

    # Recalculate health score
    new_health, new_status = health_engine.calculate(
        open_questions_count=req.open_questions_count
    )
    req.health_score = new_health
    req.health_status = new_status

    audit_service.log_event(
        db,
        requirement_id=req.id,
        actor_role="BUSINESS_ANALYST",
        action_type="BA_EDIT",
        prev_state=req.current_state,
        new_state=req.current_state,
        change_diff=diff,
    )

    db.commit()
    db.refresh(req)
    return req


# ================================================================== #
# State Machine
# ================================================================== #


@router.post(
    "/requirements/{req_id}/transition",
    response_model=TransitionResponse,
    summary="Transition a requirement to the next lifecycle state",
    tags=["Lifecycle"],
)
def transition_state(
    req_id: UUID,
    payload: TransitionRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> TransitionResponse:
    """Validate transition, update state, and route role assignment."""
    actor = current_account.assigned_role or payload.actor_role or "BUSINESS_ANALYST"
    prev_state = db.query(Requirement.current_state).filter(Requirement.id == req_id).scalar() or "DRAFT"

    updated_req = lifecycle_coordinator.transition_state(
        db=db,
        requirement_id=req_id,
        event=payload.event,
        actor_role=actor,
        rationale=payload.rationale,
    )

    return TransitionResponse(
        requirement_id=updated_req.id,
        previous_state=prev_state,
        new_state=updated_req.current_state,
        assigned_role=updated_req.assigned_role,
    )


# ================================================================== #
# Clarifications
# ================================================================== #


@router.post(
    "/clarifications",
    response_model=ClarificationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a clarification question for a stakeholder",
    tags=["Clarifications"],
)
def create_clarification(
    payload: ClarificationCreate,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ClarificationResponse:
    """Persist clarification question and dispatch notification."""
    req = db.query(Requirement).filter(Requirement.id == payload.requirement_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement '{payload.requirement_id}' not found.",
        )

    clar = Clarification(
        requirement_id=payload.requirement_id,
        question=payload.question,
        assigned_role=payload.assigned_role,
        options=payload.options,
        status="PENDING",
    )
    db.add(clar)

    # Increment open questions count and recalculate health score
    req.open_questions_count = (req.open_questions_count or 0) + 1
    new_health, new_status = health_engine.calculate(
        open_questions_count=req.open_questions_count
    )
    req.health_score = new_health
    req.health_status = new_status

    db.commit()
    db.refresh(clar)

    # Dispatch notification to assigned_role
    notification_service.dispatch_notification(
        db=db,
        recipient_role=payload.assigned_role,
        message=f"New clarification question: {payload.question}",
        notification_type="CLARIFICATION",
        requirement_id=req.id,
    )

    return clar


@router.put(
    "/clarifications/{clarification_id}",
    response_model=ClarificationResponse,
    summary="Submit an answer to a clarification question",
    tags=["Clarifications"],
)
def answer_clarification(
    clarification_id: UUID,
    payload: ClarificationAnswer,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> ClarificationResponse:
    """Mark clarification ANSWERED and recalculate requirement health."""
    clar = db.query(Clarification).filter(Clarification.id == clarification_id).first()
    if not clar:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Clarification '{clarification_id}' not found.",
        )

    clar.answer = payload.answer
    clar.status = "ANSWERED"

    req = db.query(Requirement).filter(Requirement.id == clar.requirement_id).first()
    if req and req.open_questions_count > 0:
        req.open_questions_count -= 1
        new_health, new_status = health_engine.calculate(
            open_questions_count=req.open_questions_count
        )
        req.health_score = new_health
        req.health_status = new_status

    audit_service.log_event(
        db=db,
        requirement_id=clar.requirement_id,
        actor_role=current_account.assigned_role or clar.assigned_role,
        action_type="CLARIFICATION_ANSWERED",
        prev_state=req.current_state if req else None,
        new_state=req.current_state if req else None,
        change_diff={"question": clar.question, "answer": payload.answer},
    )

    db.commit()
    db.refresh(clar)
    return clar


@router.get(
    "/clarifications",
    response_model=list[ClarificationResponse],
    summary="List clarifications pending for a role",
    tags=["Clarifications"],
)
def list_clarifications(
    assigned_role: str = Query(...),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> list[ClarificationResponse]:
    """Return all PENDING clarifications for the given role."""
    return (
        db.query(Clarification)
        .filter(
            Clarification.assigned_role == assigned_role,
            Clarification.status == "PENDING",
        )
        .order_by(Clarification.created_at.desc())
        .all()
    )


# ================================================================== #
# Comments
# ================================================================== #


@router.post(
    "/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a review comment to a requirement element",
    tags=["Comments"],
)
def create_comment(
    payload: CommentCreate,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> CommentResponse:
    """Persist comment linked to target_element_id."""
    comment = Comment(
        requirement_id=payload.requirement_id,
        author_role=current_account.assigned_role or payload.author_role,
        target_element_id=payload.target_element_id,
        comment_text=payload.comment_text,
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    audit_service.log_event(
        db=db,
        requirement_id=payload.requirement_id,
        actor_role=comment.author_role,
        action_type="COMMENT_ADDED",
        change_diff={
            "target_element_id": payload.target_element_id,
            "text": payload.comment_text,
        },
    )

    return comment


@router.get(
    "/comments",
    response_model=list[CommentResponse],
    summary="List all comments for a requirement",
    tags=["Comments"],
)
def list_comments(
    requirement_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> list[CommentResponse]:
    """Return all comments for the given requirement UUID."""
    return (
        db.query(Comment)
        .filter(Comment.requirement_id == requirement_id)
        .order_by(Comment.created_at.asc())
        .all()
    )


# ================================================================== #
# Jira Export  (Jira service integration wired in Phase E)
# ================================================================== #


from app.services.jira import jira_service

@router.post(
    "/requirements/{req_id}/export-jira",
    response_model=JiraExportResponse,
    summary="Export an approved requirement to Jira Cloud",
    tags=["Jira"],
)
def export_to_jira(
    req_id: UUID,
    payload: JiraExportRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(require_role("BUSINESS_ANALYST")),
) -> JiraExportResponse:
    """Export an approved requirement and its user stories to Jira Cloud."""
    return jira_service.export_requirement(
        db=db,
        requirement_id=req_id,
        payload=payload,
        actor_role=current_account.assigned_role or "BUSINESS_ANALYST",
    )


# ================================================================== #
# Version History & Rollback
# ================================================================== #


@router.get(
    "/requirements/{req_id}/history",
    response_model=list[VersionHistoryItem],
    summary="Fetch version history for a requirement",
    tags=["Versioning"],
)
def get_version_history(
    req_id: UUID,
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> list[VersionHistoryItem]:
    """Return ordered list of RequirementVersion rows."""
    return memory_service.get_version_history(db, req_id)


@router.post(
    "/requirements/{req_id}/rollback",
    response_model=RequirementDetail,
    summary="Restore a requirement to a previous version",
    tags=["Versioning"],
)
def rollback_requirement(
    req_id: UUID,
    payload: RollbackRequest,
    db: Session = Depends(get_db),
    current_account: Account = Depends(require_role("BUSINESS_ANALYST")),
) -> RequirementDetail:
    """Restore target version data back to live requirement row."""
    req = db.query(Requirement).filter(Requirement.id == req_id).first()
    if not req:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requirement '{req_id}' not found.",
        )

    prev_state = req.current_state
    restored_req, snapshot = memory_service.rollback_to_version(
        db, req, payload.target_version
    )

    audit_service.log_event(
        db=db,
        requirement_id=req.id,
        actor_role="BUSINESS_ANALYST",
        action_type="ROLLBACK",
        prev_state=prev_state,
        new_state=restored_req.current_state,
        change_diff={
            "restored_to_version": payload.target_version,
            "new_version": snapshot.version,
        },
    )

    db.commit()
    db.refresh(restored_req)
    return restored_req


# ================================================================== #
# Notifications
# ================================================================== #


@router.get(
    "/notifications",
    response_model=list[NotificationResponse],
    summary="Fetch unread notifications for a role",
    tags=["Notifications"],
)
def list_notifications(
    recipient_role: str = Query(...),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> list[NotificationResponse]:
    """Return all unread notifications for the given role."""
    return notification_service.get_unread_notifications(db, recipient_role)


# ================================================================== #
# Dashboard Metrics
# ================================================================== #


@router.get(
    "/dashboard/metrics",
    response_model=DashboardMetrics,
    summary="Aggregate project-level metrics for the BA dashboard",
    tags=["Dashboard"],
)
def get_dashboard_metrics(
    project_id: UUID = Query(...),
    db: Session = Depends(get_db),
    current_account: Account = Depends(get_current_account),
) -> DashboardMetrics:
    """Compute aggregate scores across all project requirements."""
    reqs = db.query(Requirement).filter(Requirement.project_id == project_id).all()
    total = len(reqs)
    if total == 0:
        return DashboardMetrics(
            total_requirements=0,
            frozen_count=0,
            at_risk_count=0,
            blocked_count=0,
            average_confidence=0.0,
            average_health=100.0,
        )

    frozen = sum(1 for r in reqs if r.current_state == "FROZEN")
    at_risk = sum(1 for r in reqs if r.health_status == "At Risk")
    blocked = sum(1 for r in reqs if r.health_status == "Blocked")
    avg_conf = round(sum(r.confidence_score for r in reqs) / total, 2)
    avg_health = round(sum(r.health_score for r in reqs) / total, 2)

    return DashboardMetrics(
        total_requirements=total,
        frozen_count=frozen,
        at_risk_count=at_risk,
        blocked_count=blocked,
        average_confidence=avg_conf,
        average_health=avg_health,
    )

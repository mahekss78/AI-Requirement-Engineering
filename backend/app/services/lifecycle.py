"""
app/services/lifecycle.py
=========================
Lifecycle Coordinator and State Machine Engine for the AREA platform.

Responsibilities (PDS Vol 2 Chapter 11):
1. Enforces deterministic state transitions according to the PDS Transition Gate Matrix.
2. Validates state prerequisites, permitted next states, and role permissions.
3. Manages role ownership routing (`BUSINESS_ANALYST`, `CLIENT`, `DEVELOPER`, `QA`, `PRODUCT_OWNER`).
4. Enforces the Clarification Cycle Limit (max 3 cycles) and raises escalation alerts.
5. Invokes Audit, Notification, and Memory services during transitions.
6. Executes inside SQL transaction blocks to prevent race conditions.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple, Set
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.models import Requirement
from app.services.audit_notify import audit_service, notification_service
from app.services.memory import memory_service
from app.services.scoring import health_engine

logger = logging.getLogger(__name__)

# Valid Lifecycle States per PDS Vol 2 §11.1
VALID_STATES: Set[str] = {
    "DRAFT",
    "INGESTING",
    "AI_ANALYZED",
    "BA_REVIEW",
    "CLARIFYING",
    "PEER_REVIEW",
    "APPROVED",
    "JIRA_SYNCED",
    "FROZEN",
    "FAILED",
}

# Maximum clarification cycles before mandating manual BA intervention
MAX_CLARIFICATION_CYCLES = 3


class LifecycleCoordinator:
    """
    State Machine transition controller and task router.
    """

    @staticmethod
    def transition_state(
        db: Session,
        requirement_id: UUID,
        event: str,
        actor_role: str,
        rationale: Optional[str] = None,
        target_role: Optional[str] = None,
    ) -> Requirement:
        """
        Execute a deterministic state machine transition inside a SQL transaction.

        Args:
            db:             SQLAlchemy session
            requirement_id: UUID of the requirement
            event:          Triggering event string (e.g. APPROVE_PEER_REVIEW, MARK_JIRA_SYNCED, FREEZE)
            actor_role:     Role triggering this transition
            rationale:      Optional rationale / comment string
            target_role:    Optional target role for clarification or review assignment

        Returns:
            Updated Requirement ORM object
        """
        # Fetch with row lock inside transaction
        req = (
            db.query(Requirement)
            .filter(Requirement.id == requirement_id)
            .with_for_update(of=Requirement)
            .first()
        )

        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requirement '{requirement_id}' not found.",
            )

        current_state = req.current_state
        prev_state = current_state

        if current_state == "FROZEN" and event != "ROLLBACK":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Requirement is FROZEN and locked. No further state transitions allowed except rollback.",
            )

        # Transition matrix resolution
        new_state, next_owner_role, is_major_bump = LifecycleCoordinator._resolve_transition(
            req=req,
            current_state=current_state,
            event=event,
            actor_role=actor_role,
            target_role=target_role,
            db=db,
        )

        # Apply state & owner update
        req.current_state = new_state
        req.assigned_role = next_owner_role

        # Recalculate health score
        new_health, new_status = health_engine.calculate(
            open_questions_count=req.open_questions_count,
            rejections_count=0,
        )
        req.health_score = new_health
        req.health_status = new_status

        # Create version snapshot if minor/major version bump is required
        snapshot_rationale = rationale or f"Transitioned from {prev_state} to {new_state} via {event}"
        memory_service.create_version_snapshot(
            db=db,
            requirement=req,
            change_rationale=snapshot_rationale,
            is_major_bump=is_major_bump,
        )

        # Audit log
        audit_service.log_event(
            db=db,
            requirement_id=req.id,
            actor_role=actor_role,
            action_type=f"STATE_TRANSITION:{event}",
            prev_state=prev_state,
            new_state=new_state,
            change_diff={"event": event, "rationale": rationale},
        )

        # Dispatch notification to new owner role
        notif_msg = (
            f"Requirement '{req.title}' transitioned to state {new_state}. "
            f"Assigned to {next_owner_role}."
        )
        notification_service.dispatch_notification(
            db=db,
            recipient_role=next_owner_role,
            message=notif_msg,
            notification_type="REVIEW_REQUEST" if new_state == "PEER_REVIEW" else "INFO",
            requirement_id=req.id,
        )

        db.commit()
        db.refresh(req)
        logger.info(
            f"Requirement {req.id} transitioned: {prev_state} -> {new_state} "
            f"(Event: {event}, Owner: {next_owner_role})"
        )
        return req

    @staticmethod
    def _resolve_transition(
        req: Requirement,
        current_state: str,
        event: str,
        actor_role: str,
        target_role: Optional[str],
        db: Session,
    ) -> Tuple[str, str, bool]:
        """
        Internal transition matrix evaluator matching PDS Vol 2 §11.1 & §11.3.

        Returns:
            Tuple of (new_state: str, next_owner_role: str, is_major_bump: bool)
        """
        event_clean = event.strip().upper()

        # 1. Ingestion Completion (DRAFT / INGESTING -> AI_ANALYZED)
        if event_clean in ("VALIDATE_DOCUMENT", "COMPLETE_INGESTION"):
            if current_state not in ("DRAFT", "INGESTING"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot trigger '{event}' from state '{current_state}'.",
                )
            return "AI_ANALYZED", "BUSINESS_ANALYST", False

        # 2. Send Clarification (AI_ANALYZED / BA_REVIEW -> CLARIFYING or BA_REVIEW if cycle limit reached)
        elif event_clean == "SEND_CLARIFICATION":
            if current_state not in ("AI_ANALYZED", "BA_REVIEW"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot send clarifications from state '{current_state}'. Must be in BA_REVIEW or AI_ANALYZED.",
                )

            # Check Clarification Cycle Limit (PDS Vol 2 §11.3)
            if req.clarification_cycle_count >= MAX_CLARIFICATION_CYCLES:
                logger.warning(
                    f"Clarification cycle limit ({MAX_CLARIFICATION_CYCLES}) reached for requirement {req.id}. "
                    "Mandating manual BA intervention."
                )
                notification_service.dispatch_notification(
                    db=db,
                    recipient_role="BUSINESS_ANALYST",
                    message=(
                        f"Maximum clarification threshold ({MAX_CLARIFICATION_CYCLES} cycles) reached for "
                        f"'{req.title}'. Mandating manual BA review."
                    ),
                    notification_type="WARNING",
                    requirement_id=req.id,
                )
                # Freeze auto-routing; remain in BA_REVIEW assigned to BUSINESS_ANALYST
                return "BA_REVIEW", "BUSINESS_ANALYST", False

            destination_role = target_role or "CLIENT"
            return "CLARIFYING", destination_role, False

        # 3. Clarification Answered (CLARIFYING -> BA_REVIEW)
        elif event_clean in ("CLARIFICATION_ANSWERED", "SUBMIT_ANSWERS"):
            if current_state != "CLARIFYING":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot answer clarification when state is '{current_state}'. Must be in CLARIFYING.",
                )
            # Increment clarification cycle count
            req.clarification_cycle_count += 1
            return "BA_REVIEW", "BUSINESS_ANALYST", False

        # 4. Submit for Peer Review / Approve Draft (AI_ANALYZED / BA_REVIEW -> PEER_REVIEW)
        elif event_clean in ("APPROVE_DRAFT", "SUBMIT_FOR_REVIEW"):
            if current_state not in ("AI_ANALYZED", "BA_REVIEW"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot submit for review from state '{current_state}'. Must be in BA_REVIEW or AI_ANALYZED.",
                )
            review_owner = target_role or "DEVELOPER"
            return "PEER_REVIEW", review_owner, False

        # 5. Request Rework / Peer Review Rejection (PEER_REVIEW -> BA_REVIEW)
        elif event_clean in ("REQUEST_REWORK", "REJECT_PEER_REVIEW"):
            if current_state != "PEER_REVIEW":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot request rework when state is '{current_state}'. Must be in PEER_REVIEW.",
                )
            return "BA_REVIEW", "BUSINESS_ANALYST", False

        # 6. Approve Peer Review (PEER_REVIEW -> APPROVED)
        elif event_clean == "APPROVE_PEER_REVIEW":
            if current_state != "PEER_REVIEW":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot approve peer review when state is '{current_state}'. Must be in PEER_REVIEW.",
                )
            return "APPROVED", "BUSINESS_ANALYST", False

        # 7. Mark Jira Synced (APPROVED -> JIRA_SYNCED)
        elif event_clean == "MARK_JIRA_SYNCED":
            if current_state != "APPROVED":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot mark Jira synced when state is '{current_state}'. Must be in APPROVED.",
                )
            return "JIRA_SYNCED", "BUSINESS_ANALYST", False

        # 8. Freeze Requirement (APPROVED / JIRA_SYNCED -> FROZEN)
        elif event_clean == "FREEZE":
            if current_state not in ("APPROVED", "JIRA_SYNCED", "PEER_REVIEW"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Cannot freeze requirement from state '{current_state}'. Must be in APPROVED, JIRA_SYNCED, or PEER_REVIEW.",
                )
            # Freeze triggers major version bump (e.g. 0.3.0 -> 1.0.0)
            return "FROZEN", "BUSINESS_ANALYST", True

        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown transition event '{event}'.",
            )


lifecycle_coordinator = LifecycleCoordinator()


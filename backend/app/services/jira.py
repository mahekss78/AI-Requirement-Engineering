"""
app/services/jira.py
====================
Real Jira Cloud REST API Integration Service.

Responsibilities:
1. Validates Jira domain, email, API token, and project key configuration.
2. Performs connectivity checks against Jira Cloud API v3 (`GET /rest/api/3/project/{project_key}`).
3. Enforces Human Approval Gate: Export is ONLY permitted from states `APPROVED` or `JIRA_SYNCED`.
4. Idempotency: Prevents duplicate Jira issue creation if requirement is exported multiple times.
5. Requirement -> Jira Mapping: Maps AREA Requirement & User Stories to Jira Epic & Story issues.
6. Database Persistence: Stores `jira_epic_key`, `jira_epic_url`, `jira_story_keys`, and `jira_synced_at` in `Requirement.requirement_data`.
7. Transitions Requirement state to `JIRA_SYNCED`.
8. Logs AuditLog (`JIRA_EXPORT_SUCCESS` / `JIRA_EXPORT_FAILED`) and sends Notification.
9. Redacts secrets: NEVER logs, prints, or exposes Jira API token or authorization headers.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.models.models import Requirement
from app.schemas.schemas import JiraExportRequest, JiraExportResponse
from app.services.audit_notify import audit_service, notification_service
from app.services.lifecycle import lifecycle_coordinator

logger = logging.getLogger(__name__)


class JiraServiceError(Exception):
    """Custom exception for Jira integration failures with sanitized messages."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class JiraService:
    """
    Manages REST integration with Jira Cloud API v3.
    """

    @staticmethod
    def _clean_domain(domain: str) -> str:
        """Strip http://, https://, and trailing slashes from domain string."""
        clean = domain.strip().lower()
        if clean.startswith("https://"):
            clean = clean[8:]
        elif clean.startswith("http://"):
            clean = clean[7:]
        return clean.rstrip("/")

    @classmethod
    def get_config(cls, request_payload: Optional[JiraExportRequest] = None) -> Tuple[str, str, str, str]:
        """
        Extract and validate Jira configuration.
        Returns (domain, email, api_token, project_key).
        Raises HTTPException HTTP 400 if configuration is missing.
        """
        payload = request_payload or JiraExportRequest()
        domain = cls._clean_domain(payload.jira_domain or settings.JIRA_DOMAIN)
        email = (payload.jira_email or settings.JIRA_EMAIL).strip()
        api_token = settings.JIRA_API_TOKEN.strip()
        project_key = (payload.project_key or settings.JIRA_PROJECT_KEY).strip().upper()

        if not domain or not email or not api_token or not project_key:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Jira configuration incomplete. Ensure JIRA_DOMAIN, JIRA_EMAIL, "
                    "JIRA_API_TOKEN, and JIRA_PROJECT_KEY are configured in backend/.env."
                ),
            )

        return domain, email, api_token, project_key

    @classmethod
    def validate_connection(cls, domain: str, email: str, api_token: str, project_key: str) -> bool:
        """
        Verify Jira Cloud API authentication and project existence via REST API v3.
        """
        url = f"https://{domain}/rest/api/3/project/{project_key}"
        auth = (email, api_token)

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(url, auth=auth, headers={"Accept": "application/json"})

            if response.status_code == 200:
                logger.info(f"Jira connection verified for project '{project_key}' on {domain}.")
                return True
            elif response.status_code == 401:
                raise JiraServiceError("Jira authentication failed. Check JIRA_EMAIL and JIRA_API_TOKEN.", status_code=401)
            elif response.status_code == 404:
                raise JiraServiceError(f"Jira project '{project_key}' not found on domain '{domain}'.", status_code=404)
            else:
                raise JiraServiceError(f"Jira API returned HTTP {response.status_code}: {response.text[:200]}")

        except httpx.TimeoutException:
            raise JiraServiceError("Jira connection timed out after 10 seconds.", status_code=504)
        except httpx.RequestError as exc:
            raise JiraServiceError(f"Jira connection network error: {type(exc).__name__}", status_code=502)

    @classmethod
    def export_requirement(
        cls,
        db: Session,
        requirement_id: UUID,
        payload: Optional[JiraExportRequest] = None,
        actor_role: str = "BUSINESS_ANALYST",
    ) -> JiraExportResponse:
        """
        Export an approved AREA requirement to Jira Cloud.

        Workflow:
        1. Validates configuration and connection.
        2. Human Approval Gate: Verifies requirement is in state APPROVED or JIRA_SYNCED.
        3. Idempotency Check: Returns existing Jira mapping if already exported.
        4. Creates Jira Epic & Story issues via REST API.
        5. Persists Jira mapping in requirement_data.
        6. Transitions state to JIRA_SYNCED (if currently APPROVED).
        7. Logs AuditLog and dispatches Notification.
        """
        domain, email, api_token, project_key = cls.get_config(payload)

        # Fetch Requirement
        req = db.query(Requirement).filter(Requirement.id == requirement_id).first()
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Requirement '{requirement_id}' not found.",
            )

        # 2. Human Approval Gate
        if req.current_state not in ("APPROVED", "JIRA_SYNCED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Requirement state is '{req.current_state}'. "
                    "Jira export requires human approval (state APPROVED or JIRA_SYNCED)."
                ),
            )

        req_data = dict(req.requirement_data or {})

        # 3. Idempotency Check (Duplicate Export Prevention)
        existing_epic_key = req_data.get("jira_epic_key")
        if existing_epic_key:
            epic_url = req_data.get("jira_epic_url") or f"https://{domain}/browse/{existing_epic_key}"
            story_keys = req_data.get("jira_story_keys", [])
            logger.info(f"Requirement {req.id} already exported to Jira (Epic: {existing_epic_key}). Returning existing mapping.")
            return JiraExportResponse(
                status="already_synced",
                jira_epic_key=existing_epic_key,
                jira_epic_url=epic_url,
                jira_story_count=len(story_keys),
                message=f"Requirement already exported to Jira (Epic: {existing_epic_key}). Duplicate creation skipped.",
            )

        # 4. Connection Test
        cls.validate_connection(domain, email, api_token, project_key)

        # 5. Issue Creation via Jira REST API v3
        auth = (email, api_token)
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        base_url = f"https://{domain}/rest/api/3/issue"

        summary_title = f"[AREA-{str(req.id)[:8]}] {req.title}"
        metadata = req_data.get("metadata", {})
        summary_desc = metadata.get("summary") or req.title

        # Epic Payload (Atlassian Document Format ADF for v3 API)
        epic_adf = {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {"type": "text", "text": f"AREA Requirement ID: {req.id}\nVersion: v{req.version}\n\nSummary:\n{summary_desc}"}
                    ],
                }
            ],
        }

        epic_payload = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary_title,
                "description": epic_adf,
                "issuetype": {"name": "Epic"},
            }
        }

        try:
            with httpx.Client(timeout=15.0) as client:
                res = client.post(base_url, json=epic_payload, auth=auth, headers=headers)

                # Fallback if "Epic" issuetype name is different (e.g. "Task")
                if res.status_code == 400 and "issuetype" in res.text:
                    logger.warning("Jira 'Epic' issuetype rejected; retrying with 'Task'")
                    epic_payload["fields"]["issuetype"] = {"name": "Task"}
                    res = client.post(base_url, json=epic_payload, auth=auth, headers=headers)

                if res.status_code not in (200, 201):
                    error_msg = f"Jira issue creation failed (HTTP {res.status_code}): {res.text[:200]}"
                    cls._log_failed_export(db, req, actor_role, error_msg)
                    raise JiraServiceError(error_msg, status_code=res.status_code)

                epic_data = res.json()
                created_epic_key = epic_data["key"]
                created_epic_id = epic_data["id"]
                epic_url = f"https://{domain}/browse/{created_epic_key}"

                # Create Stories for each User Story
                user_stories = req_data.get("user_stories", []) or req_data.get("structuring", {}).get("user_stories", [])
                created_story_keys = []

                for us in user_stories:
                    us_id = us.get("id") or "US"
                    us_title = f"[{created_epic_key}] {us_id}: As a {us.get('role', 'user')}, I want {us.get('action', '')}"
                    
                    # Format acceptance criteria
                    ac_text = "\n".join([
                        f"GIVEN {ac.get('given')}\nWHEN {ac.get('when')}\nTHEN {ac.get('then')}"
                        for ac in us.get("acceptance_criteria", [])
                    ])
                    
                    story_adf = {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [
                                    {"type": "text", "text": f"Benefit: {us.get('benefit', '')}\n\nAcceptance Criteria:\n{ac_text}"}
                                ],
                            }
                        ],
                    }

                    story_payload = {
                        "fields": {
                            "project": {"key": project_key},
                            "summary": us_title[:250],
                            "description": story_adf,
                            "issuetype": {"name": "Story"},
                            "parent": {"key": created_epic_key},  # Link story to Epic
                        }
                    }

                    st_res = client.post(base_url, json=story_payload, auth=auth, headers=headers)
                    if st_res.status_code not in (200, 201) and "parent" in st_res.text:
                        logger.warning("Jira parent key rejected for Story; retrying without parent link")
                        del story_payload["fields"]["parent"]
                        st_res = client.post(base_url, json=story_payload, auth=auth, headers=headers)
                    if st_res.status_code not in (200, 201) and "issuetype" in st_res.text:
                        story_payload["fields"]["issuetype"] = {"name": "Task"}
                        st_res = client.post(base_url, json=story_payload, auth=auth, headers=headers)

                    if st_res.status_code in (200, 201):
                        st_data = st_res.json()
                        created_story_keys.append(st_data["key"])
                        logger.info(f"Created Jira Story {st_data['key']} linked to Epic {created_epic_key}")
                    else:
                        logger.warning(f"Jira Story creation failed (HTTP {st_res.status_code}): {st_res.text[:200]}")

        except JiraServiceError:
            raise
        except Exception as exc:
            err_text = f"Jira REST request unexpected failure: {type(exc).__name__}"
            cls._log_failed_export(db, req, actor_role, err_text)
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=err_text)

        # 6. Database Persistence
        now_iso = datetime.now(timezone.utc).isoformat()
        req_data["jira_epic_key"] = created_epic_key
        req_data["jira_epic_id"] = created_epic_id
        req_data["jira_epic_url"] = epic_url
        req_data["jira_story_keys"] = created_story_keys
        req_data["jira_project_key"] = project_key
        req_data["jira_synced_at"] = now_iso

        req.requirement_data = req_data

        # 7. Lifecycle State Transition (APPROVED -> JIRA_SYNCED)
        if req.current_state == "APPROVED":
            lifecycle_coordinator.transition_state(
                db=db,
                requirement_id=req.id,
                event="MARK_JIRA_SYNCED",
                actor_role=actor_role,
                rationale=f"Exported to Jira Cloud (Epic: {created_epic_key})",
            )
        else:
            db.commit()
            db.refresh(req)

        # Audit Log & Notification
        audit_service.log_event(
            db=db,
            requirement_id=req.id,
            actor_role=actor_role,
            action_type="JIRA_EXPORT_SUCCESS",
            prev_state="APPROVED",
            new_state=req.current_state,
            change_diff={
                "jira_epic_key": created_epic_key,
                "jira_story_count": len(created_story_keys),
                "jira_project_key": project_key,
            },
        )

        notification_service.dispatch_notification(
            db=db,
            recipient_role=actor_role,
            message=f"Requirement '{req.title}' exported to Jira Cloud (Epic: {created_epic_key}).",
            notification_type="INFO",
            requirement_id=req.id,
        )

        return JiraExportResponse(
            status="success",
            jira_epic_key=created_epic_key,
            jira_epic_url=epic_url,
            jira_story_count=len(created_story_keys),
            message=f"Successfully exported requirement to Jira Cloud (Epic: {created_epic_key}).",
        )

    @classmethod
    def _log_failed_export(cls, db: Session, req: Requirement, actor_role: str, error_msg: str) -> None:
        """Helper to log failed export audit and dispatch warning notification."""
        audit_service.log_event(
            db=db,
            requirement_id=req.id,
            actor_role=actor_role,
            action_type="JIRA_EXPORT_FAILED",
            prev_state=req.current_state,
            new_state=req.current_state,
            change_diff={"error": error_msg},
        )
        notification_service.dispatch_notification(
            db=db,
            recipient_role=actor_role,
            message=f"Jira export failed for requirement '{req.title}': {error_msg[:100]}",
            notification_type="WARNING",
            requirement_id=req.id,
        )
        db.commit()


jira_service = JiraService()

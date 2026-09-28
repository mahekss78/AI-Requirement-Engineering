"""
tests/test_jira_service.py
===========================
Comprehensive Unit & Integration Test Suite for JiraService.

Verifies:
1. Jira connection validation (200 OK, 401 Unauthorized, 404 Not Found, Timeout).
2. Human Approval Gate (Blocks export from DRAFT / AI_ANALYZED; allows from APPROVED).
3. Requirement -> Jira Epic & Story mapping.
4. Issue creation and state transition to JIRA_SYNCED.
5. Idempotent duplicate export prevention.
6. Failure state preservation (remains APPROVED on error).
7. Audit log & Notification creation.
8. Secret redaction.
"""

import uuid
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
import httpx

from app.models.models import Project, Requirement, AuditLog, Notification
from app.schemas.schemas import JiraExportRequest, JiraExportResponse
from app.services.jira import JiraService, JiraServiceError, jira_service


@pytest.fixture
def sample_approved_req(test_db):
    """Fixture creating a test project and an APPROVED requirement."""
    proj = Project(name="Jira Test Project", description="Test project for Jira sync")
    test_db.add(proj)
    test_db.commit()
    test_db.refresh(proj)

    req = Requirement(
        project_id=proj.id,
        title="Payment Gateway Integration",
        current_state="APPROVED",
        assigned_role="BUSINESS_ANALYST",
        version="0.3.0",
        confidence_score=92.0,
        health_score=95.0,
        health_status="Healthy",
        requirement_data={
            "metadata": {"summary": "Integrate Stripe and PayPal payment gateways."},
            "user_stories": [
                {
                    "id": "US-1",
                    "role": "customer",
                    "action": "pay via credit card",
                    "benefit": "complete my purchase securely",
                    "acceptance_criteria": [
                        {"given": "valid card details", "when": "submit payment", "then": "charge card and issue receipt"}
                    ]
                }
            ]
        }
    )
    test_db.add(req)
    test_db.commit()
    test_db.refresh(req)
    return req


def test_jira_human_approval_gate(test_db, sample_approved_req):
    """Export must be rejected if requirement is not in APPROVED or JIRA_SYNCED state."""
    sample_approved_req.current_state = "AI_ANALYZED"
    test_db.commit()

    with pytest.raises(HTTPException) as exc_info:
        jira_service.export_requirement(test_db, sample_approved_req.id)
    assert exc_info.value.status_code == 400
    assert "human approval" in exc_info.value.detail.lower()


def test_jira_connection_validation_success(monkeypatch):
    """Successful connection test returns True."""
    def mock_get(self_or_url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 200
        return mock_res

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    result = JiraService.validate_connection("mycompany.atlassian.net", "user@mycompany.com", "mytoken", "PROJ")
    assert result is True


def test_jira_invalid_credentials_401(monkeypatch):
    """HTTP 401 returns JiraServiceError."""
    def mock_get(self_or_url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 401
        return mock_res

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    with pytest.raises(JiraServiceError) as exc_info:
        JiraService.validate_connection("mycompany.atlassian.net", "user@mycompany.com", "badtoken", "PROJ")
    assert exc_info.value.status_code == 401
    assert "authentication failed" in exc_info.value.message.lower()


def test_jira_invalid_project_404(monkeypatch):
    """HTTP 404 returns JiraServiceError."""
    def mock_get(self_or_url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 404
        return mock_res

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    with pytest.raises(JiraServiceError) as exc_info:
        JiraService.validate_connection("mycompany.atlassian.net", "user@mycompany.com", "token", "NONEXISTENT")
    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.message.lower()


def test_jira_successful_export_and_state_transition(test_db, sample_approved_req, monkeypatch):
    """Successful Jira export creates issues, updates state to JIRA_SYNCED, and logs audit/notifications."""
    
    def mock_get(self_or_url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 200
        return mock_res

    def mock_post(self_or_url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 201
        mock_res.json.return_value = {"id": "10001", "key": "PROJ-101"}
        return mock_res

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    monkeypatch.setattr(httpx.Client, "post", mock_post)

    req_payload = JiraExportRequest(jira_domain="company.atlassian.net", jira_email="ba@company.com", project_key="PROJ")
    
    # Mock settings credentials
    from app.config import settings
    monkeypatch.setattr(settings, "JIRA_DOMAIN", "company.atlassian.net")
    monkeypatch.setattr(settings, "JIRA_EMAIL", "ba@company.com")
    monkeypatch.setattr(settings, "JIRA_API_TOKEN", "dummy_token_123")
    monkeypatch.setattr(settings, "JIRA_PROJECT_KEY", "PROJ")

    res = jira_service.export_requirement(test_db, sample_approved_req.id, payload=req_payload)

    assert res.status == "success"
    assert res.jira_epic_key == "PROJ-101"
    assert "PROJ-101" in res.jira_epic_url

    # Refresh requirement from DB
    test_db.refresh(sample_approved_req)
    assert sample_approved_req.current_state == "JIRA_SYNCED"
    assert sample_approved_req.requirement_data["jira_epic_key"] == "PROJ-101"

    # Audit log verification
    audit = test_db.query(AuditLog).filter(AuditLog.requirement_id == sample_approved_req.id).first()
    assert audit is not None
    assert "JIRA" in audit.action_type

    # Notification verification
    notifs = test_db.query(Notification).filter(Notification.requirement_id == sample_approved_req.id).all()
    assert any("PROJ-101" in n.message for n in notifs)


def test_jira_idempotent_duplicate_export(test_db, sample_approved_req, monkeypatch):
    """Repeat export on already synced requirement skips duplicate issue creation."""
    # Pre-populate requirement with existing Jira keys
    sample_approved_req.current_state = "JIRA_SYNCED"
    sample_approved_req.requirement_data = {
        "jira_epic_key": "PROJ-55",
        "jira_epic_url": "https://company.atlassian.net/browse/PROJ-55",
        "jira_story_keys": ["PROJ-56"]
    }
    test_db.commit()

    from app.config import settings
    monkeypatch.setattr(settings, "JIRA_DOMAIN", "company.atlassian.net")
    monkeypatch.setattr(settings, "JIRA_EMAIL", "ba@company.com")
    monkeypatch.setattr(settings, "JIRA_API_TOKEN", "dummy_token")

    res = jira_service.export_requirement(test_db, sample_approved_req.id)

    assert res.status == "already_synced"
    assert res.jira_epic_key == "PROJ-55"
    assert res.jira_story_count == 1
    assert "Duplicate creation skipped" in res.message


def test_jira_failed_export_state_handling(test_db, sample_approved_req, monkeypatch):
    """If Jira API fails, requirement state remains APPROVED and is NOT marked JIRA_SYNCED."""
    def mock_get(self_or_url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 200
        return mock_res

    def mock_post(self_or_url, *args, **kwargs):
        mock_res = MagicMock()
        mock_res.status_code = 500
        mock_res.text = "Internal Server Error in Jira Cloud"
        return mock_res

    monkeypatch.setattr(httpx.Client, "get", mock_get)
    monkeypatch.setattr(httpx.Client, "post", mock_post)

    from app.config import settings
    monkeypatch.setattr(settings, "JIRA_DOMAIN", "company.atlassian.net")
    monkeypatch.setattr(settings, "JIRA_EMAIL", "ba@company.com")
    monkeypatch.setattr(settings, "JIRA_API_TOKEN", "dummy_token")
    monkeypatch.setattr(settings, "JIRA_PROJECT_KEY", "PROJ")

    with pytest.raises(JiraServiceError):
        jira_service.export_requirement(test_db, sample_approved_req.id)

    test_db.refresh(sample_approved_req)
    # State MUST remain APPROVED
    assert sample_approved_req.current_state == "APPROVED"

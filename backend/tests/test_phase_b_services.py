"""
tests/test_phase_b_services.py
===============================
Phase B unit and integration tests:
1. Confidence & Health Scoring Engines
2. Requirement Lifecycle State Machine & Clarification Cycle Gating
3. Requirement Memory, Versioning, JSON Diffs, and Rollbacks
4. Audit Logging & Notification Queueing
5. Backend Authorization Enforcement
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.models import Account, Project, Requirement, RequirementVersion
from app.services.audit_notify import audit_service, notification_service
from app.services.lifecycle import lifecycle_coordinator
from app.services.memory import compute_json_diff, memory_service
from app.services.scoring import confidence_engine, health_engine
from main import app

client = TestClient(app)


# ------------------------------------------------------------------ #
# 1. Scoring Engines Tests
# ------------------------------------------------------------------ #


def test_confidence_scoring_formula():
    # Weights: comp:0.30, clar:0.20, cons:0.20, test:0.15, trac:0.15
    score, breakdown = confidence_engine.calculate(
        completeness=100.0,
        clarity=80.0,
        consistency=80.0,
        testability=60.0,
        traceability=60.0,
    )
    # Expected: (0.3*100) + (0.2*80) + (0.2*80) + (0.15*60) + (0.15*60) = 30 + 16 + 16 + 9 + 9 = 80.0
    assert score == 80.0
    assert breakdown["completeness"] == 100.0
    assert breakdown["clarity"] == 80.0
    assert breakdown["testability"] == 60.0

    # Test clamping out-of-bounds inputs
    clamp_score, _ = confidence_engine.calculate(completeness=150.0, clarity=-20.0)
    # completeness clamped to 100, clarity clamped to 0 -> 0.30*100 = 30.0
    assert clamp_score == 30.0


def test_health_scoring_formula_and_labels():
    # Healthy: 100.0 (no penalties)
    score1, label1 = health_engine.calculate(open_questions_count=0)
    assert score1 == 100.0
    assert label1 == "Healthy"

    # Needs Review: 1 open question (-5.0), 1 rejection (-10.0) -> 85.0
    score2, label2 = health_engine.calculate(open_questions_count=1, rejections_count=1)
    assert score2 == 85.0
    assert label2 == "Needs Review"

    # At Risk: 3 open questions (-15.0), 2 rejections (-20.0) -> 65.0
    score3, label3 = health_engine.calculate(open_questions_count=3, rejections_count=2)
    assert score3 == 65.0
    assert label3 == "At Risk"

    # Blocked: 5 open questions (-25.0), 3 rejections (-30.0), delay (-15.0) -> 30.0
    score4, label4 = health_engine.calculate(
        open_questions_count=5, rejections_count=3, peer_review_duration_hours=50.0
    )
    assert score4 == 30.0
    assert label4 == "Blocked"


# ------------------------------------------------------------------ #
# 2. Lifecycle State Machine Tests
# ------------------------------------------------------------------ #


def test_lifecycle_valid_transitions(test_db: Session):
    # Setup test project & requirement
    proj = Project(name="Test Proj", description="TP")
    test_db.add(proj)
    test_db.commit()

    req = Requirement(
        project_id=proj.id,
        title="Test Feature",
        current_state="INGESTING",
        assigned_role="SYSTEM",
    )
    test_db.add(req)
    test_db.commit()

    # 1. INGESTING -> AI_ANALYZED
    req1 = lifecycle_coordinator.transition_state(
        test_db, req.id, event="COMPLETE_INGESTION", actor_role="SYSTEM"
    )
    assert req1.current_state == "AI_ANALYZED"
    assert req1.assigned_role == "BUSINESS_ANALYST"

    # 2. AI_ANALYZED -> PEER_REVIEW
    req2 = lifecycle_coordinator.transition_state(
        test_db, req.id, event="APPROVE_DRAFT", actor_role="BUSINESS_ANALYST"
    )
    assert req2.current_state == "PEER_REVIEW"
    assert req2.assigned_role == "DEVELOPER"

    # 3. PEER_REVIEW -> APPROVED
    req3 = lifecycle_coordinator.transition_state(
        test_db, req.id, event="APPROVE_PEER_REVIEW", actor_role="DEVELOPER"
    )
    assert req3.current_state == "APPROVED"
    assert req3.assigned_role == "BUSINESS_ANALYST"

    # 4. APPROVED -> JIRA_SYNCED
    req4 = lifecycle_coordinator.transition_state(
        test_db, req.id, event="MARK_JIRA_SYNCED", actor_role="BUSINESS_ANALYST"
    )
    assert req4.current_state == "JIRA_SYNCED"
    assert req4.assigned_role == "BUSINESS_ANALYST"

    # 5. JIRA_SYNCED -> FROZEN
    req5 = lifecycle_coordinator.transition_state(
        test_db, req.id, event="FREEZE", actor_role="BUSINESS_ANALYST"
    )
    assert req5.current_state == "FROZEN"
    assert req5.assigned_role == "BUSINESS_ANALYST"
    assert req5.version == "1.0.0"  # Major version bump on freeze


def test_lifecycle_invalid_transition(test_db: Session):
    proj = Project(name="Invalid Transition Proj", description="ITP")
    test_db.add(proj)
    test_db.commit()

    req = Requirement(
        project_id=proj.id,
        title="Invalid Transition Req",
        current_state="DRAFT",
        assigned_role="BUSINESS_ANALYST",
    )
    test_db.add(req)
    test_db.commit()

    # Attempt invalid direct transition DRAFT -> JIRA_SYNCED (Must be APPROVED first)
    with pytest.raises(Exception) as exc_info:
        lifecycle_coordinator.transition_state(
            test_db, req.id, event="MARK_JIRA_SYNCED", actor_role="BUSINESS_ANALYST"
        )
    assert "Cannot mark Jira synced" in str(exc_info.value.detail)

    # Attempt invalid direct transition DRAFT -> APPROVED (Must be in PEER_REVIEW first)
    with pytest.raises(Exception) as exc_info2:
        lifecycle_coordinator.transition_state(
            test_db, req.id, event="APPROVE_PEER_REVIEW", actor_role="DEVELOPER"
        )
    assert "Cannot approve peer review" in str(exc_info2.value.detail)



def test_lifecycle_clarification_cycle_limit_escalation(test_db: Session):
    proj = Project(name="Escalation Proj", description="EP")
    test_db.add(proj)
    test_db.commit()

    req = Requirement(
        project_id=proj.id,
        title="Escalation Req",
        current_state="BA_REVIEW",
        assigned_role="BUSINESS_ANALYST",
        clarification_cycle_count=3,  # Reached max threshold
        open_questions_count=1,
    )
    test_db.add(req)
    test_db.commit()

    # Trigger SEND_CLARIFICATION when cycle count is 3
    req_updated = lifecycle_coordinator.transition_state(
        test_db, req.id, event="SEND_CLARIFICATION", actor_role="BUSINESS_ANALYST"
    )

    # State MUST remain in BA_REVIEW assigned to BUSINESS_ANALYST
    assert req_updated.current_state == "BA_REVIEW"
    assert req_updated.assigned_role == "BUSINESS_ANALYST"

    # Escalation warning notification MUST be created for BA
    notifs = notification_service.get_unread_notifications(test_db, "BUSINESS_ANALYST")
    assert len(notifs) > 0
    assert any("Maximum clarification threshold" in n.message for n in notifs)


# ------------------------------------------------------------------ #
# 3. Memory & Versioning Tests
# ------------------------------------------------------------------ #


def test_memory_version_snapshots_and_diffs(test_db: Session):
    proj = Project(name="Memory Proj", description="MP")
    test_db.add(proj)
    test_db.commit()

    req = Requirement(
        project_id=proj.id,
        title="Initial Title",
        current_state="BA_REVIEW",
        version="0.1.0",
        requirement_data={"overview": "Original description"},
    )
    test_db.add(req)
    test_db.commit()

    # Initial snapshot
    v1 = memory_service.create_version_snapshot(
        test_db, req, change_rationale="Initial creation", is_major_bump=False
    )
    assert v1.version == "0.2.0"
    assert req.version == "0.2.0"

    # Compute JSON diff
    before = {"overview": "Original description"}
    after = {"overview": "Updated description", "new_field": True}
    diff = compute_json_diff(before, after)
    assert "new_field" in diff["added"]
    assert "overview" in diff["modified"]


def test_memory_version_rollback(test_db: Session):
    proj = Project(name="Rollback Proj", description="RP")
    test_db.add(proj)
    test_db.commit()

    req = Requirement(
        project_id=proj.id,
        title="Rollback Feature",
        current_state="BA_REVIEW",
        version="0.1.0",
        requirement_data={"v": 1},
    )
    test_db.add(req)
    test_db.commit()

    # Save version 0.2.0
    memory_service.create_version_snapshot(test_db, req, change_rationale="V1 Data")

    # Modify to version 0.3.0
    req.requirement_data = {"v": 2}
    memory_service.create_version_snapshot(test_db, req, change_rationale="V2 Data")
    assert req.version == "0.3.0"

    # Rollback to version 0.2.0
    restored_req, snapshot = memory_service.rollback_to_version(
        test_db, req, target_version_str="0.2.0"
    )
    assert restored_req.requirement_data == {"v": 1}
    assert snapshot.version == "0.4.0"
    assert "Rollback restored content to version 0.2.0" in snapshot.change_rationale


# ------------------------------------------------------------------ #
# 4. Audit & Notification Tests
# ------------------------------------------------------------------ #


def test_audit_and_notification_services(test_db: Session):
    proj = Project(name="Audit Proj", description="AP")
    test_db.add(proj)
    test_db.commit()

    req = Requirement(project_id=proj.id, title="Audit Req", current_state="BA_REVIEW")
    test_db.add(req)
    test_db.commit()

    # Test audit logging
    log_entry = audit_service.log_event(
        test_db,
        requirement_id=req.id,
        actor_role="BUSINESS_ANALYST",
        action_type="BA_EDIT",
        prev_state="BA_REVIEW",
        new_state="BA_REVIEW",
        change_diff={"field": "value"},
    )
    assert log_entry.id is not None
    assert log_entry.action_type == "BA_EDIT"
    assert log_entry.change_diff == {"field": "value"}

    # Test notification dispatch & retrieval
    notif = notification_service.dispatch_notification(
        test_db,
        recipient_role="DEVELOPER",
        message="Review requested for US-1",
        notification_type="REVIEW_REQUEST",
        requirement_id=req.id,
    )
    assert notif.id is not None
    assert notif.is_read is False

    unread = notification_service.get_unread_notifications(test_db, "DEVELOPER")
    assert len(unread) == 1
    assert unread[0].message == "Review requested for US-1"


# ------------------------------------------------------------------ #
# 5. Backend Authorization Integration Tests
# ------------------------------------------------------------------ #


def test_protected_endpoints_require_authentication(test_db: Session):
    fresh_client = TestClient(app)

    # Calling requirement detail without session cookie -> 401 Unauthorized
    resp = fresh_client.get("/api/requirements/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 401


def test_role_restricted_operations(test_db: Session):
    c = TestClient(app)
    # Register developer account
    c.post(
        "/api/auth/register",
        json={"email": "dev@xyz.com", "password": "password123"},
    )
    c.post("/api/auth/role", json={"role": "DEVELOPER"})

    # Attempting BA-restricted update_requirement as DEVELOPER -> 403 Forbidden
    resp = c.put(
        "/api/requirements/00000000-0000-0000-0000-000000000000",
        json={"title": "Unauthorized Edit"},
    )
    assert resp.status_code == 403
    assert "DEVELOPER" in resp.json()["detail"]

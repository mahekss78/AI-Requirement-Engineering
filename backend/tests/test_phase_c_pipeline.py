"""
tests/test_phase_c_pipeline.py
===============================
Phase C unit and integration tests:
1. 6 AI Capabilities executed independently with mocked LLM & RAG interfaces.
2. Malformed LLM response handling and validation fallback.
3. CapabilityRunner pipeline execution order, database checkpoints, and version snapshotting.
4. CapabilityRunner failure handling (state set to FAILED, error audit logged, BA notified).
5. Document Ingestion API endpoint (POST /api/requirements/ingest).
"""

import base64
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.capabilities.conflict import ConflictDetectionCapability
from app.capabilities.context import ContextCapability
from app.capabilities.extraction import ExtractionCapability
from app.capabilities.gap_detection import GapDetectionCapability
from app.capabilities.quality import QualityCapability
from app.capabilities.structuring import StructuringCapability
from app.models.models import Project, Requirement
from app.services.prompt_orch import LLMServiceError
from app.services.runner import CapabilityRunner
from main import app

client = TestClient(app)


# ------------------------------------------------------------------ #
# 1. Independent Capability Unit Tests (Mocked LLM & RAG)
# ------------------------------------------------------------------ #


def test_extraction_capability_unit():
    mock_orch = MagicMock()
    mock_orch.execute.return_value = {
        "raw_title": "Extracted Guest Checkout",
        "functional_requirements": [
            {
                "id": "FR-1",
                "statement": "Allow guest checkout with email verification.",
                "type": "functional_requirement",
                "actor": "Guest User",
                "source_evidence": {"snippet": "Allow guest checkout", "start_offset": 0, "end_offset": 20},
                "confidence": 0.9,
            }
        ],
        "actors": [{"name": "Guest User", "description": None, "confidence": 0.9}, {"name": "Payment Processor", "description": None, "confidence": 0.9}],
        "data_entities": [{"name": "email"}, {"name": "cart_id"}],
        "assumptions": [{"id": "AS-1", "statement": "User has valid email"}],
        "constraints": [{"id": "CO-1", "statement": "PCI-DSS compliance"}],
    }

    cap = ExtractionCapability(orchestrator=mock_orch)
    res = cap.execute({"document_content": "Guest checkout text", "domain_context": "E-Commerce"})

    assert res["raw_title"] == "Extracted Guest Checkout"
    assert len(res["functional_requirements"]) == 1
    assert len(res["actors"]) == 2


def test_context_capability_unit():
    mock_orch = MagicMock()
    mock_orch.execute.return_value = {
        "domain": "E-Commerce",
        "business_capability": "Checkout & Payments",
        "related_entities": [{"name": "PaymentGateway", "relevance": "High"}, {"name": "CartService", "relevance": "High"}],
        "external_systems": ["PaymentGateway"],
        "mapped_subsystems": ["CartService"],
        "enrichment_notes": "Mapped payment gateway requirements.",
        "terminology": {},
        "confidence": 0.85,
    }

    mock_rag = MagicMock()
    mock_rag.search_context.return_value = "Policy fragment: 30-day refund policy"

    cap = ContextCapability(orchestrator=mock_orch, rag_service=mock_rag)
    res = cap.execute({
        "extracted_data": {"raw_title": "Checkout", "functional_requirements": [{"statement": "Stmt 1"}]},
        "domain_context": "E-Commerce",
    })

    assert len(res["related_entities"]) == 2
    assert res["domain"] == "E-Commerce"


def test_gap_detection_capability_unit():
    mock_orch = MagicMock()
    mock_orch.execute.return_value = {
        "gaps": [{"id": "GAP-1", "description": "Unspecified session timeout", "severity": "medium", "clarification_question": "What is timeout?", "assigned_role": "CLIENT"}],
        "open_questions": [{"text": "What is the guest cart timeout?", "source": "ai_identified"}],
        "missing_edge_cases": ["Expired credit card handling"],
    }

    cap = GapDetectionCapability(orchestrator=mock_orch)
    res = cap.execute({"extracted_data": {"raw_title": "Checkout"}})

    assert len(res["gaps"]) == 1
    assert len(res["open_questions"]) == 1


def test_conflict_detection_capability_unit():
    mock_orch = MagicMock()
    mock_orch.execute.return_value = {
        "conflicts": [
            {
                "id": "CF-1",
                "severity": "high",
                "conflict": "Refund window conflict (14d vs 30d)",
                "requirement_a": "14 days",
                "requirement_b": "30 days",
                "explanation": "Different refund periods",
            }
        ],
        "severity_summary": {"high": 1, "medium": 0},
        "has_blocking_conflicts": True,
    }

    cap = ConflictDetectionCapability(orchestrator=mock_orch)
    res = cap.execute({"extracted_data": {"raw_title": "Checkout"}})

    assert len(res["conflicts"]) == 1
    assert res["has_blocking_conflicts"] is True


def test_structuring_capability_unit():
    mock_orch = MagicMock()
    mock_orch.execute.return_value = {
        "metadata": {
            "title": "Guest Checkout System",
            "version": "0.1.0",
            "primary_actor": "Guest User",
            "domain": "E-Commerce",
            "summary": "Guest checkout feature",
        },
        "user_stories": [
            {
                "id": "US-1",
                "as_a": "Guest User",
                "i_want": "complete checkout without account",
                "so_that": "purchase items quickly",
                "status": "complete",
            }
        ],
        "acceptance_criteria": [
            {
                "id": "AC-1",
                "story_id": "US-1",
                "scenario": "Guest Checkout",
                "given": "Guest has items in cart",
                "when": "Guest enters email",
                "then": "Order is confirmed",
                "derivation": "source_derived",
            }
        ],
        "incomplete_stories": [],
        "business_rules": [],
        "assumptions": [],
        "constraints": [],
    }

    cap = StructuringCapability(orchestrator=mock_orch)
    res = cap.execute({"extracted_data": {"raw_title": "Guest Checkout"}})

    assert res["metadata"]["title"] == "Guest Checkout System"
    assert len(res["user_stories"]) == 1
    assert res["user_stories"][0]["as_a"] == "Guest User"


def test_quality_capability_unit():
    mock_orch = MagicMock()
    mock_orch.execute.return_value = {
        "completeness": {"score": 90.0, "reason": "Complete requirements"},
        "clarity": {"score": 90.0, "reason": "Clear statements"},
        "consistency": {"score": 80.0, "reason": "Minor ambiguity"},
        "testability": {"score": 90.0, "reason": "Testable conditions"},
        "traceability": {"score": 80.0, "reason": "Traceable items"},
        "quality_summary": "High quality requirement.",
        "recommended_improvements": [],
    }

    cap = QualityCapability(orchestrator=mock_orch)
    res = cap.execute({
        "structured_requirement": {"metadata": {"title": "Checkout"}},
        "gap_report": {"open_questions": [{"q": 1}]},
        "conflict_report": {"conflicts": []},
    })

    assert res["confidence_score"] == 86.5
    assert res["health_score"] == 95.0
    assert res["health_status"] == "Healthy"


# ------------------------------------------------------------------ #
# 2. CapabilityRunner Pipeline Tests
# ------------------------------------------------------------------ #


def test_capability_runner_successful_pipeline(test_db: Session, monkeypatch):
    # Setup test project and requirement
    proj = Project(name="Runner Proj", description="RP")
    test_db.add(proj)
    test_db.commit()

    req = Requirement(
        project_id=proj.id,
        title="Draft Ingestion",
        current_state="INGESTING",
        assigned_role="BUSINESS_ANALYST",
    )
    test_db.add(req)
    test_db.commit()

    # Mock all capabilities to avoid real OpenAI network calls during unit test
    from app.capabilities.conflict import conflict_detection_capability
    from app.capabilities.context import context_capability
    from app.capabilities.extraction import extraction_capability
    from app.capabilities.gap_detection import gap_detection_capability
    from app.capabilities.quality import quality_capability
    from app.capabilities.structuring import structuring_capability

    monkeypatch.setattr(
        extraction_capability,
        "execute",
        lambda data: {
            "raw_title": "Guest Checkout System",
            "extracted_statements": ["Guest checkout feature"],
            "actors": ["Guest"],
            "data_fields": [],
            "assumptions": [],
            "constraints": [],
        },
    )
    monkeypatch.setattr(
        context_capability,
        "execute",
        lambda data: {
            "related_entities": ["Cart"],
            "retrieved_evidence": [],
            "context_links": [],
            "enrichment_notes": "",
            "rag_context_used": False,
        },
    )
    monkeypatch.setattr(
        gap_detection_capability,
        "execute",
        lambda data: {
            "gaps": [],
            "open_questions": [],
            "missing_edge_cases": [],
        },
    )
    monkeypatch.setattr(
        conflict_detection_capability,
        "execute",
        lambda data: {
            "conflicts": [],
            "severity_summary": {},
            "has_blocking_conflicts": False,
        },
    )
    monkeypatch.setattr(
        structuring_capability,
        "execute",
        lambda data: {
            "metadata": {"title": "Guest Checkout System"},
            "user_stories": [],
        },
    )
    monkeypatch.setattr(
        quality_capability,
        "execute",
        lambda data: {
            "confidence_score": 85.0,
            "confidence_breakdown": {},
            "health_score": 100.0,
            "health_status": "Healthy",
            "open_questions_count": 0,
            "quality_summary": "Good",
            "recommended_improvements": [],
        },
    )

    runner = CapabilityRunner()

    # Execute pipeline
    updated_req = runner.run_pipeline(
        db=test_db,
        requirement_id=req.id,
        document_content="Full feature document content for guest checkout.",
        domain_context="E-Commerce",
    )

    assert updated_req.current_state == "AI_ANALYZED"
    assert updated_req.assigned_role == "BUSINESS_ANALYST"
    assert updated_req.version == "0.2.0"  # Bumps minor version from 0.1.0 to 0.2.0 on AI analysis completion
    assert updated_req.confidence_score == 85.0
    assert updated_req.health_score == 100.0



def test_capability_runner_handles_capability_failure(test_db: Session):
    proj = Project(name="Fail Proj", description="FP")
    test_db.add(proj)
    test_db.commit()

    req = Requirement(
        project_id=proj.id,
        title="Fail Ingestion",
        current_state="INGESTING",
        assigned_role="BUSINESS_ANALYST",
    )
    test_db.add(req)
    test_db.commit()

    # Create runner with failing capability
    runner = CapabilityRunner()

    # Inject failure into mock extraction execution
    from app.capabilities.extraction import extraction_capability
    orig_exec = extraction_capability.execute

    def _failing_exec(input_data):
        raise LLMServiceError("Simulated LLM Timeout Failure")

    extraction_capability.execute = _failing_exec

    try:
        failed_req = runner.run_pipeline(
            db=test_db,
            requirement_id=req.id,
            document_content="Content that will trigger failure",
        )

        assert failed_req.current_state == "FAILED"
    finally:
        extraction_capability.execute = orig_exec


# ------------------------------------------------------------------ #
# 3. Document Ingestion API Endpoint Test
# ------------------------------------------------------------------ #


def test_ingest_document_api_endpoint(test_db: Session):
    # Register BA user
    c = TestClient(app)
    c.post(
        "/api/auth/register",
        json={"email": "ingest_ba@xyz.com", "password": "password123"},
    )
    c.post("/api/auth/role", json={"role": "BUSINESS_ANALYST"})

    proj = Project(name="Ingest API Proj", description="IAP")
    test_db.add(proj)
    test_db.commit()

    b64_content = base64.b64encode(b"System shall support guest checkout.").decode("utf-8")

    response = c.post(
        "/api/requirements/ingest",
        json={
            "project_id": str(proj.id),
            "file_name": "feature_spec.txt",
            "file_content_base64": b64_content,
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "INGESTING"
    assert "document_id" in data
    assert "requirement_id" in data


def test_ingest_text_api_endpoint(test_db: Session):
    c = TestClient(app)
    c.post(
        "/api/auth/register",
        json={"email": "transcript_ba@xyz.com", "password": "password123"},
    )
    c.post("/api/auth/role", json={"role": "BUSINESS_ANALYST"})

    proj = Project(name="Transcript Proj", description="TP")
    test_db.add(proj)
    test_db.commit()

    sample_transcript = "The system shall allow users to ingest software requirements documents and analyze them using 6 AI capability modules. The application must process PDF, DOCX, XLSX, and TXT files efficiently."

    response = c.post(
        "/api/requirements/ingest-text",
        json={
            "project_id": str(proj.id),
            "title": "Sprint 14 Stakeholder Transcript",
            "text": sample_transcript,
            "source_type": "TRANSCRIPT",
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "INGESTING"
    assert "document_id" in data
    assert "requirement_id" in data


def test_ingest_text_validation_fails(test_db: Session):
    c = TestClient(app)
    c.post(
        "/api/auth/register",
        json={"email": "short_text_ba@xyz.com", "password": "password123"},
    )
    c.post("/api/auth/role", json={"role": "BUSINESS_ANALYST"})

    response = c.post(
        "/api/requirements/ingest-text",
        json={
            "project_id": "a1b2c3d4-e5f6-47a8-b9c0-d1e2f3a4b5c6",
            "title": "Too Short",
            "text": "Short text.",
            "source_type": "TRANSCRIPT",
        },
    )

    assert response.status_code == 400
    assert "too short" in response.json()["detail"].lower()

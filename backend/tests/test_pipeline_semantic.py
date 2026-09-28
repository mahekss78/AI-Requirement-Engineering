"""
tests/test_pipeline_semantic.py
===============================
Semantic regression, cross-domain isolation, edge-case, and invariant tests for the AI Capability Pipeline.
Validates requirements engineering across 6 distinct domains with ZERO cross-domain contamination.
"""
import hashlib
import json
import pytest
from unittest.mock import patch, MagicMock
from app.services.content_classifier import classify_content, validate_input
from app.services.prompt_orch import PromptOrchestrator
from app.capabilities.extraction import ExtractionCapability
from app.capabilities.context import ContextCapability
from app.capabilities.gap_detection import GapDetectionCapability
from app.capabilities.conflict import ConflictDetectionCapability
from app.capabilities.structuring import StructuringCapability
from app.capabilities.quality import QualityCapability


def _make_orchestrator():
    """Create orchestrator that will always hit fallback (mocked LLM fails)."""
    with patch('app.services.prompt_orch.OpenAI'):
        orch = PromptOrchestrator()
    return orch


def _make_rag_service():
    """Create fast mock RAG service for instant unit tests."""
    mock_rag = MagicMock()
    mock_rag.search_context.return_value = ""
    return mock_rag


def run_extraction(text):
    orch = _make_orchestrator()
    cap = ExtractionCapability(orchestrator=orch)
    return cap.execute({"document_content": text})


def run_context(extraction_result):
    orch = _make_orchestrator()
    cap = ContextCapability(orchestrator=orch, rag_service=_make_rag_service())
    return cap.execute({"extracted_data": extraction_result})


def run_gap_detection(extraction_result, context_result):
    orch = _make_orchestrator()
    cap = GapDetectionCapability(orchestrator=orch)
    return cap.execute({"extracted_data": extraction_result, "context_data": context_result})


def run_conflict_detection(extraction_result, context_result, gap_result):
    orch = _make_orchestrator()
    cap = ConflictDetectionCapability(orchestrator=orch)
    return cap.execute({"extracted_data": extraction_result, "context_data": context_result, "gap_report": gap_result})


def run_structuring_via_fallback(text):
    ext = run_extraction(text)
    ctx = run_context(ext)
    gap = run_gap_detection(ext, ctx)
    conflict = run_conflict_detection(ext, ctx, gap)
    orch = _make_orchestrator()
    cap = StructuringCapability(orchestrator=orch)
    return cap.execute({"extracted_data": ext, "context_data": ctx, "gap_report": gap, "conflict_report": conflict})


def run_full_pipeline(text):
    ext = run_extraction(text)
    ctx = run_context(ext)
    gap = run_gap_detection(ext, ctx)
    conflict = run_conflict_detection(ext, ctx, gap)
    orch = _make_orchestrator()
    struct_cap = StructuringCapability(orchestrator=orch)
    struct = struct_cap.execute({"extracted_data": ext, "context_data": ctx, "gap_report": gap, "conflict_report": conflict})
    q_cap = QualityCapability(orchestrator=orch)
    quality = q_cap.execute({"structured_requirement": struct, "gap_report": gap, "conflict_report": conflict})
    classification = classify_content(text)
    return {
        "pipeline_status": "success",
        "input_hash": f"sha256:{hashlib.sha256(text.encode()).hexdigest()}",
        "classification": classification,
        "extraction": ext,
        "context": ctx,
        "gap_detection": gap,
        "conflict_detection": conflict,
        "structuring": struct,
        "quality": quality,
    }


# =====================================================================
# 6 CANONICAL TEST DATASETS (Zero Cross-Domain Overlap)
# =====================================================================

DOMAIN_A_ECOMMERCE = """Meeting Discussion: E-Commerce Cancellation & Refund Order Tracking
Anita – Business Analyst
Rahul – Product Owner

Customer can cancel unfulfilled orders within 30 minutes of placement.
Support agents can override cancellation limits for VIP customers.
Refund processing notifications must be delivered within 2 seconds.
The application should be much faster during flash sales.
The system should integrate with the Stripe Payment Gateway.
Can partially shipped orders be cancelled?
Refunds should normally complete within 5 business days.
Another stakeholder said refunds must happen immediately."""

DOMAIN_B_UNIVERSITY = """University Course Registration Portal
Registrar – Academic Authority

Students can register for academic courses during the open enrollment window.
The system must enforce prerequisite validation before course confirmation.
The registration portal must support 5,000 concurrent students without performance degradation.
Academic advisors can override course prerequisites for graduating seniors.
Can students on academic probation register for honors courses?"""

DOMAIN_C_BANKING = """Banking Loan Application System
Borrowers can submit mortgage loan applications online.
Loan officers can review and approve applicant financial disclosures.
Credit verification check response time must be under 3 seconds.
All customer financial data must be encrypted at rest.
The application should process approvals in reasonable time."""

DOMAIN_D_HEALTHCARE = """Hospital Patient Clinical Management System
Patients can schedule outpatient appointments with specialized doctors.
Doctors can view real-time triage notes and medical history.
Emergency telemetry alerts must be delivered within 500ms.
Hospital administrators can manage clinic room assignments.
Should international visitors be required to provide passport verification?"""

DOMAIN_E_CYBERSECURITY = """SOC Incident Management & Threat Containment
SOC Analysts can isolate compromised endpoints immediately upon critical detection.
The platform must integrate with the Enterprise SIEM Service.
Endpoint quarantine action execution must complete within 1 second.
Security Engineers can configure automated playbooks for malware alerts."""

DOMAIN_F_IRRELEVANT = """Today is sunny and warm outside.
I went to the grocery market and bought fresh apples, milk, and bread.
We are planning a dinner party cooking Italian pasta tonight.
The birds are singing in the garden trees."""


# =====================================================================
# A. Content Classifier Tests
# =====================================================================

def test_classify_empty_input():
    result = validate_input("")
    assert result["status"] == "INVALID_INPUT"
    assert result["condition"] == "DOCUMENT_EMPTY"


def test_classify_whitespace_only():
    result = validate_input("   \n\n  \t  ")
    assert result["status"] == "INVALID_INPUT"
    assert result["condition"] == "DOCUMENT_EMPTY"


def test_classify_meeting_transcript():
    text = "BA: We need cancellation.\nClient: Yes, within 30 minutes.\nDeveloper: What about VIP customers?"
    result = classify_content(text)
    assert result["status"] == "VALID"
    assert result["input_type"] in ("meeting_transcript", "mixed_document")


def test_classify_structured_requirements():
    text = "FR-01: User can cancel order.\nFR-02: Admin can override.\nNFR-01: Response under 500ms."
    result = classify_content(text)
    assert result["has_explicit_requirements"] is True


def test_classify_email():
    text = "From: john@example.com\nTo: team@example.com\nSubject: Password Reset\n\nWe need password reset functionality."
    result = classify_content(text)
    assert result["input_type"] in ("email", "mixed_document")


def test_classify_questions_only():
    text = "Should users receive email after cancellation?\nShould admins override?\nWhat happens after shipment?"
    result = classify_content(text)
    assert result["has_questions"] is True


def test_classify_irrelevant():
    result = classify_content(DOMAIN_F_IRRELEVANT)
    assert result["content_quality"] == "irrelevant" or result["requirement_density"] == "none"


# =====================================================================
# B. Cross-Domain Semantic Isolation Tests (Zero Bleed-Through)
# =====================================================================

def test_cross_domain_semantic_isolation():
    """Verify that all 5 real domains produce unique, isolated entities with zero bleed."""
    res_a = run_extraction(DOMAIN_A_ECOMMERCE)
    res_b = run_extraction(DOMAIN_B_UNIVERSITY)
    res_c = run_extraction(DOMAIN_C_BANKING)
    res_d = run_extraction(DOMAIN_D_HEALTHCARE)
    res_e = run_extraction(DOMAIN_E_CYBERSECURITY)

    actors_a = {a["name"].lower() for a in res_a.get("actors", [])}
    actors_b = {a["name"].lower() for a in res_b.get("actors", [])}
    actors_c = {a["name"].lower() for a in res_c.get("actors", [])}
    actors_d = {a["name"].lower() for a in res_d.get("actors", [])}
    actors_e = {a["name"].lower() for a in res_e.get("actors", [])}

    # Verify domain-specific actors
    assert any("customer" in a or "support" in a for a in actors_a), f"Expected ecommerce actors, got: {actors_a}"
    assert any("student" in a or "advisor" in a for a in actors_b), f"Expected university actors, got: {actors_b}"
    assert any("borrower" in a or "loan" in a for a in actors_c), f"Expected banking actors, got: {actors_c}"
    assert any("patient" in a or "doctor" in a for a in actors_d), f"Expected healthcare actors, got: {actors_d}"
    assert any("soc" in a or "security" in a for a in actors_e), f"Expected cybersecurity actors, got: {actors_e}"

    # Verify strict actor isolation (no ecommerce actors in university, etc.)
    assert not (actors_a & actors_b), f"Cross-domain actor contamination between A and B: {actors_a & actors_b}"
    assert not (actors_b & actors_c), f"Cross-domain actor contamination between B and C: {actors_b & actors_c}"
    assert not (actors_c & actors_d), f"Cross-domain actor contamination between C and D: {actors_c & actors_d}"
    assert not (actors_d & actors_e), f"Cross-domain actor contamination between D and E: {actors_d & actors_e}"


def test_irrelevant_domain_produces_zero_requirements():
    res_f = run_extraction(DOMAIN_F_IRRELEVANT)
    assert len(res_f.get("functional_requirements", [])) == 0
    assert len(res_f.get("actors", [])) == 0


# =====================================================================
# C. Strict Question Isolation Tests
# =====================================================================

def test_questions_never_become_functional_requirements():
    """Verify that questions are stored in open_questions and never in functional_requirements."""
    res_a = run_extraction(DOMAIN_A_ECOMMERCE)
    questions = res_a.get("open_questions", [])
    assert len(questions) >= 1
    assert any("partially shipped" in q.get("question", "").lower() for q in questions)

    # Ensure question does not appear in functional requirements
    frs = res_a.get("functional_requirements", [])
    for fr in frs:
        stmt = fr.get("statement", "").lower()
        assert not stmt.startswith("can partially shipped")
        assert not stmt.endswith("?")

    # Ensure structuring also did NOT turn question into user story
    struct_a = run_structuring_via_fallback(DOMAIN_A_ECOMMERCE)
    stories = struct_a.get("user_stories", [])
    for s in stories:
        assert "?" not in s.get("i_want", "")
        assert not s.get("i_want", "").lower().startswith("to can partially shipped")


# =====================================================================
# D. Structured NFR Isolation Tests
# =====================================================================

def test_structured_nfr_separation():
    """Verify NFRs are captured with category, metric, and scope without becoming User Stories."""
    res_a = run_extraction(DOMAIN_A_ECOMMERCE)
    nfrs = res_a.get("non_functional_requirements", [])
    assert len(nfrs) >= 1
    perf_nfr = next((n for n in nfrs if "2 seconds" in n.get("statement", "")), None)
    assert perf_nfr is not None
    assert perf_nfr.get("category") == "Performance"
    assert perf_nfr.get("metric") == "2 seconds"
    assert perf_nfr.get("id").startswith("NFR-")

    # Scalability NFR in Domain B
    res_b = run_extraction(DOMAIN_B_UNIVERSITY)
    nfrs_b = res_b.get("non_functional_requirements", [])
    sc_nfr = next((n for n in nfrs_b if "5,000" in n.get("statement", "")), None)
    assert sc_nfr is not None
    assert sc_nfr.get("category") == "Scalability"


# =====================================================================
# E. Ambiguity & Conflict Detection Tests
# =====================================================================

def test_ambiguity_detection_with_clarification_question():
    res_a = run_extraction(DOMAIN_A_ECOMMERCE)
    ambs = res_a.get("ambiguities", [])
    assert len(ambs) >= 1
    assert any("much faster" in a.get("ambiguous_term", "").lower() for a in ambs)
    assert any("clarification_question" in a for a in ambs)


def test_conflict_detection_on_sla():
    res_a = run_extraction(DOMAIN_A_ECOMMERCE)
    conflicts = res_a.get("candidate_conflicts", [])
    assert len(conflicts) >= 1
    assert any("5 business days" in c.get("requirement_a", "") or "immediately" in c.get("requirement_b", "") for c in conflicts)


# =====================================================================
# F. Traceability IDs & User Story Structuring Tests
# =====================================================================

def test_traceability_ids_across_artifacts():
    res_a = run_full_pipeline(DOMAIN_A_ECOMMERCE)
    extraction = res_a["extraction"]
    structuring = res_a["structuring"]

    for fr in extraction.get("functional_requirements", []):
        assert fr["id"].startswith("FR-")

    for nfr in extraction.get("non_functional_requirements", []):
        assert nfr["id"].startswith("NFR-")

    for story in structuring.get("user_stories", []):
        assert story["id"].startswith("US-")
        assert story.get("source_requirement", "").startswith("FR-")

    for ac in structuring.get("acceptance_criteria", []):
        assert ac["id"].startswith("AC-")
        assert ac.get("story_id", "").startswith("US-")


def test_no_blank_or_generic_user_stories():
    struct_b = run_structuring_via_fallback(DOMAIN_B_UNIVERSITY)
    for story in struct_b.get("user_stories", []):
        assert story.get("as_a") not in ("", "User", "Project Discussion", "Anita", "Rahul")
        assert story.get("i_want").strip() != ""
        assert story.get("so_that").strip() != ""


# =====================================================================
# G. Quality Fallback Tests
# =====================================================================

def test_quality_fallback_returns_null_scores():
    res = run_full_pipeline(DOMAIN_A_ECOMMERCE)
    quality = res["quality"]
    assert quality.get("evaluation_status") == "ai_unavailable"
    assert quality.get("completeness", {}).get("score") is None
    assert quality.get("clarity", {}).get("score") is None


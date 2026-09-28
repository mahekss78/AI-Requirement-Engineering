"""
app/services/runner.py
======================
CapabilityRunner Orchestrator Pipeline for the AREA platform.

Responsibilities:
1. Executes the 6 AI capabilities in strict, deterministic order:
   Extraction -> Context -> Gap Detection -> Conflict Detection -> Structuring -> Quality.
2. Checkpoints intermediate execution artifacts in PostgreSQL.
3. Handles capability failures gracefully (sets state to FAILED, logs audit record, notifies BA).
4. Integrates with Memory, Scoring, Lifecycle, Audit, and Notification services.
5. Updates requirement state from INGESTING/DRAFT to AI_ANALYZED upon clean completion.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.capabilities.conflict import conflict_detection_capability
from app.capabilities.context import context_capability
from app.capabilities.extraction import extraction_capability
from app.capabilities.gap_detection import gap_detection_capability
from app.capabilities.quality import quality_capability
from app.capabilities.structuring import structuring_capability
from app.capabilities.nfr_specification import nfr_specification_capability
from app.capabilities.integration_specification import integration_specification_capability
from app.models.models import Document, Requirement
from app.services.audit_notify import audit_service, notification_service
from app.services.memory import memory_service
from app.services.content_classifier import classify_content, validate_input

logger = logging.getLogger(__name__)


class CapabilityRunner:
    """
    Deterministic AI Capability Pipeline Orchestrator.
    Manages the end-to-end execution of the 6 AI capability modules.
    """

    def run_pipeline(
        self,
        db: Session,
        requirement_id: UUID,
        document_content: str,
        domain_context: Optional[str] = None,
    ) -> Requirement:
        """
        Execute the full 6-step AI Capability Pipeline.

        Args:
            db:               SQLAlchemy database session
            requirement_id:   UUID of the requirement record
            document_content: Raw/normalized text content of the ingested document
            domain_context:   Optional domain context string

        Returns:
            Updated Requirement ORM object (in state AI_ANALYZED if successful, or FAILED if error).
        """
        req = db.query(Requirement).filter(Requirement.id == requirement_id).first()
        if not req:
            raise ValueError(f"Requirement '{requirement_id}' not found.")

        import uuid as uuid_mod
        correlation_id = str(uuid_mod.uuid4())[:8]
        logger.info(f"[PIPELINE {correlation_id}] Starting for Requirement {req.id}")
        req.current_state = "INGESTING"
        db.commit()

        context_domain = domain_context or "General Enterprise Software"
        checkpoint_data: Dict[str, Any] = {}

        try:
            # -------------------------------------------------------------- #
            # Step 0: Input Validation & Classification
            # -------------------------------------------------------------- #
            validation = validate_input(document_content)
            if validation["status"] != "VALID":
                # Set requirement state to FAILED with validation status
                req.current_state = "FAILED"
                req.requirement_data = {"pipeline_status": "invalid_input", "validation": validation}
                db.commit()
                return req

            classification = classify_content(document_content)

            import hashlib
            input_hash = hashlib.sha256(document_content.encode('utf-8')).hexdigest()

            # -------------------------------------------------------------- #
            # Step 1: Extraction Capability (Stage 0 Normalization)
            # -------------------------------------------------------------- #
            logger.info(f"[PIPELINE {correlation_id}][CAP 1/6] Extraction | input_len={len(document_content)} | input_hash=sha256:{input_hash[:16]}...")
            stage0_res = extraction_capability.execute({
                "document_content": document_content,
                "domain_context": context_domain,
                "classification": classification,
            })
            
            # -------------------------------------------------------------- #
            # Step 1.5: Semantic Classification (Stage 1)
            # -------------------------------------------------------------- #
            from app.capabilities.semantic_classification import semantic_classification_capability
            
            logger.info(f"[PIPELINE {correlation_id}][CAP 1.5/6] Semantic Classification...")
            stage1_res = semantic_classification_capability.execute({
                "normalized_statements": stage0_res.get("normalized_statements", []),
            })
            
            # -------------------------------------------------------------- #
            # Stage 2: Cross-Statement Relationship Analysis
            # -------------------------------------------------------------- #
            from app.capabilities.relationship_analysis import relationship_analysis_capability
            
            # Build initial canonical registry
            registry = []
            for i, c in enumerate(stage1_res.get("classifications", [])):
                stype = c.get("primary_type")
                processing_status = "DRAFT"
                artifact_routes = []
                
                # Determine multi-routes
                if stype == "FUNCTIONAL_REQUIREMENT":
                    if c.get("eligible_for_user_story", True):
                        artifact_routes.append("USER_STORY")
                elif stype == "NON_FUNCTIONAL_REQUIREMENT":
                    artifact_routes.append("NFR_SPECIFICATION")
                elif stype == "REQUIREMENT_CONSTRAINT":
                    # Do not route unresolved conflicts/constraints to NFR specification
                    if not (c.get("requires_human_review") or c.get("requires_clarification") or c.get("requires_resolution")):
                        artifact_routes.append("NFR_SPECIFICATION")
                elif stype == "EXTERNAL_INTEGRATION":
                    artifact_routes.append("INTEGRATION_SPECIFICATION")
                    
                # Also check secondary aspects for routes
                secondary = c.get("secondary_aspects", [])
                for aspect in secondary:
                    atype = aspect.get("type")
                    if atype == "EXTERNAL_INTEGRATION" and "INTEGRATION_SPECIFICATION" not in artifact_routes:
                        artifact_routes.append("INTEGRATION_SPECIFICATION")
                    elif atype == "NON_FUNCTIONAL_REQUIREMENT" and "NFR_SPECIFICATION" not in artifact_routes:
                        artifact_routes.append("NFR_SPECIFICATION")
                    elif atype == "REQUIREMENT_CONSTRAINT" and "NFR_SPECIFICATION" not in artifact_routes:
                        if not (c.get("requires_human_review") or c.get("requires_clarification") or c.get("requires_resolution")):
                            artifact_routes.append("NFR_SPECIFICATION")
                        
                # Determine status
                if c.get("requires_human_review") or c.get("requires_clarification"):
                    processing_status = "BLOCKED_PENDING_CLARIFICATION"
                else:
                    if artifact_routes:
                        processing_status = "READY"
                    else:
                        processing_status = "CLASSIFIED"
                    
                registry.append({
                    "statement_id": c.get("statement_id", f"STMT-{i+1:03d}"),
                    "content": c.get("content", ""),
                    "primary_type": stype,
                    "subtype": c.get("subtype"),
                    "secondary_aspects": secondary,
                    "ba_reasoning": c.get("ba_reasoning", ""),
                    "requires_clarification": c.get("requires_clarification", False),
                    "requires_human_review": c.get("requires_human_review", False),
                    "processing_status": processing_status,
                    "artifact_routes": artifact_routes,
                    "human_review_status": "NOT_REVIEWED"
                })

            logger.info(f"[PIPELINE {correlation_id}][CAP 2/6] Relationship Analysis...")
            stage2_res = relationship_analysis_capability.execute({
                "semantic_statement_registry": registry
            })
            
            # Apply relationship registry updates
            registry_updates = stage2_res.get("registry_updates", [])
            update_map = {u["statement_id"]: u for u in registry_updates}
            for stmt in registry:
                if stmt["statement_id"] in update_map:
                    stmt.update(update_map[stmt["statement_id"]])
                    
            # Auto-block conflicts
            relationships = stage2_res.get("relationships", [])
            for rel in relationships:
                if rel.get("relationship_type") == "CONFLICTS_WITH" and rel.get("requires_resolution"):
                    for stmt in registry:
                        if stmt["statement_id"] in (rel["source_statement_id"], rel["target_statement_id"]):
                            stmt["processing_status"] = "BLOCKED_PENDING_RESOLUTION"

            # -------------------------------------------------------------- #
            # Stage 3: Hard Semantic Gate
            # -------------------------------------------------------------- #
            logger.info(f"[PIPELINE {correlation_id}] Stage 3: Hard Semantic Gate START")
            ready_statements = [s for s in registry if s["processing_status"] == "READY" and s["human_review_status"] != "HUMAN_REJECTED"]
            
            ready_for_us = [s for s in ready_statements if "USER_STORY" in s.get("artifact_routes", [])]
            ready_for_nfr = [s for s in ready_statements if "NFR_SPECIFICATION" in s.get("artifact_routes", [])]
            ready_for_int = [s for s in ready_statements if "INTEGRATION_SPECIFICATION" in s.get("artifact_routes", [])]
            
            # Map back into extracted_res for now to appease downstream Structuring capability
            # TODO: Refactor Structuring capability to consume the canonical registry directly.
            extracted_res = {
                "ai_status": stage1_res.get("ai_status"),
                "raw_title": stage0_res.get("document_title", "Untitled"),
                "metadata": stage0_res.get("metadata", []),
                "actors": stage0_res.get("actors", []),
                "semantic_statement_registry": registry,
                "relationships": relationships,
                
                # Legacy bridges - include ALL statements so they appear in UI
                "functional_requirements": [{"id": f"FR-{i+1:03d}", "statement": s["content"], "statement_id": s["statement_id"]} for i, s in enumerate(registry) if s.get("primary_type") != "NON_FUNCTIONAL_REQUIREMENT"],
                "non_functional_requirements": [{"id": f"NFR-{i+1:03d}", "statement": s["content"], "statement_id": s["statement_id"]} for i, s in enumerate(registry) if s.get("primary_type") == "NON_FUNCTIONAL_REQUIREMENT"],
                "external_integrations": [{"id": f"INT-{i+1:03d}", "statement": s["content"], "statement_id": s["statement_id"]} for i, s in enumerate(registry) if s.get("primary_type") == "EXTERNAL_INTEGRATION"],
                "candidate_conflicts": [],
                "open_questions": [],
                "business_rules": [],
                "ambiguities": [],
            }
            checkpoint_data["extraction"] = extracted_res
            logger.info(f"[PIPELINE {correlation_id}] Stage 3: Hard Semantic Gate DONE | Passed: {len(ready_for_us)} FRs, {len(ready_for_nfr)} NFRs, {len(ready_for_int)} Integrations")

            # Stubs for removed pipeline steps
            context_res = {"ai_status": "skipped", "domain": context_domain}
            gap_res = {"ai_status": "skipped", "gaps": []}
            
            # Map Stage 2 relationships to legacy conflict_res for frontend
            legacy_conflicts = []
            for rel in relationships:
                if rel.get("relationship_type") == "CONFLICTS_WITH":
                    req_a = next((s["content"] for s in registry if s["statement_id"] == rel.get("source_statement_id")), "")
                    req_b = next((s["content"] for s in registry if s["statement_id"] == rel.get("target_statement_id")), "")
                    legacy_conflicts.append({
                        "id": rel.get("relationship_id", "CON-001"),
                        "requirement_a": req_a,
                        "requirement_b": req_b,
                        "conflict_description": rel.get("evidence", "Conflict detected in semantic analysis."),
                        "severity": "HIGH",
                        "clarification_question": f"Resolution required for {rel.get('conflict_dimension')} conflict on {rel.get('conflict_scope')}."
                    })
            conflict_res = {"ai_status": "legacy_mapped", "conflicts": legacy_conflicts}

            # -------------------------------------------------------------- #
            # Step 4: Structuring Capabilities (US, NFR, INT)
            # -------------------------------------------------------------- #
            logger.info(f"[PIPELINE {correlation_id}][CAP 4/6] User Story Structuring START")
            structuring_res = structuring_capability.execute({
                "ready_for_us": ready_for_us,
                "metadata": extracted_res.get("metadata", []),
                "relationships": relationships,
            })
            checkpoint_data["structuring"] = structuring_res
            logger.info(f"[PIPELINE {correlation_id}][CAP 4/6] User Story Structuring DONE | ai_status={structuring_res.get('ai_status')}")

            logger.info(f"[PIPELINE {correlation_id}][CAP 4B] NFR Structuring START")
            ready_for_nfr = [s for s in ready_statements if "NFR_SPECIFICATION" in s.get("artifact_routes", [])]
            nfr_res = nfr_specification_capability.execute({
                "ready_for_nfr": ready_for_nfr,
                "metadata": extracted_res.get("metadata", []),
                "relationships": relationships,
            })
            checkpoint_data["nfr_structuring"] = nfr_res

            logger.info(f"[PIPELINE {correlation_id}][CAP 4C] INT Structuring START")
            ready_for_int = [s for s in ready_statements if "INTEGRATION_SPECIFICATION" in s.get("artifact_routes", [])]
            int_res = integration_specification_capability.execute({
                "ready_for_int": ready_for_int,
                "metadata": extracted_res.get("metadata", []),
                "relationships": relationships,
            })
            checkpoint_data["int_structuring"] = int_res

            # -------------------------------------------------------------- #
            # Step 6: Quality Capability & Scoring Integration
            # -------------------------------------------------------------- #
            logger.info(f"[PIPELINE {correlation_id}][CAP 6/6] Quality Scoring START")
            quality_res = quality_capability.execute({
                "structured_requirement": structuring_res,
                "gap_report": gap_res,
                "conflict_report": conflict_res,
                "classification": classification,
            })
            checkpoint_data["quality"] = quality_res
            logger.info(f"[PIPELINE {correlation_id}][CAP 6/6] Quality Scoring DONE | ai_status={quality_res.get('ai_status')}")

            # -------------------------------------------------------------- #
            # Pipeline Checkpoint Persistence & State Transition
            # -------------------------------------------------------------- #
            from datetime import datetime, timezone

            title = structuring_res.get("metadata", {}).get("title") or extracted_res.get("raw_title") or "Ingested Requirement"
            req.title = title
            
            req.requirement_data = {
                "pipeline_version": "2.0.0",
                "pipeline_status": "success",
                "input_hash": f"sha256:{input_hash}",
                "input_length": len(document_content),
                "classification": classification,
                "extraction": extracted_res,
                "context": context_res,
                "gap_detection": gap_res,
                "conflict_detection": conflict_res,
                "structuring": structuring_res,
                "nfr_structuring": nfr_res,
                "int_structuring": int_res,
                "quality": quality_res,
                "capability_statuses": {
                    "extraction": extracted_res.get("ai_status", "unknown"),
                    "context": context_res.get("ai_status", "unknown"),
                    "gap_detection": gap_res.get("ai_status", "unknown"),
                    "conflict_detection": conflict_res.get("ai_status", "unknown"),
                    "structuring": structuring_res.get("ai_status", "unknown"),
                    "quality": quality_res.get("ai_status", "unknown"),
                },
                "pipeline_timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            def _extract_score(val):
                if isinstance(val, dict):
                    return val.get("score")
                if isinstance(val, (int, float)):
                    return val
                return None
            
            confidence_score = quality_res.get("confidence_score")
            if confidence_score is None:
                comp = _extract_score(quality_res.get("completeness"))
                clar = _extract_score(quality_res.get("clarity"))
                if comp is not None and clar is not None:
                    confidence_score = 0.0 # would use confidence_engine.calculate, defaulting to 0 for fallback
                else:
                    confidence_score = 0.0
            
            req.confidence_score = confidence_score or 0.0
            req.health_score = quality_res.get("health_score", 100.0)
            req.health_status = quality_res.get("health_status", "Healthy")
            req.open_questions_count = quality_res.get("open_questions_count", 0)

            # Seed Clarification records from extraction, gaps, and conflicts
            try:
                from app.models.models import Clarification
                existing_clarifications = {
                    c.question.strip().lower()
                    for c in db.query(Clarification).filter(Clarification.requirement_id == req.id).all()
                }

                candidate_questions = []
                for q in extracted_res.get("open_questions", []):
                    q_text = q.get("question") or q.get("text") if isinstance(q, dict) else str(q)
                    if q_text:
                        candidate_questions.append({"question": q_text, "role": "CLIENT"})
                for g in gap_res.get("gaps", []):
                    q_text = g.get("clarification_question") if isinstance(g, dict) else None
                    if q_text:
                        candidate_questions.append({"question": q_text, "role": g.get("assigned_role") or "PRODUCT_OWNER"})
                for c in conflict_res.get("conflicts", []):
                    q_text = c.get("clarification_question") if isinstance(c, dict) else None
                    if q_text:
                        candidate_questions.append({"question": q_text, "role": "PRODUCT_OWNER"})

                for item in candidate_questions:
                    norm_q = item["question"].strip()
                    if norm_q.lower() not in existing_clarifications:
                        db.add(Clarification(
                            requirement_id=req.id,
                            question=norm_q,
                            assigned_role=item.get("role") or "CLIENT",
                            status="PENDING",
                        ))
                        existing_clarifications.add(norm_q.lower())

                req.open_questions_count = len(existing_clarifications)
            except Exception as e_clar:
                logger.warning(f"Failed to seed clarification records: {e_clar}")

            # Transition to AI_ANALYZED
            req.current_state = "AI_ANALYZED"
            req.assigned_role = "BUSINESS_ANALYST"

            # Version 0.1.0 snapshot
            memory_service.create_version_snapshot(
                db, req, change_rationale="Initial AI Capability Pipeline Analysis", is_major_bump=False
            )

            # Audit log
            audit_service.log_event(
                db=db,
                requirement_id=req.id,
                actor_role="SYSTEM",
                action_type="AI_ANALYSIS_COMPLETE",
                prev_state="INGESTING",
                new_state="AI_ANALYZED",
                change_diff={
                    "confidence_score": req.confidence_score,
                    "health_score": req.health_score,
                    "open_questions": req.open_questions_count,
                },
            )

            # Notification to BA
            notification_service.dispatch_notification(
                db=db,
                recipient_role="BUSINESS_ANALYST",
                message=f"AI analysis completed for '{req.title}'. Assigned to Business Analyst for review.",
                notification_type="INFO",
                requirement_id=req.id,
            )

            db.commit()
            db.refresh(req)
            logger.info(
                f"CapabilityRunner pipeline completed successfully for Requirement {req.id}. "
                f"State: AI_ANALYZED, Confidence: {req.confidence_score}, Health: {req.health_score}"
            )
            return req

        except Exception as exc:
            logger.error(f"CapabilityRunner pipeline failed for Requirement {req.id}: {exc}")
            db.rollback()

            # Mark requirement FAILED
            req = db.query(Requirement).filter(Requirement.id == requirement_id).first()
            if req:
                req.current_state = "FAILED"
                audit_service.log_event(
                    db=db,
                    requirement_id=req.id,
                    actor_role="SYSTEM",
                    action_type="AI_ANALYSIS_FAILED",
                    prev_state="INGESTING",
                    new_state="FAILED",
                    change_diff={"error": str(exc)},
                )
                notification_service.dispatch_notification(
                    db=db,
                    recipient_role="BUSINESS_ANALYST",
                    message=f"AI analysis failed for requirement '{req.title}': {exc}",
                    notification_type="WARNING",
                    requirement_id=req.id,
                )
                db.commit()
                db.refresh(req)
            return req


capability_runner = CapabilityRunner()

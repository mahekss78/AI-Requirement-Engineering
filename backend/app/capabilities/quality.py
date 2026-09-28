"""
app/capabilities/quality.py
==========================
Quality Analysis Capability (Capability #6).

Responsibility:
  Evaluates requirement quality across the 5 PDS dimensions (Completeness, Clarity,
  Consistency, Testability, Traceability) and integrates directly with the Phase B
  ConfidenceEngine and HealthEngine scoring services.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.capabilities.base import BaseAICapability
from app.services.prompt_orch import LLMServiceError
from app.services.scoring import confidence_engine, health_engine

logger = logging.getLogger(__name__)


class QualityCapability(BaseAICapability):
    """
    Capability #6: Quality Verification & Scoring Integration.
    """

    @property
    def capability_name(self) -> str:
        return "quality"

    @property
    def template_name(self) -> str:
        return "quality"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute quality evaluation.
        """
        structured_requirement = input_data.get("structured_requirement", {})
        gap_report = input_data.get("gap_report", {})
        conflict_report = input_data.get("conflict_report", {})

        if not structured_requirement:
            raise ValueError("Quality capability requires non-empty 'structured_requirement'.")

        variables = {
            "structured_requirement": structured_requirement,
            "gap_report": gap_report,
            "conflict_report": conflict_report,
        }

        logger.info("Executing Quality Capability...")
        try:
            raw_result = self.orchestrator.execute(
                template_name=self.template_name,
                variables=variables,
                expect_json=True,
            )
            ai_status = raw_result.get("ai_status", "llm_success" if raw_result else "fallback_deterministic")
            eval_status = raw_result.get("evaluation_status", "evaluated" if ai_status == "llm_success" else "ai_unavailable")
        except LLMServiceError:
            raw_result = {}
            ai_status = "fallback_deterministic"
            eval_status = "ai_unavailable"

        if not isinstance(raw_result, dict) or ai_status == "fallback_deterministic":
            eval_status = "ai_unavailable"

        def get_score_and_reason(field, default_reason):
            val = raw_result.get(field)
            if isinstance(val, dict):
                return val.get("score"), val.get("reason", default_reason)
            if isinstance(val, (int, float)):
                return float(val), "Evaluated score."
            return None, default_reason

        default_reason = "AI quality evaluation unavailable."
        comp_score, comp_reason = get_score_and_reason("completeness", default_reason)
        clar_score, clar_reason = get_score_and_reason("clarity", default_reason)
        cons_score, cons_reason = get_score_and_reason("consistency", default_reason)
        test_score, test_reason = get_score_and_reason("testability", default_reason)
        trac_score, trac_reason = get_score_and_reason("traceability", default_reason)

        if eval_status == "evaluated" and all(s is None for s in [comp_score, clar_score, cons_score, test_score, trac_score]):
             eval_status = "insufficient_information"
             
        # Count open questions and rejections for HealthEngine
        open_q_count = len(gap_report.get("open_questions", []))
        rejections_count = len(conflict_report.get("conflicts", []))

        # Integrate with Phase B Engines
        if eval_status == "evaluated" and all(s is not None for s in [comp_score, clar_score, cons_score, test_score, trac_score]):
            confidence_score, confidence_breakdown = confidence_engine.calculate(
                completeness=comp_score,
                clarity=clar_score,
                consistency=cons_score,
                testability=test_score,
                traceability=trac_score,
            )
        else:
            confidence_score = 0.0
            confidence_breakdown = {}

        # Health score is computed based on unresolved open questions, conflicts, and gaps
        health_score, health_status = health_engine.calculate(
            open_questions_count=open_q_count,
            rejections_count=rejections_count,
        )

        validated_output = {
            "ai_status": ai_status,
            "evaluation_status": eval_status,
            "completeness": {"score": comp_score, "reason": comp_reason},
            "clarity": {"score": clar_score, "reason": clar_reason},
            "consistency": {"score": cons_score, "reason": cons_reason},
            "testability": {"score": test_score, "reason": test_reason},
            "traceability": {"score": trac_score, "reason": trac_reason},
            "confidence_score": confidence_score,
            "confidence_breakdown": confidence_breakdown,
            "health_score": health_score,
            "health_status": health_status,
            "open_questions_count": open_q_count,
            "quality_summary": raw_result.get("quality_summary", "Quality analysis pending/unavailable."),
            "recommended_improvements": raw_result.get("recommended_improvements", []),
        }

        logger.info(
            f"Quality Capability complete: Confidence={confidence_score}, "
            f"Health={health_score} ({health_status})."
        )
        return validated_output


quality_capability = QualityCapability()

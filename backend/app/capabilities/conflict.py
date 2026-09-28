"""
app/capabilities/conflict.py
============================
Conflict & Inconsistency Detection Capability (Capability #4).

Responsibility:
  Detects logical contradictions, conflicting constraints, or terminology
  mismatches between requirement statements and domain rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.capabilities.base import BaseAICapability
from app.services.prompt_orch import LLMServiceError

logger = logging.getLogger(__name__)


class ConflictDetectionCapability(BaseAICapability):
    """
    Capability #4: Conflict & Contradiction Detection.
    """

    @property
    def capability_name(self) -> str:
        return "conflict"

    @property
    def template_name(self) -> str:
        return "conflict"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute conflict detection.
        """
        extracted_data = input_data.get("extracted_data", {})
        context_data = input_data.get("context_data", {})
        gap_report = input_data.get("gap_report", {})

        if not extracted_data:
            raise ValueError("Conflict Detection capability requires non-empty 'extracted_data'.")

        variables = {
            "extracted_data": extracted_data,
            "context_data": context_data,
            "gap_report": gap_report,
        }

        logger.info("Executing Conflict Detection Capability...")
        raw_result = self.orchestrator.execute(
            template_name=self.template_name,
            variables=variables,
            expect_json=True,
        )

        if not isinstance(raw_result, dict):
            raise LLMServiceError("Conflict Detection LLM output must be a valid JSON dictionary.")

        ai_status = raw_result.get("ai_status", "llm_success" if raw_result else "fallback_deterministic")
        conflicts = raw_result.get("conflicts", [])
        has_blocking = any(c.get("severity", "").upper() == "HIGH" for c in conflicts)

        validated_output = {
            "ai_status": ai_status,
            "conflicts": conflicts,
            "severity_summary": raw_result.get("severity_summary", {"high": sum(1 for c in conflicts if c.get("severity", "").upper() == "HIGH"), "medium": sum(1 for c in conflicts if c.get("severity", "").upper() == "MEDIUM")}),
            "has_blocking_conflicts": has_blocking,
        }

        logger.info(
            f"Conflict Detection complete: {len(conflicts)} conflicts detected "
            f"(Blocking: {has_blocking})."
        )
        return validated_output


conflict_detection_capability = ConflictDetectionCapability()

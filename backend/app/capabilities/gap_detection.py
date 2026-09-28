"""
app/capabilities/gap_detection.py
================================
Gap & Ambiguity Detection Capability (Capability #3).

Responsibility:
  Analyzes extracted requirements and context to identify missing business rules,
  unspecified edge cases, and targeted clarification questions for stakeholders.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.capabilities.base import BaseAICapability
from app.services.prompt_orch import LLMServiceError

logger = logging.getLogger(__name__)


class GapDetectionCapability(BaseAICapability):
    """
    Capability #3: Gap & Ambiguity Detection.
    """

    @property
    def capability_name(self) -> str:
        return "gap_detection"

    @property
    def template_name(self) -> str:
        return "gap_detection"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute gap detection.
        """
        extracted_data = input_data.get("extracted_data", {})
        context_data = input_data.get("context_data", {})

        if not extracted_data:
            raise ValueError("Gap Detection capability requires non-empty 'extracted_data'.")

        variables = {
            "extracted_data": extracted_data,
            "context_data": context_data,
        }

        logger.info("Executing Gap Detection Capability...")
        raw_result = self.orchestrator.execute(
            template_name=self.template_name,
            variables=variables,
            expect_json=True,
        )

        if not isinstance(raw_result, dict):
            raise LLMServiceError("Gap Detection LLM output must be a valid JSON dictionary.")

        ai_status = raw_result.get("ai_status", "llm_success" if raw_result else "fallback_deterministic")
        
        # Pass through open_questions from extraction
        extraction_questions = extracted_data.get("open_questions", [])
        ai_questions = raw_result.get("open_questions", [])
        all_questions = extraction_questions + ai_questions

        validated_output = {
            "ai_status": ai_status,
            "gaps": raw_result.get("gaps", []),
            "open_questions": all_questions,
            "missing_edge_cases": raw_result.get("missing_edge_cases", []),
        }

        logger.info(
            f"Gap Detection complete: {len(validated_output['gaps'])} gaps, "
            f"{len(validated_output['open_questions'])} open questions detected."
        )
        return validated_output


gap_detection_capability = GapDetectionCapability()

"""
app/capabilities/semantic_classification.py
=============================
Semantic Classification Capability (Capability #1.5).

Responsibility:
  Takes normalized statements and classifies them semantically.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.capabilities.base import BaseAICapability
from app.services.prompt_orch import LLMServiceError

logger = logging.getLogger(__name__)


class SemanticClassificationCapability(BaseAICapability):
    """
    Capability #1.5: Semantic Classification.
    """

    @property
    def capability_name(self) -> str:
        return "semantic_classification"

    @property
    def template_name(self) -> str:
        return "semantic_classification"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute semantic classification.

        Args:
            input_data: Must contain 'normalized_statements' list.
        """
        normalized_statements = input_data.get("normalized_statements", [])
        
        # Prepare statements for prompt
        statements_text = "\n".join([f"{i+1}. {s}" for i, s in enumerate(normalized_statements)])

        variables = {
            "normalized_statements": statements_text,
        }

        logger.info("Executing Semantic Classification Capability...")
        raw_result = self.orchestrator.execute(
            template_name=self.template_name,
            variables=variables,
            expect_json=True,
        )

        if not isinstance(raw_result, dict):
            raise LLMServiceError("Semantic Classification LLM output must be a valid JSON dictionary.")

        ai_status = raw_result.get("ai_status", "llm_success" if raw_result else "fallback_deterministic")

        classifications = raw_result.get("classifications", [])
        
        validated_output = {
            "ai_status": ai_status,
            "classifications": classifications,
        }

        logger.info(
            f"Semantic Classification complete: "
            f"{len(classifications)} statements classified."
        )
        return validated_output


semantic_classification_capability = SemanticClassificationCapability()

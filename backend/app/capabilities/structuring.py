"""
app/capabilities/structuring.py
==============================
Structuring Capability (Capability #4 - User Story Engine).

Responsibility:
  Takes canonical statements routed to USER_STORY and structures them into User Stories.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.capabilities.base import BaseAICapability
from app.services.prompt_orch import LLMServiceError

logger = logging.getLogger(__name__)


class StructuringCapability(BaseAICapability):
    """
    Capability #4: User Story Structuring Engine.
    """

    @property
    def capability_name(self) -> str:
        return "structuring"

    @property
    def template_name(self) -> str:
        return "structuring"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute requirement structuring.
        """
        ready_for_us = input_data.get("ready_for_us", [])
        metadata = input_data.get("metadata", {})
        relationships = input_data.get("relationships", [])

        variables = {
            "ready_for_us": ready_for_us,
            "metadata": metadata,
            "relationships": relationships,
        }

        logger.info("Executing User Story Structuring Capability...")
        raw_result = self.orchestrator.execute(
            template_name=self.template_name,
            variables=variables,
            expect_json=True,
        )

        if not isinstance(raw_result, dict):
            raise LLMServiceError("Structuring LLM output must be a valid JSON dictionary.")
            
        ai_status = raw_result.get("ai_status", "llm_success" if raw_result else "fallback_deterministic")
        raw_result["ai_status"] = ai_status

        logger.info(
            f"Structuring complete: User Stories={len(raw_result.get('user_stories', []))}"
        )
        return raw_result


structuring_capability = StructuringCapability()

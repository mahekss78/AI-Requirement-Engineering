"""
app/capabilities/extraction.py
=============================
Extraction Capability (Capability #1).

Responsibility:
  Parses normalized document content and extracts raw requirement statements,
  actors, domain data fields, assumptions, and constraints.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.capabilities.base import BaseAICapability
from app.services.prompt_orch import LLMServiceError

logger = logging.getLogger(__name__)


class ExtractionCapability(BaseAICapability):
    """
    Capability #1: Requirement Extraction.
    """

    @property
    def capability_name(self) -> str:
        return "extraction"

    @property
    def template_name(self) -> str:
        return "extraction"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute requirement extraction.

        Args:
            input_data: Must contain 'document_content' string. Optional 'content_classification'.
        """
        doc_content = input_data.get("document_content", "").strip()
        if not doc_content:
            raise ValueError("Extraction capability requires non-empty 'document_content'.")

        content_classification = input_data.get("content_classification", {})

        variables = {
            "document_content": doc_content,
            "content_classification": content_classification,
        }

        logger.info("Executing Extraction Capability...")
        raw_result = self.orchestrator.execute(
            template_name=self.template_name,
            variables=variables,
            expect_json=True,
        )

        if not isinstance(raw_result, dict):
            raise LLMServiceError("Extraction LLM output must be a valid JSON dictionary.")

        ai_status = raw_result.get("ai_status", "llm_success" if raw_result else "fallback_deterministic")

        raw_actors = raw_result.get("actors", [])
        raw_metadata = raw_result.get("metadata", [])
        raw_integrations = raw_result.get("external_integrations", [])
        raw_statements = raw_result.get("normalized_statements", [])

        validated_output = {
            "ai_status": ai_status,
            "document_title": raw_result.get("document_title", "Untitled Document"),
            "metadata": raw_metadata,
            "actors": raw_actors,
            "external_integrations": raw_integrations,
            "normalized_statements": raw_statements,
        }

        logger.info(
            f"Stage 0 Normalization complete: Input length {len(doc_content)}, "
            f"{len(validated_output['normalized_statements'])} normalized statements extracted, "
            f"{len(validated_output['actors'])} actors extracted."
        )
        return validated_output


extraction_capability = ExtractionCapability()

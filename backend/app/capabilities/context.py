"""
app/capabilities/context.py
==========================
Context Capability (Capability #2).

Responsibility:
  Queries the RAG knowledge store for domain policies and maps contextual
  relationships, related sub-systems, and stakeholder evidence.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.capabilities.base import BaseAICapability
from app.services.prompt_orch import LLMServiceError

logger = logging.getLogger(__name__)


class ContextCapability(BaseAICapability):
    """
    Capability #2: Context Enrichment & Knowledge Mapping.
    """

    @property
    def capability_name(self) -> str:
        return "context"

    @property
    def template_name(self) -> str:
        return "context"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute context enrichment using RAG retrieval.
        """
        extracted_data = input_data.get("extracted_data", {})
        if not extracted_data:
            raise ValueError("Context capability requires non-empty 'extracted_data'.")

        # Formulate RAG search query from extracted entities
        query_parts = []
        query_parts.append(extracted_data.get("raw_title", ""))
        for fr in extracted_data.get("functional_requirements", [])[:3]:
            query_parts.append(fr.get("statement", ""))
        for actor in extracted_data.get("actors", [])[:3]:
            query_parts.append(actor.get("name", ""))
        for de in extracted_data.get("data_entities", [])[:3]:
            query_parts.append(de.get("name", ""))
            
        query_text = " ".join([q for q in query_parts if q])

        # Query RAG service for knowledge fragments
        rag_context = self.rag_service.search_context(query=query_text, n_results=3)

        variables = {
            "extracted_data": extracted_data,
            "rag_context": rag_context or "No additional RAG knowledge fragments found.",
        }

        logger.info("Executing Context Capability...")
        raw_result = self.orchestrator.execute(
            template_name=self.template_name,
            variables=variables,
            expect_json=True,
        )

        if not isinstance(raw_result, dict):
            raise LLMServiceError("Context LLM output must be a valid JSON dictionary.")
            
        ai_status = raw_result.get("ai_status", "llm_success" if raw_result else "fallback_deterministic")
        domain = raw_result.get("domain")
        confidence = float(raw_result.get("confidence", 0.0))
        if not domain or domain == "General Software":
            domain = None
            confidence = 0.0

        validated_output = {
            "ai_status": ai_status,
            "domain": domain,
            "business_capability": raw_result.get("business_capability"),
            "related_entities": raw_result.get("related_entities", []),
            "external_systems": raw_result.get("external_systems", []),
            "mapped_subsystems": raw_result.get("mapped_subsystems", []),
            "enrichment_notes": raw_result.get("enrichment_notes", ""),
            "terminology": raw_result.get("terminology", {}),
            "confidence": confidence
        }

        logger.info(
            f"Context capability complete: {len(validated_output['related_entities'])} entities mapped."
        )
        return validated_output


context_capability = ContextCapability()

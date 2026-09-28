"""
app/capabilities/base.py
========================
Abstract Base Class for all AREA AI Capabilities.

Responsibilities:
- Defines the common capability interface `execute(input_data: dict) -> dict`.
- Provides unified access to PromptOrchestrator and RAGService.
- Implements error handling and logging wrappers.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from app.services.prompt_orch import PromptOrchestrator, LLMServiceError
from app.services.rag import RAGService

logger = logging.getLogger(__name__)


class BaseAICapability(ABC):
    """
    Abstract interface for all 6 AI Capabilities.
    """

    def __init__(
        self,
        orchestrator: PromptOrchestrator | None = None,
        rag_service: RAGService | None = None,
    ) -> None:
        self.orchestrator = orchestrator or PromptOrchestrator()
        self.rag_service = rag_service or RAGService()

    @property
    @abstractmethod
    def capability_name(self) -> str:
        """Unique identifier name for this capability."""
        pass

    @property
    @abstractmethod
    def template_name(self) -> str:
        """Key for the prompt template in app/prompts/templates/."""
        pass

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the capability against input data.

        Args:
            input_data: Dict containing inputs required by this capability's prompt template.

        Returns:
            Validated structured output dictionary.

        Raises:
            LLMServiceError: If LLM call fails after retries.
            ValueError: If input or output validation fails.
        """
        pass

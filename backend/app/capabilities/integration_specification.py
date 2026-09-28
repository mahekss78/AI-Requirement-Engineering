from typing import Dict, Any
import logging
from app.services.prompt_orch import PromptOrchestrator

logger = logging.getLogger(__name__)

class IntegrationSpecificationCapability:
    """
    Stage 4C: Integration Specification Structuring Engine.
    Structures Integration Specifications.
    """
    def __init__(self, orchestrator: PromptOrchestrator):
        self.orchestrator = orchestrator
        self.template_name = "integration_specification"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        ready_for_int = input_data.get("ready_for_int", [])
        metadata = input_data.get("metadata", {})
        relationships = input_data.get("relationships", [])

        variables = {
            "ready_for_int": ready_for_int,
            "metadata": metadata,
            "relationships": relationships,
        }

        logger.info("Executing Integration Specification Capability...")
        raw_result = self.orchestrator.execute(
            template_name=self.template_name,
            variables=variables,
            expect_json=True,
        )

        return raw_result


integration_specification_capability = IntegrationSpecificationCapability(PromptOrchestrator())

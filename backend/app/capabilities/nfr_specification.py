from typing import Dict, Any
import logging
from app.services.prompt_orch import PromptOrchestrator

logger = logging.getLogger(__name__)

class NFRSpecificationCapability:
    """
    Stage 4B: NFR Specification Structuring Engine.
    Structures Non-Functional Requirements.
    """
    def __init__(self, orchestrator: PromptOrchestrator):
        self.orchestrator = orchestrator
        self.template_name = "nfr_specification"

    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        ready_for_nfr = input_data.get("ready_for_nfr", [])
        metadata = input_data.get("metadata", {})
        relationships = input_data.get("relationships", [])

        variables = {
            "ready_for_nfr": ready_for_nfr,
            "metadata": metadata,
            "relationships": relationships,
        }

        logger.info("Executing NFR Specification Capability...")
        raw_result = self.orchestrator.execute(
            template_name=self.template_name,
            variables=variables,
            expect_json=True,
        )

        return raw_result


nfr_specification_capability = NFRSpecificationCapability(PromptOrchestrator())

import json
import logging
from app.services.prompt_orch import PromptOrchestrator

logger = logging.getLogger(__name__)

class RelationshipAnalysisCapability:
    def __init__(self):
        self.orchestrator = PromptOrchestrator()

    def execute(self, payload: dict) -> dict:
        logger.info("Executing Relationship Analysis Capability")
        
        registry = payload.get("semantic_statement_registry", [])
        
        if not registry:
            return {"relationships": []}

        variables = {
            "semantic_statement_registry": json.dumps(registry, indent=2)
        }

        try:
            result = self.orchestrator.execute("relationship_analysis", variables)
            if isinstance(result, str):
                result = json.loads(result)
            return result
        except Exception as e:
            logger.error(f"Error in Relationship Analysis: {e}")
            return {"relationships": [], "error": str(e)}

relationship_analysis_capability = RelationshipAnalysisCapability()

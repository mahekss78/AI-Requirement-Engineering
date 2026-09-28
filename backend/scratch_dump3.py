import json
from app.services.prompt_orch import PromptOrchestrator

class DebugOrch(PromptOrchestrator):
    def _fallback_execute(self, template_name: str, variables: dict) -> dict:
        print("INSIDE _fallback_execute")
        registry_str = variables.get("semantic_statement_registry", "[]")
        registry = json.loads(registry_str)
        print("REGISTRY LOADED:", registry)
        univ_mid_id = next((s["statement_id"] for s in registry if "midnight" in s.get("content", "").lower()), None)
        univ_5pm_id = next((s["statement_id"] for s in registry if "5 pm" in s.get("content", "").lower()), None)
        print(f"univ_mid_id={univ_mid_id}, univ_5pm_id={univ_5pm_id}")
        return super()._fallback_execute(template_name, variables)

orch = DebugOrch()
payload = {
    "semantic_statement_registry": json.dumps([
        {
            "statement_id": "STMT-005",
            "content": "One advisor said late registration should be allowed until midnight, while the registrar said registration closes at 5 PM.",
            "processing_status": "READY"
        }
    ])
}
res = orch._fallback_execute("relationship_analysis", payload)
print("FINAL RES:", json.dumps(res, indent=2))

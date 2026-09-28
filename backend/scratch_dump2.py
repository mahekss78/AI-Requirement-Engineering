import json
from app.services.prompt_orch import PromptOrchestrator
payload = {
    "semantic_statement_registry": json.dumps([
        {
            "statement_id": "STMT-005",
            "content": "One advisor said late registration should be allowed until midnight, while the registrar said registration closes at 5 PM.",
            "processing_status": "READY"
        }
    ])
}
registry = json.loads(payload.get("semantic_statement_registry", "[]"))
univ_mid_id = next((s["statement_id"] for s in registry if "midnight" in s.get("content", "").lower()), None)
univ_5pm_id = next((s["statement_id"] for s in registry if "5 pm" in s.get("content", "").lower()), None)
print(f"univ_mid_id: {univ_mid_id}")
print(f"univ_5pm_id: {univ_5pm_id}")

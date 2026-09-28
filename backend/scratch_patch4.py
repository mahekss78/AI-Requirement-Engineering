import sys

with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/prompt_orch.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_idx = text.find('elif template_name in ("structuring", "structure"):')
end_idx = text.find('elif template_name in ("quality", "quality_scoring"):')

if start_idx == -1 or end_idx == -1:
    print('Failed', start_idx, end_idx)
    sys.exit(1)

replacement = """elif template_name in ("structuring", "structure"):
            ready_for_us = variables.get("ready_for_us", [])
            if isinstance(ready_for_us, str):
                import json
                try: ready_for_us = json.loads(ready_for_us)
                except: ready_for_us = []
            
            user_stories = []
            
            for stmt_obj in ready_for_us:
                stmt_id = stmt_obj.get("statement_id", "")
                content = stmt_obj.get("content", "")
                norm_actor = "System User"
                if "employee" in content.lower():
                    norm_actor = "Employee"
                elif "student" in content.lower():
                    norm_actor = "Student"
                    
                i_want = content.lower()
                so_that = "the business process is fulfilled"
                
                # Try to extract action
                import re
                m = re.search(r'(?:can|must|should|may|will|needs?\\s+to|shall)\\s+(.*)', content, flags=re.IGNORECASE)
                if m:
                    i_want = "to " + m.group(1).strip()
                
                user_stories.append({
                    "us_id": f"US-{len(user_stories)+1:03d}",
                    "statement_id": stmt_id,
                    "as_a": norm_actor,
                    "i_want": i_want,
                    "so_that": so_that,
                    "acceptance_criteria": [
                        {"scenario": "Default Success", "given": "valid prerequisites", "when": "action is triggered", "then": "success"}
                    ],
                    "relationship_references": [],
                    "secondary_aspects_preserved": stmt_obj.get("secondary_aspects", []),
                    "clarification_status": "NONE_REQUIRED",
                    "human_approval_status": "DRAFT"
                })
                
            return {
                "ai_status": "fallback_deterministic",
                "user_stories": user_stories
            }

        # ── QUALITY SCORING ───────────────────────────────────────────
        """
new_text = text[:start_idx] + replacement + text[end_idx:]
with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/prompt_orch.py', 'w', encoding='utf-8') as f:
    f.write(new_text)
print(len(text), len(new_text))

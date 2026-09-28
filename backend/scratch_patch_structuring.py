import sys

with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/prompt_orch.py', 'r', encoding='utf-8') as f:
    text = f.read()

start_idx = text.find('elif template_name in ("structuring", "structure"):')
end_idx = text.find('elif template_name in ("quality", "quality_analysis"):')

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
                
                # Default null for safe extraction
                norm_actor = None
                actor_evidence_status = "NOT_EXPLICITLY_SUPPORTED"
                clarification_status = "ACTOR_OR_BUSINESS_OUTCOME_REQUIRES_REVIEW"
                external_system = None
                
                import re
                
                if "student information system" in content.lower():
                    external_system = "Student Information System"
                    content_without_sys = re.sub(r'student information system', '', content, flags=re.IGNORECASE)
                else:
                    content_without_sys = content
                
                # Safe regex word bounds
                if re.search(r'\\bemployees?\\b', content_without_sys, flags=re.IGNORECASE):
                    norm_actor = "Employee"
                    actor_evidence_status = "EXPLICITLY_SUPPORTED"
                    clarification_status = "NONE_REQUIRED"
                elif re.search(r'\\bstudents?\\b', content_without_sys, flags=re.IGNORECASE):
                    norm_actor = "Student"
                    actor_evidence_status = "EXPLICITLY_SUPPORTED"
                    clarification_status = "NONE_REQUIRED"
                    
                i_want = content.lower()
                so_that = None
                
                # Try to extract action
                m = re.search(r'(?:can|must|should|may|will|needs?\\s+to|shall)\\s+(.*)', content, flags=re.IGNORECASE)
                if m:
                    i_want = "to " + m.group(1).strip()
                elif "can" in content.lower():
                    m = re.search(r'can\\s+(.*)', content, flags=re.IGNORECASE)
                    if m:
                        i_want = "to " + m.group(1).strip()
                
                if norm_actor is None:
                    as_a_val = "an authorized system user"
                else:
                    as_a_val = norm_actor
                
                user_stories.append({
                    "us_id": f"US-{len(user_stories)+1:03d}",
                    "statement_id": stmt_id,
                    "as_a": as_a_val if norm_actor is None else norm_actor,
                    "i_want": i_want,
                    "so_that": so_that,
                    "source_evidence": {
                        "actor": norm_actor,
                        "action": i_want.replace("to ", ""),
                        "external_system": external_system,
                        "business_outcome": so_that
                    },
                    "actor_evidence_status": actor_evidence_status,
                    "acceptance_criteria": [
                        {"scenario": "Default Success", "given": "valid prerequisites", "when": "action is triggered", "then": "success"}
                    ],
                    "relationship_references": [],
                    "secondary_aspects_preserved": stmt_obj.get("secondary_aspects", []),
                    "clarification_status": clarification_status,
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

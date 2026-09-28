import re

with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/prompt_orch.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = """                if norm_actor is None:
                    as_a_val = "an authorized system user"
                else:
                    as_a_val = norm_actor
                
                user_stories.append({
                    "us_id": f"US-{len(user_stories)+1:03d}",
                    "statement_id": stmt_id,
                    "as_a": as_a_val,
                    "i_want": i_want,
                    "so_that": None,"""

replacement = """                
                user_stories.append({
                    "us_id": f"US-{len(user_stories)+1:03d}",
                    "statement_id": stmt_id,
                    "as_a": norm_actor,
                    "draft_as_a": "an authorized system user" if norm_actor is None else None,
                    "i_want": i_want,
                    "so_that": None,"""

text = text.replace(target, replacement)

with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/prompt_orch.py', 'w', encoding='utf-8') as f:
    f.write(text)

import re

with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/prompt_orch.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = re.sub(r'"acceptance_criteria": \[.*?\],\s*', '', text, flags=re.DOTALL)
text = re.sub(r'"source_system": "Core Application",', '"source_system": None,', text, flags=re.DOTALL)
text = re.sub(r'"interaction_purpose": "Data Sync",', '"interaction_purpose": None,', text, flags=re.DOTALL)
text = re.sub(r'"direction": "BIDIRECTIONAL",', '"direction": None,', text, flags=re.DOTALL)
text = re.sub(r'"protocol": "REST API",', '"protocol": None,', text, flags=re.DOTALL)

unspecified = '"unspecified_details_requiring_clarification": [\n                        "Source application identity",\n                        "Interaction purpose",\n                        "Data exchanged",\n                        "Interaction direction",\n                        "Trigger",\n                        "Protocol/interface",\n                        "Authentication"\n                    ],'
text = re.sub(r'"unspecified_details_requiring_clarification": \[.*?\],', unspecified, text, flags=re.DOTALL)

text = re.sub(r'draft_as_a = None', 'draft_as_a = None', text, flags=re.DOTALL)
text = text.replace('"draft_as_a": draft_as_a,', '"draft_as_a": draft_as_a,')

with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/prompt_orch.py', 'w', encoding='utf-8') as f:
    f.write(text)

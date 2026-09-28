with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/tests/test_stage04.py', 'r') as f:
    text = f.read()

text = text.replace('req1.requirement_data.get("stage1_registry", [])', 'req1.requirement_data.get("extraction", {}).get("semantic_statement_registry", [])')
text = text.replace('req2.requirement_data.get("stage1_registry", [])', 'req2.requirement_data.get("extraction", {}).get("semantic_statement_registry", [])')

text = text.replace('req1.requirement_data.get("user_stories", [])', 'req1.requirement_data.get("structuring", {}).get("user_stories", [])')
text = text.replace('req2.requirement_data.get("user_stories", [])', 'req2.requirement_data.get("structuring", {}).get("user_stories", [])')

text = text.replace('req1.requirement_data.get("nfr_specifications", [])', 'req1.requirement_data.get("nfr_structuring", {}).get("nfr_specifications", [])')
text = text.replace('req2.requirement_data.get("nfr_specifications", [])', 'req2.requirement_data.get("nfr_structuring", {}).get("nfr_specifications", [])')

text = text.replace('req1.requirement_data.get("integration_specifications", [])', 'req1.requirement_data.get("int_structuring", {}).get("integration_specifications", [])')
text = text.replace('req2.requirement_data.get("integration_specifications", [])', 'req2.requirement_data.get("int_structuring", {}).get("integration_specifications", [])')

with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/tests/test_stage04.py', 'w') as f:
    f.write(text)

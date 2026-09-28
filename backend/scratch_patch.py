with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/runner.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('"structuring": structuring_res,', '"structuring": structuring_res,\n                "nfr_structuring": nfr_res,\n                "int_structuring": int_res,')

with open('c:/Users/Admin/Downloads/Assisted-AI-1/backend/app/services/runner.py', 'w', encoding='utf-8') as f:
    f.write(text)

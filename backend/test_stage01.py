import os
import sys
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__))))

from app.capabilities.extraction import extraction_capability
from app.capabilities.semantic_classification import semantic_classification_capability

expense_text = """
Meeting: Employee Expense Reimbursement System
Participants:
Aisha – Business Analyst
Rohan – Finance Manager

Aisha: Employees should be able to submit expense claims.
Rohan: Expense reimbursements should normally be completed within 5 business days.
Meera: employees should receive reimbursement immediately after approval.
Rohan: The application should handle expense submissions very quickly.
Aisha: The system should integrate with the existing Payroll Management System.
Meera: It is not yet decided how long rejected expense claims should be retained.
"""

university_text = """
Title: University Registration
Students can search courses.
Registration should be completed within 3 seconds.
The platform must support 8,000 concurrent students.
Can students register for a course after the deadline?
One advisor said late registration should be allowed until midnight...
...while the registrar said registration closes at 5 PM.
The system should check prerequisite completion with the Student Information System.
The system should provide appropriate access.
"""

def run_tests():
    out = []
    out.append("=== EXPENSE DATASET STAGE 0 ===")
    stage0_res = extraction_capability.execute({"document_content": expense_text})
    out.append(json.dumps(stage0_res, indent=2))

    out.append("\n=== EXPENSE DATASET STAGE 1 ===")
    stage1_res = semantic_classification_capability.execute({"normalized_statements": stage0_res.get("normalized_statements", [])})
    for c in stage1_res.get("classifications", []):
        out.append(f"[{c.get('statement_id')}] [{c.get('primary_type')}] [{c.get('subtype')}] {c.get('content')} (Reason: {c.get('ba_reasoning')} | Clarify: {c.get('requires_clarification')} | Review: {c.get('requires_human_review')})")

    out.append("\n=== UNIVERSITY DATASET STAGE 0 ===")
    stage0_univ = extraction_capability.execute({"document_content": university_text})
    out.append(json.dumps(stage0_univ, indent=2))

    out.append("\n=== UNIVERSITY DATASET STAGE 1 ===")
    stage1_univ = semantic_classification_capability.execute({"normalized_statements": stage0_univ.get("normalized_statements", [])})
    for c in stage1_univ.get("classifications", []):
        out.append(f"[{c.get('statement_id')}] [{c.get('primary_type')}] [{c.get('subtype')}] {c.get('content')} (Reason: {c.get('ba_reasoning')} | Clarify: {c.get('requires_clarification')} | Review: {c.get('requires_human_review')})")

    with open("test_output.txt", "w") as f:
        f.write("\n".join(out))
        
run_tests()

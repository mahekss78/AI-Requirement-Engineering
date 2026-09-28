import os
import sys
import json

# Add backend dir to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import Base, Requirement
from app.services.runner import capability_runner
import uuid

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

from app.models.models import Project
proj_id = uuid.uuid4()
proj = Project(id=proj_id, name="Test")
db.add(proj)
db.commit()

# EXPENSE REIMBURSEMENT
doc_content_expense = """
Title: Expense Reimbursement System
Employees should be able to submit expense claims.
Expense reimbursements should normally be completed within 5 business days.
employees should receive reimbursement immediately after approval.
The application should handle expense submissions very quickly.
The system should integrate with the existing Payroll Management System.
It is not yet decided how long rejected expense claims should be retained.
"""
proj_id = uuid.uuid4()
req_exp = Requirement(id=uuid.uuid4(), project_id=proj_id, title="Expense", current_state="DRAFT")
db.add(req_exp)
db.commit()

# UNIVERSITY REGISTRATION
doc_content_univ = """
Title: University Registration
Students can search courses.
Registration should be completed within 3 seconds.
The platform must support 8,000 concurrent students.
Can students register for a course after the deadline?
One advisor said late registration should be allowed until midnight...
...while the registrar said registration closes at 5 PM.
The system should check prerequisite completion with the Student Information System.
"""
req_univ = Requirement(id=uuid.uuid4(), project_id=proj_id, title="Univ", current_state="DRAFT")
db.add(req_univ)
db.commit()

out_md = []
out_md.append("# Stage 2 Execution Results")

# Run Expense
try:
    print("Running Expense...")
    res_exp = capability_runner.run_pipeline(db, req_exp.id, doc_content_expense, "Expense")
    registry = res_exp.requirement_data["extraction"]["semantic_statement_registry"]
    relationships = res_exp.requirement_data["extraction"].get("relationships", [])
    out_md.append("## Dataset: Expense Reimbursement")
    out_md.append("### Statements and Status")
    out_md.append("```json\n" + json.dumps(registry, indent=2) + "\n```")
    out_md.append("### Relationships")
    out_md.append("```json\n" + json.dumps(relationships, indent=2) + "\n```")
except Exception as e:
    print(f"Error Expense: {e}")

# Run Univ
try:
    print("Running Univ...")
    res_univ = capability_runner.run_pipeline(db, req_univ.id, doc_content_univ, "University")
    registry = res_univ.requirement_data["extraction"]["semantic_statement_registry"]
    relationships = res_univ.requirement_data["extraction"].get("relationships", [])
    out_md.append("## Dataset: University Registration")
    out_md.append("### Statements and Status")
    out_md.append("```json\n" + json.dumps(registry, indent=2) + "\n```")
    out_md.append("### Relationships")
    out_md.append("```json\n" + json.dumps(relationships, indent=2) + "\n```")
except Exception as e:
    print(f"Error Univ: {e}")

with open("C:/Users/Admin/.gemini/antigravity/brain/269ac0e4-675c-4249-9eb8-21f67c88da19/stage02_results.md", "w") as f:
    f.write("\n".join(out_md))
print("Done writing results.")

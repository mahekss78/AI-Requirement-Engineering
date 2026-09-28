import json
import logging
from app.services.runner import CapabilityRunner
from app.models.models import Requirement, Project
from app.database.connection import SessionLocal, Base, engine
import uuid

logging.basicConfig(level=logging.INFO)

# Set up in-memory SQLite DB
Base.metadata.create_all(bind=engine)

def format_registry(data):
    # Only keep some fields for readability
    return [
        {
            "statement_id": s.get("statement_id"),
            "content": s.get("content"),
            "processing_status": s.get("processing_status"),
            "artifact_routes": s.get("artifact_routes")
        } for s in data
    ]

def main():
    db = SessionLocal()
    
    # Create a dummy project
    project = Project(id=uuid.uuid4(), name="Test Project")
    db.add(project)
    db.commit()
    
    runner = CapabilityRunner()
    
    # Test 1: Expense Document
    text1 = """
Employees should be able to submit expense claims. 
Expense reimbursements should normally be completed within 5 business days. 
In fact, employees should receive reimbursement immediately after approval. 
The application should handle expense submissions very quickly.
The system should integrate with the existing Payroll Management System.
It is not yet decided how long rejected expense claims should be retained.
"""
    print("Running Expense...")
    req1 = Requirement(project_id=project.id, title="Expense Doc", requirement_data={"source": text1})
    db.add(req1)
    db.commit()
    runner.run_pipeline(db, req1.id, text1)
    db.refresh(req1)
    print('STRUCTURING KEYS:', req1.requirement_data.get('structuring', {}).keys())
    
    # Test 2: Univ Document
    text2 = """
Students can search courses. Registration should be completed within 3 seconds. The platform must support 8,000 concurrent students.
Can students register for a course after the deadline?
One advisor said late registration should be allowed until midnight, while the registrar said registration closes at 5 PM.
The system should check prerequisite completion with the Student Information System.
"""
    print("Running Univ...")
    req2 = Requirement(project_id=project.id, title="Univ Doc", requirement_data={"source": text2})
    db.add(req2)
    db.commit()
    runner.run_pipeline(db, req2.id, text2)
    db.refresh(req2)
    print('REQ2 KEYS:', req2.requirement_data.keys())
    
    # Write output to markdown
    output = "# Stage 4 User Story, NFR, and Integration Structuring Results\n"
    
    output += "## Dataset: Expense Reimbursement\n"
    output += "### Statement Registry (Truncated)\n```json\n"
    output += json.dumps(format_registry(req1.requirement_data.get("extraction", {}).get("semantic_statement_registry", [])), indent=2)
    output += "\n```\n"
    output += "### User Stories\n```json\n"
    output += json.dumps(req1.requirement_data.get("structuring", {}).get("user_stories", []), indent=2)
    output += "\n```\n"
    output += "### NFR Specifications\n```json\n"
    output += json.dumps(req1.requirement_data.get("nfr_structuring", {}).get("nfr_specifications", []), indent=2)
    output += "\n```\n"
    output += "### Integration Specifications\n```json\n"
    output += json.dumps(req1.requirement_data.get("int_structuring", {}).get("integration_specifications", []), indent=2)
    output += "\n```\n"
    
    output += "## Dataset: University Registration\n"
    output += "### Statement Registry (Truncated)\n```json\n"
    output += json.dumps(format_registry(req2.requirement_data.get("extraction", {}).get("semantic_statement_registry", [])), indent=2)
    output += "\n```\n"
    output += "### User Stories\n```json\n"
    output += json.dumps(req2.requirement_data.get("structuring", {}).get("user_stories", []), indent=2)
    output += "\n```\n"
    output += "### NFR Specifications\n```json\n"
    output += json.dumps(req2.requirement_data.get("nfr_structuring", {}).get("nfr_specifications", []), indent=2)
    output += "\n```\n"
    output += "### Integration Specifications\n```json\n"
    output += json.dumps(req2.requirement_data.get("int_structuring", {}).get("integration_specifications", []), indent=2)
    output += "\n```\n"
    
    with open("C:/Users/Admin/.gemini/antigravity/brain/269ac0e4-675c-4249-9eb8-21f67c88da19/stage04_results.md", "w") as f:
        f.write(output)
        
    print("Done writing results.")

if __name__ == "__main__":
    main()

import json
from app.database.session import SessionLocal
from app.models.requirement import Requirement

db = SessionLocal()
req2 = db.query(Requirement).filter(Requirement.title == "University Registration").first()
data = req2.requirement_data

print("RELATIONSHIPS:")
print(json.dumps(data.get("extraction", {}).get("relationships", []), indent=2))
print("---")
print("REGISTRY:")
print(json.dumps(data.get("extraction", {}).get("semantic_statement_registry", []), indent=2))

# AI Requirement Engineering Assistant (AREA)
## Product Design Specification (PDS)
### Volume 4 — Engineering Guide

---

## Chapter 20: Prompt Templates & Libraries

### 20.1 Business Purpose
The quality of our requirements depends directly on our LLM instructions. The **Prompt Templates & Libraries** standardize our system prompts, ensuring the LLM extracts features, detects gaps, checks for conflicts, and structures stories consistently.

### 20.2 Design Decisions
* **Externalized Prompts:** Prompts are stored in separate files in `app/prompts/templates/` as markdown text. This lets developers edit and tune prompt templates without touching the application's core code.
* **JSON Output Enforcement:** All prompts instruct the LLM to return data in a structured JSON schema. This ensures the output can be parsed directly into the **Requirement Object** database.

### 20.3 Component Responsibilities
* **`PromptLoader`:** Loads template files from disk and caches them in memory during server startup.
* **`PromptOrchestrator`:** Injects runtime variables (current requirement state, RAG search results, version memory) into the loaded template.

### 20.4 Inputs and Outputs
* **Inputs:** Template ID (e.g., `extraction_prompt`) and formatting context parameters.
* **Outputs:** Formatted prompt strings ready to be sent to the LLM API.

### 20.5 Implementation Notes (Key Prompt Templates)

#### 20.5.1 Ingestion & Extraction Prompt (`extraction.md`)
```markdown
SYSTEM:
You are an expert Business Analyst. Your task is to extract core requirements from the provided source text.
You must extract:
1. Actors (roles performing actions)
2. Features (system capabilities)
3. Business Rules (logic constraints, validations)
4. Constraints (technical limits, platforms)
5. Assumptions (unverified expectations)

You must output a JSON object matching this schema:
{
  "extracted_features": [{"title": "str", "description": "str"}],
  "actors": [{"name": "str", "description": "str"}],
  "business_rules": [{"rule_id": "BR-X", "statement": "str"}],
  "constraints": [{"constraint_id": "CO-X", "statement": "str"}],
  "assumptions": [{"statement": "str"}]
}

USER:
Document Source Content:
{document_content}
```

#### 20.5.2 Gap & Ambiguity Detection Prompt (`gap_detection.md`)
```markdown
SYSTEM:
You are a Quality QA and Requirements Auditor. Your task is to inspect the extracted entities for missing information (gaps) and vague language (ambiguities).
Identify:
1. Missing details (e.g., return rules without return periods).
2. Non-testable statements (e.g., "website should be fast" - what is fast?).
3. Missing edge cases (e.g., what happens if payment fails?).

Generate 2 to 5 targeted clarification questions for stakeholders. Specify options (e.g. Yes/No) where possible to make answering easy.

Output format:
{
  "gap_score_deduction": float,
  "clarification_questions": [
    {
      "question": "str",
      "assigned_role": "CLIENT" | "DEVELOPER" | "QA" | "PRODUCT_OWNER",
      "options": ["str"]
    }
  ]
}

USER:
Requirement Data:
{requirement_json}
```

#### 20.5.3 Story & Acceptance Criteria Structuring Prompt (`structuring.md`)
```markdown
SYSTEM:
You are an Agile Product Owner. Convert the provided features and business rules into standard Agile user stories and Gherkin acceptance criteria.
* User Stories must use the format: As a [User Role], I want to [Action], so that [Value].
* Acceptance Criteria must use Gherkin syntax: Given [Context], When [Action], Then [Result]. Ensure you write negative scenarios and edge cases.

Output format:
{
  "user_stories": [{"id": "US-X", "as_a": "str", "i_want": "str", "so_that": "str"}],
  "acceptance_criteria": [
    {
      "id": "AC-X",
      "story_id": "US-X",
      "scenario": "str",
      "given": "str",
      "when": "str",
      "then": "str"
    }
  ]
}

USER:
Extracted requirement features and rules:
{requirement_json}
```

---

## Chapter 21: AI Capability Orchestration Workflow

### 21.1 Business Purpose
The system must coordinate multiple AI services in order. The **AI Capability Orchestration Workflow** coordinates this execution pipeline, ensuring requirements are parsed, analyzed, and structured before saving them to the database.

### 21.2 Design Decisions
* **Deterministic Service Pipeline:** Rather than using complex agent loops, the platform runs a linear Python execution pipeline. This ensures predictable, reliable results and keeps token costs low for the MVP.
* **Stateful Database checkpoints:** The workflow updates the database at the end of each step. This acts as a savepoint, preventing data loss if a later step fails.

### 21.3 Component Responsibilities
* **`CapabilityRunner`:** The orchestrator class. It coordinates connections, reads documents, invokes the AI capabilities in order, and updates the Requirement Object's state in the database.

### 21.4 Inputs and Outputs
* **Inputs:** Requirement UUID and the normalized source documents.
* **Outputs:** Updated Requirement Object saved in the database, with its state transitioned to `AI_ANALYZED`.

### 21.5 Implementation Notes (Orchestration Engine)
The `CapabilityRunner` pipeline is implemented in Python as follows:

```python
import logging
from uuid import UUID
from app.models.models import Requirement
from app.services.prompt_orch import PromptOrchestrator
from app.capabilities.extraction import ExtractionService
from app.capabilities.context import ContextService
from app.capabilities.gap_detection import GapDetectionService
from app.capabilities.conflict import ConflictDetectionService
from app.capabilities.structuring import StructuringService
from app.capabilities.quality import QualityService

logger = logging.getLogger(__name__)

class CapabilityRunner:
    def __init__(self, db_session, prompt_orchestrator: PromptOrchestrator):
        self.db = db_session
        self.orch = prompt_orchestrator
        
        # Instantiate capabilities
        self.extraction = ExtractionService(self.orch)
        self.context = ContextService(self.orch)
        self.gap = GapDetectionService(self.orch)
        self.conflict = ConflictDetectionService(self.orch)
        self.structuring = StructuringService(self.orch)
        self.quality = QualityService(self.orch)

    async def run_pipeline(self, requirement_id: UUID):
        logger.info(f"Starting pipeline execution for requirement {requirement_id}")
        
        # Load Requirement Object record
        req_record = self.db.query(Requirement).filter(Requirement.id == requirement_id).first()
        if not req_record:
            raise ValueError("Requirement not found")
            
        req_data = req_record.requirement_data

        try:
            # 1. Extraction Phase
            extracted_entities = await self.extraction.execute(req_data)
            req_data["content"].update(extracted_entities)

            # 2. Context Dependency Mapping
            relationships = await self.context.execute(req_data)
            req_data["relationships"] = relationships

            # 3. Gap & Ambiguity Detection
            gap_results = await self.gap.execute(req_data)
            req_data["open_questions_count"] = len(gap_results.get("questions", []))
            # Write open questions to the database

            # 4. Conflict Detection
            conflicts = await self.conflict.execute(req_data)
            # Log conflicts to database

            # 5. Structuring Phase (Stories & Criteria)
            structured_stories = await self.structuring.execute(req_data)
            req_data["content"]["user_stories"] = structured_stories.get("user_stories", [])
            req_data["content"]["acceptance_criteria"] = structured_stories.get("acceptance_criteria", [])

            # 6. Quality Checks & Confidence Scoring
            quality_metrics = await self.quality.execute(req_data)
            req_data["confidence_score"] = quality_metrics.get("normalized_score", 0.0)

            # Commit updates to database and set state
            req_record.requirement_data = req_data
            req_record.current_state = "AI_ANALYZED"
            req_record.assigned_role = "BUSINESS_ANALYST"
            self.db.commit()
            logger.info(f"Pipeline execution completed successfully for {requirement_id}")
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Pipeline execution failed for {requirement_id}: {str(e)}")
            req_record.current_state = "FAILED"
            self.db.commit()
            raise e
```

---

## Chapter 22: Testing Strategy & Mocking

### 22.1 Business Purpose
To ensure code quality, developers must be able to run tests locally without calling the live LLM APIs. This saves API costs and makes testing faster and more reliable.

### 22.2 Design Decisions
* **Standardized Testing Framework:** Uses `pytest` for all unit and integration tests.
* **Mocked LLM API layer:** All OpenAI / LLM service calls are mocked during testing. Tests supply mock LLM JSON responses to verify that the parsing, database, and state machine transitions work correctly.

### 22.3 Component Responsibilities
* **`conftest.py`:** Configures test environments, initializes a temporary in-memory database, and sets up global mock fixtures.
* **`test_pipeline.py`:** Verifies the capability orchestration steps and checks state transition rules.

### 22.4 Inputs and Outputs
* **Inputs:** Test documents containing mock requirement texts.
* **Outputs:** Test pass/fail reports and coverage metrics.

### 22.5 Implementation Notes (Mock Test Example)
The following example test shows how to mock the LLM and test the ingestion pipeline:

```python
import pytest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from app.services.runner import CapabilityRunner

@pytest.fixture
def mock_db():
    # In-memory SQLite session setup
    ...

@pytest.fixture
def mock_prompt_orchestrator():
    orchestrator = AsyncMock()
    # Mock return values for prompt executions
    orchestrator.execute_llm.return_value = {
        "extracted_features": [{"title": "Payment Gateway", "description": "Support payments"}],
        "actors": [{"name": "Customer", "description": "Buys items"}],
        "business_rules": [],
        "constraints": [],
        "assumptions": []
    }
    return orchestrator

@pytest.mark.asyncio
async def test_extraction_capability(mock_db, mock_prompt_orchestrator):
    # Initialize the Capability Runner with mocked orchestrator
    runner = CapabilityRunner(db_session=mock_db, prompt_orchestrator=mock_prompt_orchestrator)
    
    req_id = uuid4()
    # Run the pipeline and assert it transitions the state correctly
    with patch("app.capabilities.extraction.ExtractionService.execute") as mock_extract:
        mock_extract.return_value = {
            "epic_title": "E-Commerce Payment Integration",
            "user_stories": [],
            "acceptance_criteria": []
        }
        
        await runner.run_pipeline(req_id)
        
        # Verify the database was updated
        updated_req = mock_db.query(Requirement).filter(Requirement.id == req_id).first()
        assert updated_req.current_state == "AI_ANALYZED"
        assert updated_req.requirement_data["confidence_score"] > 0.0
```

---

## Chapter 23: Implementation Roadmap & Next Steps

### 23.1 Business Purpose
A structured roadmap ensures that developers build core features first, delivering a working MVP within the 4-week internship timeline.

### 23.2 Design Decisions
* **Core-First Priority:** The roadmap focuses on building the core features (Database setup, Ingestion Pipeline, and the BA Workspace) in the first two weeks. Frontend workspaces and Jira integration are built in the final weeks.
* **Continuous Integration Gating:** Every week's deliverables must pass automated tests before work on the next week's features begins.

### 23.3 Implementation Phases

```
┌─────────────────────────────────┐
│ WEEK 1: Project Setup & DB      │ ──> Setup Docker, PostgreSQL tables, Ingestion pipeline
└─────────────────────────────────┘
┌─────────────────────────────────┐
│ WEEK 2: AI Capabilities Engine  │ ──> Implement Ingestion, Extraction, and Gap Detection
└─────────────────────────────────┘
┌─────────────────────────────────┐
│ WEEK 3: Workspaces & Routing    │ ──> Build BA Console and Client/Dev/QA/PO workspaces
└─────────────────────────────────┘
┌─────────────────────────────────┐
│ WEEK 4: Jira Integration & QA   │ ──> Implement Jira REST exporter, final testing & freeze
└─────────────────────────────────┘
```

#### Week-by-Week Deliverables Matrix

| Week | Phase | Focus Areas | Key Deliverables |
| :--- | :--- | :--- | :--- |
| **Week 1** | **Setup & Database** | Project initialization and database configuration. | Docker environment ready; PostgreSQL tables and schemas initialized; Document ingestion and file parsing working. |
| **Week 2** | **AI Processing Services** | AI capabilities pipeline integration. | Extraction and Gap Detection services working; Prompt Orchestrator and memory services functioning; Test suite with mocked APIs running. |
| **Week 3** | **Orchestration & Workspaces** | State machine controller and UI views. | State machine transition engine complete; BA Dashboard and workspace views built; Notification routing working. |
| **Week 4** | **Jira Integration & Hand-off** | Downstream connections and final testing. | Jira REST exporter complete; End-to-end testing of the pipeline finished; Final QA verification complete. |

---

### Future Extensions for Volume 4
* **Automated CI/CD Pipeline:** Setting up a GitHub Actions workflow that automatically runs the pytest suite and builds Docker images on every code commit.
* **Auto-Generating Unit Tests:** Using the structured Gherkin acceptance criteria to automatically generate boilerplate test code for development frameworks (e.g., Python Behave or Jest).

# AI Requirement Engineering Assistant (AREA)
## Product Design Specification (PDS)
### Volume 3 — Technical Architecture

---

## Chapter 15: Frontend Architecture

### 15.1 Business Purpose
The user interface must serve five different stakeholder roles, each with different tasks and technical skills. The **Frontend Architecture** provides a responsive application that separates workspace views and coordinates dashboard updates.

### 15.2 Design Decisions
* **Single-Page Application (SPA) with React & Vite:** Built on React and Vite for fast development and rendering. Vite is chosen for its near-instant hot module replacement (HMR) and lightweight build sizes.
* **Premium Vanilla CSS Design System:** Uses standard Vanilla CSS for complete styling control. It features glassmorphic cards, smooth transitions, a dark-mode theme, and Outfit/Inter fonts. Tailwind CSS is excluded to keep CSS structure simple.
* **Mock Role Context:** For the MVP, a global React Context manages simulated roles. Users can switch between views (BA, Client, Developer, QA, PO) with a single click, testing the system's role separation without requiring an authentication server.
* **Authentication Placeholder for Production:** In future enterprise releases, the mockup selector will be replaced by an OAuth2 / OpenID Connect authorization server (such as Keycloak or Auth0). JSON Web Tokens (JWT) will be stored in HTTP-only cookies, and client-side routes will be protected using standard React Guard components based on Role-Based Access Control (RBAC).

### 15.3 Component Responsibilities
* **`AppShell` / Layout Manager:** Controls navigation header, role selector, and sidebar layout.
* **`DashboardGrid` (BA Workspace):** Renders the metrics panels (Confidence Score radial charts, Health Status indicator badges) and the requirement list grid.
* **`RequirementDetailPanel`:** Displays the active Requirement Object, including User Stories, Gherkin scenarios, and comments.
* **`ClarificationCenter` (Client Workspace):** Renders open questions as simple multiple-choice poll cards.
* **`ReviewConsole` (Dev/QA/PO Workspaces):** Displays review checklists, risk ratings, and priority selectors.

### 15.4 Inputs and Outputs
* **Inputs:** JSON structures retrieved from backend REST endpoints.
* **Outputs:** User actions (clicks, votes, text edits) serialized and sent as HTTP POST/PUT requests.

### 15.5 Implementation Notes (Folder Structure)
The React application's file layout is structured as follows:

```
frontend/
├── public/
│   └── favicon.ico
├── src/
│   ├── assets/
│   │   └── logo.svg
│   ├── components/
│   │   ├── AppShell.css
│   │   ├── AppShell.jsx
│   │   ├── ConfidenceDial.jsx
│   │   ├── StatusBadge.jsx
│   │   └── RelationshipGraph.jsx
│   ├── context/
│   │   └── RoleContext.jsx      # Simulated role context and active user state
│   ├── views/
│   │   ├── BaDashboard.jsx       # BA Console: uploads and overview
│   │   ├── ClientPortal.jsx      # Client Console: open clarifications
│   │   ├── DeveloperPortal.jsx   # Dev Portal: feasibility & risks
│   │   ├── QaPortal.jsx          # QA Workspace: testability & Gherkin review
│   │   └── ProductOwnerBoard.jsx # PO Dashboard: prioritization & backlog mapping
│   ├── App.jsx
│   ├── index.css                 # Color tokens, styles, layout grids
│   └── main.jsx
├── index.html
├── package.json
└── vite.config.js
```

---

## Chapter 16: Backend Architecture

### 16.1 Business Purpose
The backend services must handle heavy document ingestion, coordinate stateless AI capabilities, process state machine changes, and synchronize data with Jira.

### 16.2 Design Decisions
* **FastAPI Web Framework:** Built on FastAPI to leverage asynchronous endpoints, automatic OpenAPI documentation, and Python data validation via Pydantic.
* **Service Dependency Injection:** All database sessions, prompt orchestrator contexts, and RAG instances are injected into FastAPI endpoints using standard dependency-injection patterns.
* **Non-Blocking Background Tasks:** AI pipeline execution is long-running (10s to 60s). Instead of blocking HTTP threads, FastAPI's `BackgroundTasks` executes pipelines in a separate thread pool. The endpoint immediately returns an HTTP 202 Accepted response with a processing status.
* **Configuration Layer:** All credentials and variables (OpenAI keys, Database URLs, SMTP settings, model parameters) are managed via Pydantic `BaseSettings` reading from a `.env` file.
* **Authentication Placeholder for Production:** An OAuth2 bearer scheme will secure REST endpoints in production. The backend will validate incoming JWT tokens and enforce endpoint-level RBAC decorators (e.g., restricting `/api/requirements/{id}/transition` to users with the `BUSINESS_ANALYST` role).

### 16.3 Folder Structure

```
backend/
├── app/
│   ├── api/
│   │   ├── dependencies.py      # DB session, auth, and service providers
│   │   └── router.py            # FastAPI route controllers
│   ├── services/
│   │   ├── lifecycle.py         # State machine and transition engine
│   │   ├── memory.py            # Version diffing and history tracker
│   │   ├── prompt_orch.py       # Prompt rendering and LLM wrapper
│   │   ├── rag.py               # Vector store indexer and retriever
│   │   └── audit_notify.py      # Event auditor and webhook/email dispatcher
│   ├── capabilities/
│   │   ├── base.py              # Base class for AI capabilities
│   │   ├── extraction.py        # Entities and business rules extraction
│   │   ├── context.py           # Dependency and graph context linker
│   │   ├── gap_detection.py     # Missing details analysis
│   │   ├── conflict.py          # contradiction finder
│   │   ├── structuring.py       # Gherkin story formatter
│   │   └── quality.py           # Integrity checker
│   ├── models/
│   │   └── models.py            # PostgreSQL SQLAlchemy schemas
│   ├── schemas/
│   │   └── schemas.py           # Pydantic schemas (e.g. RequirementObject)
│   ├── database/
│   │   ├── connection.py        # SQLAlchemy engine and session makers
│   │   └── migrations/          # Alembic migrations directory
│   ├── prompts/
│   │   └── templates/           # System prompt templates
│   ├── config.py                # Pydantic Settings class (.env reader)
│   └── utils/
│       └── helpers.py           # String normalizers and general utils
├── tests/
│   └── test_pipeline.py         # Capability mock tests
├── .env
├── Dockerfile
├── requirements.txt
└── main.py
```

### 16.4 Backend Execution Flow
The following sequence diagram displays the step-by-step processing of requirements, from file upload to Jira synchronization:

```mermaid
sequenceDiagram
    autonumber
    actor BA as Business Analyst
    participant FE as Frontend View
    participant BE as FastAPI API
    participant BG as FastAPI BackgroundTasks
    participant CR as Capability Runner
    participant DB as Postgres & ChromaDB
    
    BA->>FE: Upload Document File
    FE->>BE: POST /api/requirements/ingest
    activate BE
    BE->>DB: Write Raw Document & Set State (INGESTING)
    BE->>BG: Queue Runner.run_pipeline()
    BE-->>FE: HTTP 202 Accepted (Req Object JSON, State: INGESTING)
    deactivate BE
    
    activate BG
    BG->>CR: Run Capability Pipeline
    activate CR
    CR->>CR: Parser & Normalizer (Extract plain text)
    CR->>CR: Execute AI Capabilities (Extract, Link, Gap, Structuring, Quality)
    CR->>DB: Save enriched Requirement Object
    CR->>DB: Log Audit Event & Trigger Notifications
    CR->>DB: Update State to AI_ANALYZED
    deactivate CR
    BG-->>FE: Webhook/UI Polling (Update state: AI_ANALYZED)
    deactivate BG
    
    BA->>FE: Review & Edit Draft in Cockpit
    FE->>BE: PUT /api/requirements/{id} (Save edits)
    BE->>DB: Save changes, increment minor version
    BE-->>FE: HTTP 200 OK
    
    BA->>FE: Trigger Stakeholder Review (Dev/QA/PO)
    FE->>BE: POST /api/requirements/{id}/transition (Trigger transition)
    BE->>DB: Update State to PEER_REVIEW
    BE-->>FE: HTTP 200 OK (State: PEER_REVIEW)
    
    BA->>FE: Freeze and Baseline Requirement
    FE->>BE: POST /api/requirements/{id}/transition (Transition to FROZEN)
    BE->>DB: Lock Requirement (Increment Major Version, Set read-only)
    BE-->>FE: HTTP 200 OK (State: FROZEN)
    
    BA->>FE: Export Requirement to Jira
    FE->>BE: POST /api/requirements/{id}/export-jira
    BE->>BE: Create Epics, Stories, and Tasks via Jira REST API
    BE->>DB: Update Artifact Links (Save Jira Issue Keys to DB)
    BE-->>FE: HTTP 200 OK (Export sync complete)
```

### 16.5 Capability Runner Execution Order
The `CapabilityRunner` coordinates the sequential processing of requirements, passing data through the following steps:

```
[Normalized Text]
       │
       ▼
 1. Extraction  ──> Extract Entities, Business Rules, and Constraints
       │
       ▼
 2. Context     ──> Create relationship links and map dependencies
       │
       ▼
 3. Gap Detect  ──> Identify missing attributes and raise questions
       │
       ▼
 4. Conflict    ──> Check semantic conflicts across documents
       │
       ▼
 5. Structuring ──> Formulate User Stories and Gherkin Scenarios
       │
       ▼
 6. Quality     ──> Validate syntax and evaluate Confidence Metrics
       │
       ▼
[Central Database]
```

### 16.6 Implementation Notes (Background Job Code)
The pipeline runs asynchronously using FastAPI's built-in background tasks:

```python
from fastapi import APIRouter, BackgroundTasks, Depends
from app.services.runner import CapabilityRunner
from app.schemas import IngestRequest

router = APIRouter()

async def execute_analysis_pipeline(runner: CapabilityRunner, req_id: str):
    await runner.run_pipeline(req_id)

@router.post("/requirements/ingest")
async def ingest_document(
    payload: IngestRequest, 
    background_tasks: BackgroundTasks, 
    runner: CapabilityRunner = Depends()
):
    # Initialize the database records in "INGESTING" state
    req_id = await runner.initialize_draft(payload.project_id, payload.file_name)
    
    # Process the pipeline in the background
    background_tasks.add_task(execute_analysis_pipeline, runner, req_id)
    
    return {"requirement_id": req_id, "status": "INGESTING", "message": "Pipeline execution started."}
```

---

## Chapter 17: Database & Vector Store Design

### 17.1 Business Purpose
The platform must store relational metadata (versions, comments, and audit histories) with ACID guarantees, and run fast semantic searches over compliance guidelines and glossaries.

### 17.2 Design Decisions
* **Transactional Layer (PostgreSQL):** Uses PostgreSQL as the transactional database. It stores structured requirement metadata and uses a `JSONB` column to store the dynamic Requirement Object payload.
* **Vector Store Layer (ChromaDB):** ChromaDB is used as a local vector database for the MVP. It stores and queries embedding vectors, keeping setup simple without needing a cloud database.

### 17.3 Component Responsibilities
* **Database Session Manager:** Manages SQL connections and runs database operations.
* **Chroma Vector Client:** Generates text embeddings and runs vector queries.
* **Database Migrations Manager:** Manages schema updates using Alembic.

### 17.4 Inputs and Outputs
* **PostgreSQL Inputs:** SQL queries, JSONB updates, and audit records. **Outputs:** Target records and version lists.
* **Vector Store Inputs:** Query string embeddings. **Outputs:** Top-k similar text fragments.

### 17.5 Implementation Notes (Expanded SQL DDL)
To support all features, the database schema is structured as follows:

```sql
-- Projects Table
CREATE TABLE projects (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Documents Table (Ingested Files)
CREATE TABLE documents (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size INT NOT NULL,
    normalized_content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Central Requirements Table
CREATE TABLE requirements (
    id UUID PRIMARY KEY,
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    current_state VARCHAR(50) NOT NULL,
    assigned_role VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    requirement_data JSONB NOT NULL, -- Pydantic RequirementObject Schema
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Requirement Version History Table (Immutable Records)
CREATE TABLE requirement_versions (
    id UUID PRIMARY KEY,
    requirement_id UUID REFERENCES requirements(id) ON DELETE CASCADE,
    version VARCHAR(20) NOT NULL,
    requirement_data JSONB NOT NULL,
    change_rationale TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Clarification Questions Table
CREATE TABLE clarifications (
    id UUID PRIMARY KEY,
    requirement_id UUID REFERENCES requirements(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    assigned_role VARCHAR(50) NOT NULL,
    status VARCHAR(30) DEFAULT 'PENDING' NOT NULL, -- 'PENDING', 'ANSWERED'
    options JSONB, -- For multiple choice formats e.g., ["Yes", "No"]
    answer TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    answered_at TIMESTAMP
);

-- Comments & Annotations Table
CREATE TABLE comments (
    id UUID PRIMARY KEY,
    requirement_id UUID REFERENCES requirements(id) ON DELETE CASCADE,
    author_role VARCHAR(50) NOT NULL,
    target_element_id VARCHAR(50) NOT NULL, -- US-1, AC-1, etc.
    comment_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Notifications Table
CREATE TABLE notifications (
    id UUID PRIMARY KEY,
    recipient_role VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Audit Logs Table (Immutable History)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,
    requirement_id UUID REFERENCES requirements(id) ON DELETE CASCADE,
    actor_role VARCHAR(50) NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    prev_state VARCHAR(50),
    new_state VARCHAR(50),
    change_diff JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);
```

---

## Chapter 18: APIs & Jira Integration Details

### 18.1 Business Purpose
To streamline the development handoff, frozen requirements must be exported directly to Jira Cloud, creating Epics, Stories, and Tasks with complete bidirectional traceability.

### 18.2 Design Decisions
* **Jira REST API v3 Integration:** Communicates with Jira using basic authentication with an API Token.
* **Mapping Schema:** Epics are created for high-level requirement containers, User Stories represent the functional requirements, and sub-tasks are created for the acceptance criteria.
* **Traceability Sync:** The external Jira issue ID is written back to the **Requirement Object**, creating a permanent sync link between the two systems.

### 18.3 Component Responsibilities
* **Jira Client Service:** Communicates with Jira REST endpoints.
* **Payload Mapper:** Translates the Pydantic Requirement Object fields into Jira's JSON schemas.
* **Callback Handler:** Tracks updates in Jira and logs them back to the database.

### 18.4 Inputs and Outputs
* **Inputs:** Approved Requirement Object.
* **Outputs:** HTTP requests sent to Jira API, and saved sync indicators.

### 18.5 Detailed API Endpoint Specifications

The system exposes the following REST API endpoints:

| Method | Endpoint Path | Description | Payload Schema | Response Schema |
| :--- | :--- | :--- | :--- | :--- |
| **POST** | `/api/requirements/ingest` | Triggers document ingestion and kicks off the background analysis pipeline. | `{"project_id": UUID, "file_name": str, "file_content": Base64String}` | `{"requirement_id": UUID, "status": "INGESTING"}` |
| **GET** | `/api/requirements` | Fetches a list of all requirements for a project. | Query params: `project_id`, `state` | `[{"id": UUID, "title": str, "version": str, "current_state": str}]` |
| **GET** | `/api/requirements/{id}` | Fetches the full structured Requirement Object by its UUID. | None | Complete `RequirementObject` JSON |
| **PUT** | `/api/requirements/{id}` | Updates requirement content (used when the BA edits text). | Modified `RequirementObject` JSON | Updated `RequirementObject` JSON |
| **POST** | `/api/requirements/{id}/transition` | Transitions a requirement to a new state in the state machine. | `{"event": "APPROVE_DRAFT" \| "REQUEST_REWORK"}` | `{"id": UUID, "new_state": str, "owner": str}` |
| **POST** | `/api/clarifications` | Submits a question to a stakeholder. | `{"requirement_id": UUID, "question": str, "role": str, "options": []}` | `{"clarification_id": UUID, "status": "PENDING"}` |
| **PUT** | `/api/clarifications/{id}` | Submits the answer to a clarification question. | `{"answer": str}` | `{"clarification_id": UUID, "status": "ANSWERED"}` |
| **GET** | `/api/clarifications` | Fetches pending clarifications. | Query params: `assigned_role` | `[{"id": UUID, "question": str, "options": []}]` |
| **POST** | `/api/comments` | Adds a review comment to a specific story or criterion. | `{"requirement_id": UUID, "author_role": str, "target_element_id": str, "text": str}` | `{"comment_id": UUID, "created_at": timestamp}` |
| **GET** | `/api/comments` | Fetches all comments for a requirement. | Query params: `requirement_id` | `[{"id": UUID, "author_role": str, "text": str}]` |
| **POST** | `/api/requirements/{id}/export-jira` | Exports the frozen requirement to Jira. | `{"jira_domain": str, "project_key": str}` | `{"status": "SUCCESS", "jira_epic_key": str}` |
| **GET** | `/api/requirements/{id}/history` | Fetches the version history log. | None | `[{"version": str, "updated_at": timestamp, "rationale": str}]` |
| **POST** | `/api/requirements/{id}/rollback` | Rolls back the requirement to a previous version. | `{"target_version": str}` | Complete `RequirementObject` JSON (Restored) |
| **GET** | `/api/notifications` | Fetches unread notifications. | Query params: `recipient_role` | `[{"id": UUID, "message": str}]` |
| **GET** | `/api/dashboard/metrics` | Fetches project-level health and confidence scores. | Query params: `project_id` | `{"average_confidence": float, "at_risk_count": int}` |

---

## Chapter 19: Deployment Architecture

### 19.1 Business Purpose
To simplify setup and configuration for developers, the platform uses a containerized deployment architecture that runs all services locally.

### 19.2 Design Decisions
* **Multi-Container Docker Compose Setup:** The application is split into three containers: the React frontend, the FastAPI backend, and the PostgreSQL database.
* **Environment File Segregation:** Environment variables (database passwords, LLM API keys, ports) are stored in a central `.env` file for security and ease of configuration.

### 19.3 Component Topology
The diagram below shows how the local system components interact with external APIs:

```mermaid
graph TD
    Browser[Web Browser / User]
    
    subgraph LocalContainers["Docker Compose Environment"]
        ReactApp[React Frontend Container]
        FastAPIApp[FastAPI Backend Container]
        Postgres[(PostgreSQL Transactional DB)]
        ChromaDB[(Chroma Vector DB)]
    end
    
    subgraph ExternalAPIs["External SaaS Endpoints"]
        OpenAI[OpenAI / LLM Service]
        Jira[Atlassian Jira Cloud]
    end

    %% Routing
    Browser -->|HTTP Port 5173| ReactApp
    ReactApp -->|REST API Port 8000| FastAPIApp
    FastAPIApp -->|SQL Connection| Postgres
    FastAPIApp -->|Local Vector Queries| ChromaDB
    FastAPIApp -->|HTTPS / API Token| OpenAI
    FastAPIApp -->|HTTPS / OAuth| Jira
```

### 19.4 Inputs and Outputs
* **Inputs:** Configuration variables defined in `.env`.
* **Outputs:** Live local containers accessible at `http://localhost:5173` (Frontend) and `http://localhost:8000` (Backend).

### 19.5 Implementation Notes (Docker Compose Blueprint)
The system is deployed locally using the following `docker-compose.yml`:

```yaml
version: '3.8'

services:
  database:
    image: postgres:15-alpine
    container_name: area-db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: secret_db_password
      POSTGRES_DB: area_db
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - area-network

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: area-backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:secret_db_password@database:5432/area_db
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - CHROMA_DB_PATH=/app/chroma_db
    depends_on:
      - database
    volumes:
      - ./backend/chroma_db:/app/chroma_db
    networks:
      - area-network

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: area-frontend
    ports:
      - "5173:80"
    depends_on:
      - backend
    networks:
      - area-network

volumes:
  pgdata:

networks:
  area-network:
    driver: bridge
```

---

### Future Extensions for Volume 3
* **Kubernetes (Helm Charts) Blueprint:** To scale the system in production, future updates will package the containers into Kubernetes pods with load balancing.
* **Redis Caching Layer:** Adding a Redis container to cache LLM responses and manage websocket connections for real-time collaboration.

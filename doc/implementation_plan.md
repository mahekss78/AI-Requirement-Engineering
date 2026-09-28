# Implementation Plan - AREA Platform

This plan defines the step-by-step implementation blueprint for the **AI-Driven Requirement Engineering Assistant (AREA)** platform, based strictly on the approved Product Design Specification (PDS).

---

## 1. Technology Stack & Dependency Versions

### 1.1 Backend Stack (Python 3.11+)
The backend uses FastAPI for API routing and SQLAlchemy for ORM database connections:

* **FastAPI:** `0.110.0` (Core REST framework)
* **Uvicorn:** `0.28.0` (ASGI Web Server)
* **SQLAlchemy:** `2.0.28` (Object Relational Mapper)
* **Psycopg2-binary:** `2.9.9` (PostgreSQL driver)
* **ChromaDB:** `0.4.24` (Local Vector Database)
* **OpenAI SDK:** `1.13.3` (LLM communication)
* **Pydantic:** `2.6.4` (Data validation)
* **Pydantic-Settings:** `2.2.1` (Config manager)
* **PyPDF2:** `3.0.1` (PDF text extraction)
* **python-docx:** `1.1.0` (Docx text extraction)
* **HTTPX:** `0.27.0` (Asynchronous HTTP calls for API/Jira)
* **Pytest & Pytest-Asyncio:** `0.23.5` (Testing suite)

### 1.2 Frontend Stack (Node.js 20+)
The frontend is a single-page application built on Vite and React:

* **Vite:** `5.1.4` (Build tool and local dev server)
* **React:** `18.2.0` (View library)
* **React-DOM:** `18.2.0` (DOM rendering)
* **React-Router-DOM:** `6.22.2` (Routing)
* **Lucide-React:** `0.344.0` (Standard UI icons library)
* **CSS:** Vanilla CSS (no styling frameworks)

---

## 2. Project Folder Structure

```
area-project/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── dependencies.py
│   │   │   └── router.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── lifecycle.py
│   │   │   ├── memory.py
│   │   │   ├── prompt_orch.py
│   │   │   ├── rag.py
│   │   │   └── audit_notify.py
│   │   ├── capabilities/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── extraction.py
│   │   │   ├── context.py
│   │   │   ├── gap_detection.py
│   │   │   ├── conflict.py
│   │   │   ├── structuring.py
│   │   │   └── quality.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── models.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py
│   │   ├── database/
│   │   │   ├── __init__.py
│   │   │   └── connection.py
│   │   ├── prompts/
│   │   │   └── templates/
│   │   │       ├── extraction.md
│   │   │       ├── gap_detection.md
│   │   │       ├── structuring.md
│   │   │       └── conflict.md
│   │   ├── config.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── helpers.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   └── test_pipeline.py
│   ├── .env.example
│   ├── Dockerfile
│   ├── requirements.txt
│   └── main.py
├── frontend/
│   ├── public/
│   ├── src/
│   │   ├── assets/
│   │   ├── components/
│   │   │   ├── AppShell.css
│   │   │   ├── AppShell.jsx
│   │   │   ├── ConfidenceDial.jsx
│   │   │   ├── StatusBadge.jsx
│   │   │   └── RelationshipGraph.jsx
│   │   ├── context/
│   │   │   └── RoleContext.jsx
│   │   ├── views/
│   │   │   ├── BaDashboard.jsx
│   │   │   ├── ClientPortal.jsx
│   │   │   ├── DeveloperPortal.jsx
│   │   │   ├── QaPortal.jsx
│   │   │   └── ProductOwnerBoard.jsx
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── Dockerfile
│   ├── package.json
│   └── vite.config.js
└── docker-compose.yml
```

---

## 3. Database Migration Order

To maintain referential integrity, PostgreSQL tables must be created in the following order:

1. **`projects`:** No external dependencies.
2. **`documents`:** References `projects(id)` with cascade delete constraints.
3. **`requirements`:** References `projects(id)`. Contains the primary requirement JSONB payload.
4. **`requirement_versions`:** References `requirements(id)`. Stores snapshots of versions.
5. **`clarifications`:** References `requirements(id)`. Houses Q&A data.
6. **`comments`:** References `requirements(id)`. Houses annotations.
7. **`notifications`:** No external key dependencies.
8. **`audit_logs`:** References `requirements(id)`. Stores diff trace records.

---

## 4. Development Milestones & Estimated Schedule

We divide the implementation into 4 sequential weekly phases. Each phase must be completed and validated before the next starts.

```
       Phase 1 (3 Days)              Phase 2 (6 Days)              Phase 3 (5 Days)              Phase 4 (4 Days)
┌────────────────────────────┐┌────────────────────────────┐┌────────────────────────────┐┌────────────────────────────┐
│ M1: Skeleton & DB          ││ M2: Ingestion & AI Services││ M3: Workspaces & Routing   ││ M4: Jira Sync & Testing    │
└────────────────────────────┘└────────────────────────────┘└────────────────────────────┘└────────────────────────────┘
```

### Milestone 1: Core Configuration & Database Schema (Days 1–3)
* **Goal:** Initialize folder layouts, set up configurations, initialize the database tables, and run connection checks.
* **Deliverables:**
  * Root folder structure and configuration variables.
  * DB connection pooling and ORM model mapping.
  * Verified REST connection status from backend main entry point.

### Milestone 2: Normalization & AI Processing Pipeline (Days 4–9)
* **Goal:** Build the parser services, RAG vector client, stateless AI capabilities, and the asynchronous BackgroundTask runner.
* **Deliverables:**
  * Working parser modules for PDF, Word, and text.
  * Prompt Orchestration wrapper and ChromaDB vector indexer.
  * Capability runner executing 6 AI services sequentially.

### Milestone 3: Workspaces UI & State Coordinator (Days 10–14)
* **Goal:** Build the React dashboards, implement the State Gating engine, and route stakeholder tasks.
* **Deliverables:**
  * Unified React Single-Page Application with simulated role contexts.
  * Central state machine validating transitions and ownership roles.
  * Notification dispatching and comment annotation views.

### Milestone 4: Jira Integration & Final Validation (Days 15–18)
* **Goal:** Link Jira Cloud integration endpoints, run full local container environments, and run test suites.
* **Deliverables:**
  * Verified Jira issue mapping and ID writebacks.
  * Local docker-compose environments spinning up database, vector index, backend, and frontend.
  * Unit tests running successfully with mocked LLM calls.

---

## 5. File-by-File Implementation Sequence

To keep development orderly, modules are built from the bottom up. We write dependencies first, core logic next, and API interfaces last.

### Phase 1: Core Configuration & Database
1. **[NEW]** `backend/requirements.txt` (Define dependency libraries).
2. **[NEW]** `backend/app/config.py` (Define Settings class for config loading).
3. **[NEW]** `backend/app/database/connection.py` (Initialize engine and SessionLocal session builder).
4. **[NEW]** `backend/app/models/models.py` (Write SQLAlchemy class models).
5. **[NEW]** `backend/app/schemas/schemas.py` (Define Pydantic schema structures).
6. **[NEW]** `backend/main.py` & `backend/app/api/router.py` (Define root FastAPI routes).

### Phase 2: Ingestion & AI Capabilities
7. **[NEW]** `backend/app/utils/helpers.py` (Write parsing code for pdf/docx).
8. **[NEW]** `backend/app/prompts/templates/` (Add markdown template prompt files).
9. **[NEW]** `backend/app/services/prompt_orch.py` (Write LLM template rendering code).
10. **[NEW]** `backend/app/services/rag.py` (Initialize ChromaDB collection mappings).
11. **[NEW]** `backend/app/capabilities/base.py` (Add baseline stateless capability class).
12. **[NEW]** `backend/app/capabilities/` (Write extraction, context, gap, conflict, structuring, and quality scripts).
13. **[NEW]** `backend/app/services/runner.py` (Write BackgroundTask CapabilityRunner workflow).

### Phase 3: Workspaces UI & State Coordinator
14. **[NEW]** `backend/app/services/lifecycle.py` (Implement transitions state machine logic).
15. **[NEW]** `backend/app/services/audit_notify.py` (Implement DB logging and notification queues).
16. **[MODIFY]** `backend/app/api/router.py` (Map state transition routes).
17. **[NEW]** `frontend/package.json` (Specify Vite/React dependencies).
18. **[NEW]** `frontend/src/context/RoleContext.jsx` (Write context for workspace views).
19. **[NEW]** `frontend/src/index.css` (Set design system CSS tokens).
20. **[NEW]** `frontend/src/components/` (Write layout components: AppShell, Dial, badge).
21. **[NEW]** `frontend/src/views/` (Write dashboards: BaDashboard, ClientPortal, DeveloperPortal, QaPortal, ProductOwnerBoard).

### Phase 4: Jira Integration & Final Validation
22. **[NEW]** `backend/app/services/jira.py` (Write HTTPX-based Jira Cloud integration client).
23. **[MODIFY]** `backend/app/api/router.py` (Add Jira export route).
24. **[NEW]** `backend/tests/conftest.py` & `backend/tests/test_pipeline.py` (Write test suites).
25. **[NEW]** `backend/Dockerfile`, `frontend/Dockerfile`, and `docker-compose.yml` (Configure local containers).

---

## 6. Implementation Risks & Mitigation Strategies

* **Risk 1: JSON Schema Violation:** The LLM output may break Pydantic validation schemas.
  * *Mitigation:* The Prompt Orchestrator enforces JSON response formats and validates schemas. If validation fails, it catches the error and retries.
* **Risk 2: ChromaDB Dependency Issues:** ChromaDB requires compiling binaries that can fail on some systems.
  * *Mitigation:* If local ChromaDB builds fail, we fall back to a simple in-memory vector storage class mapping embeddings in memory for the MVP.
* **Risk 3: API Token Invalidation:** Incomplete environment credentials can cause connection crashes.
  * *Mitigation:* The config manager checks for credentials on startup. If keys are missing, it logs a warning and disables the affected capabilities, preventing runtime exceptions.

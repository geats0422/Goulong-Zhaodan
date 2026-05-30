# AGENTS.md

This is a monorepo containing a frontend and backend. Agentic coding tools should work in the appropriate subdirectory based on the task.

## Scope
- **Frontend**: `frontend/` — Vue 3
- **Backend**: `backend/` — Python + FastAPI
- **Tests**: follow project-local setup (frontend/backend)

---

## Communication Language
- **All replies must be in Chinese (中文)** unless the user explicitly requests otherwise in a non-Chinese language.
- This includes code comments, commit messages, documentation, and any written communication.

---

## Project Structure
- `frontend/` — Frontend application
- `backend/` — Backend application
- `docs/` — Documentation (git/, designs/, plans/)
- `.opencode/` — OpenCode configuration

## Technology Stack
- **Frontend interaction**: Vue 3 (fast MVP delivery; can evolve toward React if complexity grows)
- **Backend core**: Python + FastAPI (decoupled architecture for high concurrency and RESTful APIs)
- **AI orchestration**: PydanticAI (structured extraction first; can transition to LangGraph for complex state flows)
- **Data storage**: PostgreSQL (core business persistence and rule storage)
- **Async buffering**: Redis (I/O buffering for large-file parsing and long-running tasks)
- **Infrastructure & compliance**: Alibaba Cloud stack (security/compliance readiness and private deployment path)

## Required Verification Before Finishing
- Lint + typecheck (frontend)
- Lint + type check (backend)
- Run targeted tests for behavior changes
- Run full test suite for structural changes

## Agent Guidance
- Prefer improving shared abstractions over copying logic.
- Search for existing components/composables/constants before creating new ones.
- Keep changes narrowly scoped and consistent with existing patterns.
- Do not add dependencies unless materially justified.
- Update this file if you add new commands, workflows, or conventions.

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

## Virtual Environment
- **Backend uses `uv`** as the virtual environment and package manager.
- Always run backend commands through `uv run` (e.g., `uv run python`, `uv run pytest`, `uv run uvicorn`).
- Do not use `python` or `pip` directly in the backend directory; use `uv run` to ensure the correct environment.

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

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **Goulong-Zhaodan** (4101 symbols, 7315 relationships, 229 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/Goulong-Zhaodan/context` | Codebase overview, check index freshness |
| `gitnexus://repo/Goulong-Zhaodan/clusters` | All functional areas |
| `gitnexus://repo/Goulong-Zhaodan/processes` | All execution flows |
| `gitnexus://repo/Goulong-Zhaodan/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |
| Work in the Tests area (302 symbols) | `.claude/skills/generated/tests/SKILL.md` |
| Work in the V1 area (116 symbols) | `.claude/skills/generated/v1/SKILL.md` |
| Work in the Services area (93 symbols) | `.claude/skills/generated/services/SKILL.md` |
| Work in the Pages area (18 symbols) | `.claude/skills/generated/pages/SKILL.md` |
| Work in the Prompts area (12 symbols) | `.claude/skills/generated/prompts/SKILL.md` |
| Work in the Models area (11 symbols) | `.claude/skills/generated/models/SKILL.md` |
| Work in the Agents area (7 symbols) | `.claude/skills/generated/agents/SKILL.md` |
| Work in the Cluster_0 area (5 symbols) | `.claude/skills/generated/cluster-0/SKILL.md` |
| Work in the Composables area (5 symbols) | `.claude/skills/generated/composables/SKILL.md` |
| Work in the Cluster_84 area (4 symbols) | `.claude/skills/generated/cluster-84/SKILL.md` |
| Work in the Scripts area (3 symbols) | `.claude/skills/generated/scripts/SKILL.md` |

<!-- gitnexus:end -->

# CyberForge — Implementation Plan

**Normative source:** `TECHNICAL_SPECIFICATION.md` (SRS v3.0, 11.11.2026), especially §§0, 21–24, 26–27.
**State:** Planning baseline. No phase is complete until validated in the actual repository.
**Rule:** Execute only one user-approved phase at a time; never automatically move to the next phase.

## Definitions of status

- **NOT STARTED** — no implementation evidence.
- **IN PROGRESS** — approved work underway.
- **BLOCKED** — material prerequisite or decision unavailable.
- **REVIEW** — implementation finished; tests, user review or acceptance outstanding.
- **ACCEPTED** — criteria verified and phase approved by project owner.

## Roadmap

| Phase | Name | Status | Deliverable and acceptance focus |
|---|---|---|---|
| 0 | Project Foundation | NOT STARTED | Inspect repo and tools, establish Python 3.12/uv project, test/lint baseline, Git hygiene, foundational documentation; commands verified |
| 1 | Main UI Shell | NOT STARTED | Dark PySide6 shell, Guest view, sidebar mode controls, shared scenario panel, mode routing; UI smoke tests |
| 2 | Users & Groups | NOT STARTED | Login, Argon2id, 3 roles, demo accounts/groups, permission enforcement; denied-access tests |
| 3 | Scenario Management | NOT STARTED | Create/edit scenarios with unique IDs, persistence, statuses, versioned drafts; SQLite integration tests |
| 4 | LLM Integration | NOT STARTED | LLMGateway, provider adapter, Gemini configuration, deterministic MockLLMProvider; schema and fallback tests |
| 5 | Specialized Agents | NOT STARTED | Typed I/O contracts for four specialized agents and bounded orchestration; mock agent tests |
| 6 | Email Constructor | NOT STARTED | Email shell, generation, preview, code view, regeneration, explicit save and validation; UI tests |
| 7 | Web Constructor | NOT STARTED | Web templates, isolated Qt WebEngine, generation, preview, code view, explicit save; security and UI tests |
| 8 | Scenario Integration | NOT STARTED | Shared Email→Web context, internal link validation, readiness gate, immutable publishing; integration tests |
| 9 | Learner Simulation | NOT STARTED | Email and Web exercises, controlled navigation, recorded attempts/events, safe completion without Web; end-to-end tests |
| 10 | Scoring & Mentor | NOT STARTED | Versioned deterministic rubrics, evaluation, result display, LLM explanations without score edits; reproducibility tests |
| 11 | Analytics Mode | NOT STARTED | Read-only scenario statistics, deduplicated learner table, missing-data rules, filters, CSV/JSON export, RBAC; analytics tests |
| 12 | Finalization | NOT STARTED | Full regression/security checks, Windows 11 package, demonstration dataset, docs and release checklist |

## Implementation requirements for each phase

For the active phase, Codex must record:
1. Objective and exact SRS sections/requirements covered.
2. Dependencies and assumptions, including unresolved SRS items.
3. User-visible working outcome and demonstration steps.
4. Target files/modules and a minimal change sequence.
5. Test commands and acceptance criteria (including negative/security cases where applicable).
6. Actual check results and evidence.
7. Remaining work and a recommendation for the next phase.

Each phase can be divided into substeps, but no substep should leave the working branch in an untestable state without documenting the limitation. Use `docs/DEVELOPMENT_LOG.md` for decisions and verification details.

## Phase 0 — first approved unit of work

**Goal:** prepare the repository for reproducible, incremental development; do not implement the complete product or jump ahead to UI functionality.

**Initial actions:**
- Inspect branch, Git status, files, Python/uv/Qt availability and existing MCP integrations where accessible.
- Preserve existing README, code and uncommitted work.
- Confirm the checked-in SRS is v3.0, then read its status labels and Phase 0 scope.
- Identify whether WSL Ubuntu can launch PySide6 and flag Windows-only runtime/build checks separately.
- Create or adjust the minimal project skeleton, `pyproject.toml`, Python package, test and lint configuration, `.gitignore`, `.env.example`, project startup instructions and baseline checks as justified by existing repository state.
- Avoid live API calls and do not add actual secrets. Do not implement LLM agents, databases, role logic, simulators or full UI in this phase.

**Acceptance gate:**
- The repository contains SRS, AGENTS.md and a maintained plan/log.
- Python and dependency setup command is documented and verified in the actual environment.
- A minimal package import and baseline automated test succeed.
- Ruff and pytest commands work (or any environment blocker is explicitly documented).
- No secrets or generated/local state appear in version control.
- Git diff is scoped, and a concise Phase 0 report is available for user review.
- Status changes to REVIEW after evidence is recorded; ACCEPTED only following user approval.

## Review protocol

The owner evaluates the working demonstration, diff, test evidence and SRS traceability. If approved, Codex may start the next phase in a *new task/session* based on the updated repository plan/log. If rejected, repair only the current phase.

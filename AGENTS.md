Use English for all internal planning, technical analysis, code-related communication, progress updates, and final responses to the project owner. Keep CyberForge's end-user UI, labels, validation messages, and notifications in Ukrainian, and preserve the established language of existing project documents. Do not expose private chain-of-thought reasoning.

# CyberForge — instructions for OpenAI Codex

## Mission and source of truth

CyberForge is a local Windows 11 educational simulator and constructor of social-engineering training scenarios. It is developed as part of a master's dissertation, using Python 3.12 and PySide6. Its training flow is Email → Web → Scoring → Feedback.

Before making changes, inspect the relevant sections of these sources and reuse
already verified project context; do not repeatedly reread unrelated implementation:
1. `TECHNICAL_SPECIFICATION.md` — authoritative SRS, version 3.0.
2. `docs/IMPLEMENTATION_PLAN.md` — implementation phases, acceptance gates, progress.
3. `docs/DEVELOPMENT_LOG.md` — previous implementation decisions and verification results.
4. Existing project files, tests and architectural decisions relevant to the task.

If documents conflict, follow the SRS for approved product requirements. Do not silently override an approved requirement. The SRS labels `[ЗАТВЕРДЖЕНО]`, `[ОБОВ'ЯЗКОВА ВИМОГА]`, `[ТЕХНІЧНЕ РІШЕННЯ]`, `[ПРОПОЗИЦІЯ]`, `[ВІДКЛАДЕНО]` and `[ПОТРЕБУЄ УЗГОДЖЕННЯ]` have distinct meanings. Do not treat proposals, deferred features or decisions awaiting approval as committed MVP scope.

## Scope of work and phase gate

- Work on one approved phase or narrowly scoped task at a time. The project roadmap is Phase 0 through Phase 12, as specified in SRS section 23.
- Before coding, inspect the repository, working tree, dependencies and existing components; never duplicate working functionality or overwrite uncommitted user changes.
- Present a short implementation plan mapped to relevant SRS sections and acceptance criteria.
- Inside an approved phase, work in small, testable increments and fix regressions before proceeding.
- Do NOT start the next phase without explicit user approval, even if the current phase is complete.
- For ambiguous decisions that change approved functionality, security, evaluation semantics or architecture, record options and ask for approval. For minor reversible implementation details, make a justified choice and document it.
- Maintain `docs/IMPLEMENTATION_PLAN.md` and `docs/DEVELOPMENT_LOG.md` after each completed increment or phase.
- For a user-approved phase, Codex may update a clean local `main` with a fast-forward, create a feature branch, and, after successful relevant verification, commit, push that feature branch and create a Pull Request targeting `main`. Preserve uncommitted changes; report failed checks before publishing.
- Never merge into `main`, force-push, delete branches, rewrite history or perform destructive Git operations without explicit user approval.

## Engineering conventions

- Application code, API names, symbols, classes and variables: English. End-user UI and documentation intended for the dissertation: Ukrainian. Communication with the project owner, progress reports and technical explanations: English.
- Python 3.12; prefer typed code; small cohesive modules; src layout. Keep domain, application services, UI, persistence, analytics and AI integrations separate.
- Use the agreed stack where relevant: PySide6, Qt WebEngine, Pydantic v2, SQLite, SQLAlchemy 2.x, Alembic, LangChain, LangGraph, Gemini behind `LLMGateway`, `uv`, `pytest`, `pytest-qt` and Ruff.
- Add only necessary dependencies; verify their current official documentation and compatible versions. Do not invent APIs or quietly replace the SRS technology decisions.
- Do not create every proposed directory in advance; evolve the structure when code actually needs it.
- Build and test offline with `MockLLMProvider` whenever possible. Make real API use explicitly configurable; never require a live Gemini key for the baseline tests.
- Cloud priority (owner-approved 13.11.2026): Groq `openai/gpt-oss-120b` is primary; Gemini `gemini-4-hydrogen` is the preferred verified backup (owner live connectivity SUCCESS on 2026-11-13), enabled only through explicit local configuration. Other keys still require access verification. Gemini 3.5 Flash-Lite is optional; Gemini 3.8 Flash remains explicitly selectable with unresolved access. Without explicit cloud configuration, default to offline MockLLMProvider. Keep providers replaceable; never infer account access from published availability.
- Keep `.env`, tokens, credentials, local databases and other secrets out of Git. Supply safe `.env.example` values. Use secure password hashing (Argon2id) and an appropriate OS secret store where specified.

## Non-negotiable domain and security requirements

- Training content, identities, accounts, organizations and credentials must be synthetic. No real phishing delivery, external credential collection, unauthorized access or unsafe downloads.
- Web Simulator must isolate rendering and block uncontrolled external network requests; `display_url` is only visual text and MUST NOT be navigated to as a real URL. Use internal resource identifiers for navigation.
- Never execute arbitrary LLM-generated HTML, JavaScript, CSS or commands. Validate structured output, escape data and render only through controlled templates.
- Enforce role permissions in application services, not just UI. Administrator, Instructor and Learner have distinct privileges. Learners cannot see other learners' results; instructors cannot access unrelated private scenarios.
- Constructor and Analytics share one scenario identity and database. Analytics is read-only and must not duplicate scoring or permit scenario edits.
- A published scenario version is immutable; later changes create a new draft. Do not overwrite saved artifacts or unsaved UI edits silently. Do not publish an incomplete or invalid scenario.
- `ScoringService` calculates results deterministically from events, versioned rubrics and a published scenario. LLM agents may explain existing scores but must never assign or modify them.
- Missing results, incomplete attempts and actual zero scores are distinct. Skipping Web due to a correct safe decision must not automatically produce a zero Web score.
- Never send real learners' personal data, actual credentials, secrets or unanonymized attempt results to a cloud LLM.
- Verify NIST assertions from official documents. NIST Phish Scale describes email-detection difficulty, not a learner score or a web-page difficulty scale.

## Quality gates

For each relevant change:
1. Add or update appropriate unit, integration, UI and security tests.
2. Run project checks (prefer `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest` after these commands are configured). Report exactly what ran and what could not run.
3. Test both successful and forbidden access paths where permissions are involved.
4. Confirm behavior under `MockLLMProvider` without external network access.
5. On Windows-specific Qt/WebEngine behavior, state clearly whether it was actually verified on Windows 11; WSL tests alone are not Windows validation.
6. Record evidence, limitations and remaining risks; never mark an untested requirement as completed.

### Owner-approved verification workflow (12.11.2026)

- Make narrow changes; run focused tests first. Once the change set is stable,
  run full Ruff lint/format checks and the complete pytest suite before publishing.
  Repeat the complete suite only when further code changes could affect verified behavior.
- Keep existing regression/security tests. Do not omit relevant data-integrity,
  RBAC, migration, or concurrent-write checks. Linux and Windows CI must both pass
  for the final PR HEAD before any separately authorized merge.
- Use relevant real WSLg GUI checks for visual/interaction changes and owner manual
  WSLg functional acceptance. Avoid repeating unrelated manual scenarios or producing
  redundant screenshots, diagnostics, or audit reports.
- Build/package and isolated-wheel checks are required when packaging, dependencies,
  migrations, startup, or installation behavior changes; a simple UI-only change
  does not require repeating these checks. Keep concise evidence in the existing log.
- For Phases 3–11, routine physical native Windows 11 acceptance is deferred to
  Phase 12. Earlier native checks remain appropriate for a concrete platform defect
  or significant technical risk. Do not refresh/copy source snapshots into the
  existing Phase 2 native Windows test environment for each phase; preserve it.
- Phase 12 must cover native Windows 11, packaging/executable/installer behavior,
  DPI, keyboard, permissions, security, regression and end-to-end verification.
  Windows CI is not physical Windows 11 acceptance. Track the deferral as a risk,
  not a verified requirement; the SRS Windows 11 MVP criterion remains in force.

## Completion report

At the end of a task, respond in English with:
- phase / task and SRS requirements covered;
- implemented behavior;
- files added or modified;
- design decisions;
- exact checks run and their results;
- unresolved issues or environmental limitations;
- whether the acceptance gate passed;
- the proposed next action (without automatically starting the next phase).

## MCP usage policy

- Use GitHub MCP for remote repository inspection and supported branch, commit and Pull Request operations. Local Git is appropriate for working-tree inspection, checkout, fast-forward synchronization, local commits and transport of verified commits; do not replace a requested MCP connectivity check with local Git.
- Use Context7 for current library/framework documentation and OpenAI Developer Docs MCP for OpenAI-specific documentation. Prefer official primary sources for APIs and technical requirements.
- Check connections with small functional read requests; report each unavailable server and any fallback used. Never modify or expose MCP credentials.
- Developer MCP integrations are tooling only, not runtime dependencies of CyberForge agents (SRS §27.4).

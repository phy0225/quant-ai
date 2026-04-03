# Quant AI — Agent Execution Guide

This file is a working guide for coding agents operating in this repository.
It is derived from `CLAUDE.md`, but is intentionally more execution-oriented:
it focuses on how to inspect, implement, test, and verify changes without
breaking the main product flow.

## 1. Project Mission

Quant AI is a multi-agent quantitative trading assistant for A-share equities.
Four analysis agents collaborate to produce recommendations, which then go
through approval before updating portfolio holdings.

Core product path:

1. Portfolio page selects symbols and current holdings.
2. Decision pipeline runs technical, fundamental, news, and sentiment agents.
3. System creates recommendations and an `ApprovalRecord`.
4. User approves, rejects, or modifies weights.
5. Approved recommendations update `PortfolioHolding` and create snapshots.

When making changes, protect this flow first.

## 2. Stack And Code Layout

Backend:
- Python 3.11
- FastAPI
- SQLAlchemy async
- SQLite
- AKShare data integrations

Frontend:
- Vue 3
- TypeScript
- Vite
- TailwindCSS

Important directories:
- `backend/agents/`: agent logic and pipeline orchestration
- `backend/routers/`: API routes and business flow
- `backend/services/`: external data access and graph helpers
- `backend/models.py`: ORM models
- `backend/schemas.py`: request/response schemas
- `backend/tests/`: test suite
- `frontend/src/pages/`: feature pages
- `frontend/src/api/`: frontend API access layer
- `frontend/src/types/`: frontend type definitions

## 3. Non-Negotiable Engineering Rules

### Backend

1. AKShare is synchronous.
   Any AKShare call in async code must use `asyncio.to_thread()`.

2. AKShare APIs are unstable.
   Prefer fallback probing across multiple function names or payload formats.

3. No data means no hallucination.
   If an agent lacks sufficient data, return conservative output:
   `direction="hold"` and low confidence.

4. Schema consistency matters.
   If a route returns or accepts new fields, update `schemas.py`.

5. Model changes require test-awareness.
   If ORM fields change, confirm test fixtures in `backend/tests/conftest.py`
   still create tables and default seed rows correctly.

6. Use local time consistently.
   Prefer `datetime.now()` over `datetime.utcnow()` in this repo.

### Frontend

1. New API interactions belong in `frontend/src/api/`, not inline in pages,
   unless touching existing legacy code that has not yet been refactored.

2. New pages or flows must keep router and type definitions aligned.

3. Never treat `fetch()` as success without checking `response.ok`.
   Always surface backend `detail` messages to the UI when possible.

## 4. Agent Working Process

Follow this order unless there is a strong reason not to:

1. Read the relevant route/page/service first.
2. Identify the user-facing flow affected.
3. Check existing tests covering that flow.
4. Reproduce with the smallest meaningful test command.
5. Implement the smallest safe fix.
6. Add or extend regression tests for the exact bug.
7. Re-run targeted tests.
8. Re-run broader flow tests if the change touches shared logic.
9. Build frontend if frontend files changed.

Do not stop after "the code looks right". Verify it.

## 5. Preferred Test Strategy

### Fast path

Use focused tests first:

```powershell
cd backend
.\.venv\Scripts\pytest -q tests/test_api.py::TestSomething::test_case
```

### Flow validation

For business-flow changes, run:

```powershell
cd backend
.\.venv\Scripts\pytest -q tests/test_flows.py tests/test_scenarios.py tests/test_units.py
```

### Full backend regression

Before closing larger backend work:

```powershell
cd backend
.\.venv\Scripts\pytest -q tests
```

### Frontend validation

If any frontend file changes:

```powershell
cd frontend
npm run build
```

## 6. Testing Priorities

When adding or changing behavior, ensure these are covered:

### Main flow coverage

- Decision trigger and listing
- Recommendation generation
- Approval approve/reject/modify
- Portfolio update and snapshot creation
- Risk config and circuit breaker behavior

### Regression coverage

- Error handling paths
- Boundary values such as `0`, `100%`, and empty states
- API validation messages
- Frontend behavior when backend returns `4xx` or `5xx`
- Shared services used by multiple routes

### For portfolio/approval work specifically

Always test:

- Single-symbol max weight validation
- Total portfolio weight validation
- Manual portfolio edit path
- Approval modify path
- Approval apply path
- Snapshot persistence after success
- No-write behavior after failure

## 7. Known Failure Patterns To Watch

These are common sources of bugs in this repo:

1. Async SQLAlchemy object refresh issues after commit.
   Prefer `flush()` plus explicit local serialization when possible instead of
   relying on `refresh()` in fragile async paths.

2. Background tasks leaking into tests.
   API tests should validate API behavior, not depend on flaky external network
   or long-running background execution.

3. In-memory SQLite isolation surprises.
   Test fixtures must ensure sessions share the intended in-memory database.

4. Frontend silent failures.
   `fetch()` without `response.ok` checks can make failed writes look successful.

5. External data/network instability.
   Unit and API tests should not require live AKShare or live news endpoints.

## 8. Change Review Checklist

Before considering work complete, confirm:

- The fix addresses the user-visible bug, not just the symptom.
- New behavior has regression tests.
- Related main-flow tests still pass.
- Frontend build passes if UI code changed.
- Error messages are actionable.
- No unrelated user changes were reverted.

## 9. Practical Defaults For This Repo

- Prefer focused fixes over broad refactors.
- Prefer explicit validation over hidden assumptions.
- Prefer deterministic logic in tests over live network behavior.
- Prefer backend enforcement even if frontend already blocks invalid input.
- Prefer adding one good regression test over adding many weak ones.

## 10. File-Specific Guidance

If you touch:

- `backend/routers/decisions.py`
  Verify trigger/list/detail flows and background-update stability.

- `backend/routers/approvals.py`
  Verify pending-only actions, approval state transitions, and portfolio sync.

- `backend/routers/portfolio.py`
  Verify create/update/delete, summary math, and total-weight constraints.

- `backend/agents/pipeline.py`
  Verify deterministic recommendation logic, risk interaction, and unit tests.

- `frontend/src/pages/PortfolioPage.vue`
  Verify edit/add/delete error handling and visible user feedback.

- `frontend/src/pages/ApprovalDetailPage.vue`
  Verify dynamic weight editing, total-weight display, and submit blocking.

## 11. Command Reference

Backend dev server:

```powershell
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend dev server:

```powershell
cd frontend
npm run dev
```

## 12. Final Operating Principle

Do not trust an apparently small change.
In this project, many "simple" UI or route updates cross backend rules,
async database behavior, and workflow state transitions.

Read the flow, fix the bug, add the regression test, and prove it with a run.

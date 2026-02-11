# Generative AI Portfolio

A full-stack workspace combining a FastAPI backend and a Vue 3 (Vite + Vuetify + Monaco) frontend that hosts multiple mini‑apps:

- Code Generator: Generate code, tests, and documentation using an LLM.
- Code Review: LLM-assisted PR review via webhook or UI, to summarize changes and surface issues.
- Unofficial Food Packaging Forum Chatbot: A configurable retrieval‑augmented chat for the Food Packaging Forum domain, showcasing portable RAG patterns.
- ChEMBL Agent: Plan, synthesize, and execute SQLite queries against a local ChEMBL snapshot with retrieval‑augmented context, repair, and an edit workflow.

The frontend provides a single shell UI with a navigation drawer; each module is a self-contained mini app.

## Repository layout

- `backend/` — FastAPI service, LLM clients, RAG pipelines, and ChEMBL Agent orchestration.
- `frontend/` — Vue 3 app with Vuetify and Monaco, multi‑module router/shell.
- `docker-compose.yml` — Local orchestration.
- Backend logs under `/var/log/genai-portfolio` (daily‑rotated, UTC).

## Prerequisites

- Docker and Docker Compose (recommended for quick start)
- Node.js 18+ for frontend dev
- Python 3.11+ for backend dev (if not using containers)
- OpenAI API key

## Quick start (Docker Compose)

1. Copy `backend/.env.example` to `backend/.env` and set `OPENAI_API_KEY`.
2. Start services:

  docker compose up --build

3. Open http://localhost:5173

The frontend proxies `/api` to the backend service in Docker.

Logs:

- Backend writes logs to `/var/log/genai-portfolio` (same path inside container and host).
- Files rotate daily at UTC midnight; two weeks retained. Timestamps are UTC.

## Frontend (Vue 3 + Vite + Vuetify)

Multi‑module shell hosting:

- Code Generator (`/code-generator`)
- Code Review (`/code-review`)
- Unofficial Food Packaging Forum Chatbot (`/fpf-chatbot`)
- ChEMBL Agent (`/chembl-agent`)

Key features:

- Monaco editor for SQL preview with lightweight lint chips.
- Results‑first layout, CSV export, per‑column filters, and debounced re‑execute for LIMIT changes.
- “Technical details” modal with SQL, schema, optimization notes.

Dev locally:

1. Install deps: `npm ci`
2. Run dev server: `npm run dev`

Config:

- `VITE_HTTP_TIMEOUT` (ms) — HTTP client timeout; default 300000 (5m). Set 0 to disable.

## Backend (FastAPI)

Services and pipelines:

- Code gen endpoints: generate code/tests/docs and code review.
- Code Review webhook endpoint for PR review summaries.
- Unofficial Food Packaging Forum Chatbot endpoint for domain‑focused retrieval QA.
- ChEMBL Agent pipeline via LangGraph: classify → plan → retrieve → process → synthesize → execute → repair.
- Edit entrypoint for minimal SQL tweaks; `reexecute` endpoint for fast LIMIT‑only reruns.

Important endpoints (subset):

 `POST /api/chembl-agent/run` — Plan + synthesize + execute; returns SQL, schema, columns, rows, session id.
 `POST /api/chembl-agent/edit` — Apply a minimal edit to last SQL in session.
 `POST /api/chembl-agent/reexecute` — Rerun last SQL with a new LIMIT using session memory.
- `POST /api/code-review/webhook` — Accepts PR webhook payload to produce an LLM review summary.
 `POST /api/fpf-chatbot/chat` — Domain RAG chat: { prompt, api_key, config_key } → { reply }.

ChEMBL data:

- SQLite file under `backend/app/chembl/chembl_36.db` (read‑only URI).
- Chroma store under `backend/app/chroma_db/` for schema retrieval.

Safety & execution:

- Allows only SELECT/WITH, blocks DDL/DML and multi‑statements; enforces LIMIT if missing.
- SQLite executed via read‑only connection; results returned as rows/columns.

Timeouts:

- LLM upstream calls have their own client timeouts.
- Pipeline soft timeout is configurable via `CHEMBL_PIPELINE_TIMEOUT_S`; default 0 (disabled) so long DB queries aren’t killed server‑side.

## Projects in detail

### Code Generator (`/code-generator`)
- What it does: Generate source code, unit tests, and inline documentation from a natural‑language prompt and language selection.
- Key features:
  - Templated prompts per artifact (code, tests, docs) for higher quality.
  - Copy/download helpers and a simple, distraction‑free UI.
- API:
  - `POST /api/generate { prompt, language } → { code }`
  - `POST /api/tests { code } → { code }`
  - `POST /api/docs { code } → { code }`
- Why it matters: Lowers the barrier for newcomers and speeds up prototyping for the community (tutorials, workshops, hackathons). Enables quick scaffolding and example‑driven learning.

### Code Review (`/code-review`)
- What it does: Produces an LLM‑assisted review for pull requests—summarizes changes, flags risks, and suggests improvements.
- Key features:
  - Works via GitHub Webhook (PR opened/reopened) or direct PR URL input from the UI.
  - Inline comments on added lines when applicable; falls back to summary‑only if positions are rejected.
  - Comments are posted by `@anguera5`. Scope: public repositories.
- API:
  - `POST /api/code-review/webhook` → `{ review }` (set GitHub Webhook to Pull requests ONLY; secret optional)
  - `POST /api/code-review/by-url { url }` → `{ review }` (validate https://github.com/<owner>/<repo>/pull/<number>)
- Why it matters: Maintainers can triage faster and provide more consistent feedback, especially in busy OSS repos. It helps newcomers understand project standards and good practices.

### Unofficial Food Packaging Forum Chatbot (`/fpf-chatbot`)
- What it does: A domain‑focused retrieval‑augmented chat using a Chroma vector store and OpenAI.
- Key features:
  - Configurable via `config_key` to switch corpora or behaviors.
  - Clean separation of embedding, storage, and generation—easy to adapt.
- API:
  - `POST /api/fpf-chatbot/chat { prompt, api_key, config_key } → { reply }`
- Why it matters: A portable RAG pattern the community can fork to power docs Q&A, knowledge bots, and internal assistants without heavy infra.

### ChEMBL Agent (`/chembl-agent`)
- What it does: Plans and synthesizes safe SQLite SQL over a local ChEMBL snapshot using RAG for schema context, then executes locally.
- Key features:
  - LangGraph pipeline: classify → plan → retrieve → process (guidelines) → synthesize → execute → repair (loop‑capped).
  - Edit workflow for minimal changes; LIMIT re‑execute path for fast result resizing.
  - Safety guardrails: SELECT/WITH only, block DDL/DML and multi‑statements; enforce LIMIT.
  - UI: results‑first, per‑column filters, CSV export, “Technical details” modal (SQL preview with Monaco, schema, optimization notes).
- API:
  - `POST /api/chembl-agent/run` → SQL, schema snippets, columns/rows, session id (`memory_id`).
  - `POST /api/chembl-agent/edit` → updated SQL/results for a session.
  - `POST /api/chembl-agent/reexecute` → rerun last SQL with a new LIMIT.
- Why it matters: Demonstrates responsible LLM‑to‑SQL over a real scientific dataset—useful for education, reproducible data exploration, and bridging LLMs with traditional databases in a safe, auditable way.

## Environment variables

Backend:

- `OPENAI_API_KEY` — required.
- `OPENAI_MODEL` — chat model id.
- `OPENAI_EMBEDDING_MODEL` — embedding model id.
- `CHEMBL_SQLITE_PATH` — path to ChEMBL SQLite file (default `app/chembl/chembl_36.db`).
- `CHEMBL_PIPELINE_TIMEOUT_S` — soft cap for end‑to‑end pipeline (0 disables; recommended when using large DB).

Frontend:

- `VITE_HTTP_TIMEOUT` — axios timeout in ms (0 disables; default 300000).

## Development

Backend (local):

1. Create venv and install: `pip install -e .`
2. Run: `uvicorn app.main:app --reload`

Logging locally (without Docker):

- Logs will be written to `/var/log/genai-portfolio`. Ensure your user has write permissions or run with appropriate privileges.

Frontend (local):

1. `npm ci`
2. `npm run dev`

## Adding a new frontend module

1. Create `src/modules/<your-module>/` with a root `<YourModuleApp>.vue`.
2. Register a lazy route in `src/router.ts` and metadata in `src/modules/index.ts`.

## Notes

- The app saves ChEMBL sessions by `memory_id` to support edits and quick LIMIT re‑execution.
- If you deploy behind a reverse proxy, align proxy read timeouts with your chosen server/client timeouts or use an async job API for very long queries.

# Technical Design Document

## 1. Problem and goals

The product is a sales intelligence workspace for cybersecurity prospecting. It aims to answer two questions quickly:

- which accounts look important right now?
- why do they look important, and which sales actions are justified?

The current implementation focuses on a modular backend plus a React frontend. The code is organized around a standard service boundary model rather than a cloud-only deployment model.

## 2. Bounded contexts

```mermaid
flowchart TD
    Frontend[React frontend] --> Gateway[FastAPI app]
    Gateway --> Accounts[Accounts service]
    Gateway --> Auth[Auth service]
    Gateway --> Scorer[Scorer service]
    Gateway --> Crawler[Crawler service]
    Gateway --> Eval[Eval service]
    Gateway --> Jobs[Jobs service]
    Gateway --> Prompts[Prompt registry]
    Gateway --> DB[Database service]
```

## 3. Service responsibilities

### Accounts service

Responsibilities:

- list and filter accounts
- search by domain or signal
- retrieve account detail and version history
- aggregate summary counts
- compute priority-tier classifications

Key files:

- `backend/src/services/accounts/accounts_service.py`
- `backend/src/services/accounts/api.py`
- `backend/src/services/accounts/repositories/*`

### Auth service

Responsibilities:

- signup and signin
- JWT minting and validation
- user profile retrieval
- per-user Gemini API key storage and retrieval

Key files:

- `backend/src/services/auth/auth_service.py`
- `backend/src/services/auth/api.py`
- `backend/src/services/auth/security.py`

### Scorer service

Responsibilities:

- prepare prompt context from an account and its signals
- call Google Gemini with the `google-genai` SDK
- enforce JSON payload handling and score formatting
- store score history and latest score for the account

Key files:

- `backend/src/services/scorer/scorer_service.py`
- `backend/src/services/scorer/api.py`

### Database service

Responsibilities:

- initialize the system schema
- manage PostgreSQL connection and session creation
- provide health and stats endpoints
- support test isolation through SQLite-only local DB paths

Key files:

- `backend/src/services/database/database_service.py`
- `backend/src/services/database/__init__.py`

### Eval and prompts services

Responsibilities:

- prompt version lookup and registry management
- LLM comparative evaluation runs
- scoring benchmark output and result retrieval

Key files:

- `backend/src/services/eval/`
- `backend/src/services/prompts/`

## 4. Data and persistence

The runtime is PostgreSQL-first. The key configuration variable is `DATABASE_URL`.

```env
DATABASE_URL=postgresql+psycopg://user:password@host:5432/sales_intel
GEMINI_API_KEY=your_key_here
JWT_SECRET=your-secret
```

The database layer is responsible for:

- session creation
- schema initialization
- health checks
- raw query and diagnostics features

SQLite is intentionally not the normal runtime storage model. It exists to keep tests isolated and predictable.

## 5. API contract model

The primary app entry point is `backend/src/main.py`. It mounts routers for the following domain surfaces:

- `/api/auth`
- `/api/accounts`
- `/api/score`
- `/api/crawler`
- `/api/eval`
- `/api/prompts`
- `/api/jobs`
- `/api/database`

This makes the app easy to reason about in a single local runtime while still keeping the domain logic separated into service packages.

## 6. Frontend integration

The frontend is a Vite React application. It stores the JWT in local storage and automatically attaches the bearer token to subsequent API calls via `axios` interceptors.

This means the app acts like a standard web app with user identity and account workflows rather than a purely static dashboard.

## 7. Development constraints and guardrails

- Prefer Python 3.11 and type-safe service logic
- Keep `DATABASE_URL` configured for any real backend run
- Use `GEMINI_API_KEY` for scoring and evals
- Use SQLite test fixtures for isolated unit tests
- Keep API and frontend route semantics aligned while adding features

## 8. Future direction

The current codebase is already organized like a modular app that can grow without collapsing into a monolith. The next natural evolution is to add more structured monitoring, stronger deployment automation, and a richer eval framework around prompt and model changes.

The architecture is stable because it is simple: one app, one backend, one main relational database, and a focused external AI integration layer.
```

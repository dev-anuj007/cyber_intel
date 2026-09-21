# Sales Intelligence Platform

A local-first web application for B2B cybersecurity prospecting and account intelligence. It combines a FastAPI backend, a Vite + React frontend, PostgreSQL-backed storage, and Gemini-powered scoring to help teams review account risk, account signals, and score history from a single workspace.

---

## What this project does

- Surfaces account-level summaries and detail views for sales and security prospecting
- Lets users sign in with JWT-based auth and store their own Gemini API key
- Searches and filters accounts by domain, signal, and priority tier
- Scores accounts with Gemini using account context plus discovered signals
- Runs developer evaluation flows and prompt comparison jobs
- Exposes a modular backend with dedicated service packages for auth, accounts, scorer, crawler, jobs, eval, and prompts

---

## Tech stack

- Backend: Python, FastAPI, SQLModel, PostgreSQL, PyJWT, google-genai
- Frontend: React, TypeScript, Vite, Zustand, Axios
- Database: PostgreSQL via `DATABASE_URL`; SQLite is only used for test isolation
- Observability: Logfire optional instrumentation
- Testing: pytest + coverage

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL instance or local Postgres service
- Gemini API key for scoring and eval workflows

---

## Local setup

### 1. Backend

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env
```

Then update `.env` with your local values, for example:

```env
DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/sales_intel
GEMINI_API_KEY=your_key_here
JWT_SECRET=change-this-in-local-dev
GEMINI_MODEL=gemini-3.1-flash-lite
```

Start the API:

```bash
python src/main.py
```

The backend listens on `http://localhost:8000` and exposes Swagger docs at `http://localhost:8000/docs`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the Vite app at `http://localhost:5173`.

---

## Key backend entry points

The main app is mounted in `backend/src/main.py` and includes the following routers:

- `/api/auth`
- `/api/accounts`
- `/api/score`
- `/api/crawler`
- `/api/eval`
- `/api/prompts`
- `/api/jobs`
- `/api/database`

A health check is available at:

- `GET /health`
- `GET /`

---

## Repository layout

```text
.
├── backend/
│   ├── src/
│   │   ├── core/
│   │   ├── main.py
│   │   └── services/
│   │       ├── accounts/
│   │       ├── auth/
│   │       ├── crawler/
│   │       ├── database/
│   │       ├── eval/
│   │       ├── jobs/
│   │       ├── logger/
│   │       ├── prompts/
│   │       └── scorer/
│   ├── .env.example
│   ├── requirements.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   ├── mkdocs.yml
│   └── src/
├── script/
│   ├── bootstrap_e2e_test.py
│   ├── migrate_sqlite_to_postgres.py
│   └── validate_crawler_signals.py
├── conftest.py
├── pytest.ini
├── pyrightconfig.json
├── GEMINI.md
└── README.md
```

---

## Typical development workflow

1. Start PostgreSQL and configure `DATABASE_URL` in the backend environment
2. Run the FastAPI app locally
3. Sign in through the frontend and add a Gemini API key in the profile modal
4. Use the accounts dashboard to search, inspect signals, and score accounts
5. Run eval and prompt workflows from the developer tools section in the UI
6. Run unit tests from the backend with `pytest`

---

## Testing

```bash
cd backend
pytest
```

The repo includes service-level tests under each `src/services/*/tests` package. SQLite-backed temp DBs are used for test isolation; production logic expects PostgreSQL via `DATABASE_URL`.

---

## Notes

- `DATABASE_URL` is the main runtime dependency for the app.
- SQLite connection paths are used only in tests and isolated database fixtures.
- The app supports BYOK Gemini keys per user, as well as environment-level fallback configuration for local development.
- The UI and API are designed to work together, with the frontend automatically attaching JWT bearer tokens when a user is logged in.

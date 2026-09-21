# Sales Intelligence Platform

This project is a local-first sales intelligence workspace for cybersecurity prospecting. It combines a FastAPI backend, a React + Vite frontend, and PostgreSQL-backed data services to search accounts, review signals, and score account risk with Gemini.

## System overview

`mermaid
flowchart LR
    User[Sales or security user] --> Frontend[React + Vite frontend]
    Frontend --> API[FastAPI backend]
    API --> Auth[Auth service]
    API --> Accounts[Accounts service]
    API --> Scorer[Scorer service]
    API --> Crawler[Crawler service]
    API --> Eval[Eval service]
    API --> Jobs[Jobs service]
    API --> DB[(PostgreSQL)]
    Scorer --> Gemini[Google Gemini API]
`

## What the platform includes

- account listing, filtering, and detail views
- JWT-based authentication with user-managed Gemini API keys
- risk scoring with LLM-generated summaries and score history
- prompt registry and eval comparison workflows
- background job orchestration and app health checks
- modular service packages for clear domain boundaries

## Current architecture

The repository is best understood as a normal Python + React application.

- backend/src/main.py mounts the router set for the API
- backend/src/services/* groups the app by domain area
- DatabaseService prefers DATABASE_URL and PostgreSQL
- SQLite is only used for isolated test fixtures and debug scenarios
- the frontend calls the backend at http://localhost:8000/api

## Local developer workflow

`bash
cd backend
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env
python src/main.py
`

Then in another terminal:

`bash
cd frontend
npm install
npm run dev
`

The UI runs on http://localhost:5173 and the API docs on http://localhost:8000/docs.

## Key backend routes

- /api/auth — signup, signin, profile, API key management
- /api/accounts — search, list, detail, summary, and signal logic
- /api/score — score execution and score history retrieval
- /api/crawler — crawler jobs and scan endpoints
- /api/eval — prompt eval runs and comparison workflows
- /api/prompts — prompt registry and template lookup
- /api/jobs — async job lifecycle operations
- /api/database — DB health and query helpers

## Storage and data model

The app uses a relational PostgreSQL database as the system of record. The service layer is built with SQLModel and SQLAlchemy, and the database layer detects whether the connection is PostgreSQL or a temporary SQLite test connection.

This keeps the local developer experience simple while still supporting a production-ready relational database path.

## Operational guidance

- keep the runtime database connection in backend/.env
- store the Gemini API key in the environment or in a user profile
- run the backend and frontend together during development
- prefer tests in the service directories before making behavior changes

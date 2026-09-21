# How We Build

## Development approach

The repo is built like a normal Python + React application. The work is organized around clear service boundaries, tests, and a local configuration flow.

## Main workflow

1. define the behavior in a service or API-level test
2. implement the smallest valid change in the right service package
3. validate with pytest or targeted smoke checks
4. confirm the frontend still matches the backend contract
5. repeat until the feature is stable

## Service layout

The backend is split into dedicated modules under ackend/src/services:

- ccounts for account discovery and detail queries
- uth for authentication and BYOK API key handling
- scorer for Gemini-driven scoring
- crawler for scan and job related APIs
- eval for benchmark and comparison flows
- prompts for template management
- jobs for background task state
- database for PostgreSQL health and schema setup

This is a practical modular structure that keeps the code easy to follow and test.

## Local verification loop

`ash
cd backend
pytest
`

Then run the app locally:

`ash
python src/main.py
`

And the frontend:

`ash
cd frontend
npm run dev
`

## Operating principles

- configuration lives in environment variables and the central config module
- database and auth are treated as core runtime dependencies
- tests are expected to validate real behavior, not mock-only paths
- new features should fit the existing service boundaries rather than bypassing them

## Why this approach works

The project benefits from a simple architecture: one backend, one frontend, one primary relational database, and targeted external AI calls. That keeps the runtime easier to reason about and makes debugging, testing, and feature work more reliable.
